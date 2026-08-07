import logging
import os
from typing import Any, Generator
from uuid import uuid4

import mlflow
from databricks.sdk import WorkspaceClient
from databricks_openai import DatabricksOpenAI
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

from backend_agent_server.utils import get_session_id, get_user_workspace_client

mlflow.openai.autolog()

logger = logging.getLogger(__name__)

# GENERATED

NAME = 'agent-supervisor-chat'
# Databricks Supervisor Agent (Agent Bricks Multi-Agent Supervisor) serving endpoint.
# The endpoint runs the agent loop and tool selection server-side, so this app only proxies to it.
# The endpoint name is required and supplied via the SUPERVISOR_ENDPOINT_NAME env var. In a
# Databricks Apps deployment the DAB injects it from the `supervisor_endpoint_name` bundle
# variable; for local runs set it in .env.
ENDPOINT = os.environ.get("SUPERVISOR_ENDPOINT_NAME")
if not ENDPOINT:
    raise RuntimeError(
        "SUPERVISOR_ENDPOINT_NAME is not set. Set it in .env for local runs, or provide the "
        "`supervisor_endpoint_name` bundle variable when deploying (databricks bundle deploy "
        "--var supervisor_endpoint_name=<endpoint>)."
    )

# MCP tools approved automatically, without prompting the user. The endpoint pauses on an
# `mcp_approval_request` for every MCP tool call; for read-only tools like web search the prompt is
# just friction. Tools not listed here still surface Allow/Deny in the chat UI, so add a tool here
# only if it is safe to run unattended.
AUTO_APPROVED_TOOLS = {"web_search"}

# END GENERATED

# Ceiling on auto-approve round trips per user turn, so a tool that re-requests approval every time
# cannot spin forever.
MAX_AUTO_APPROVAL_ROUNDS = 5


def get_endpoint_workspace_client() -> WorkspaceClient | None:
    # Uncomment the line below to call the endpoint as the requesting user (on-behalf-of-user
    # auth) instead of as the app's service principal. Requires the `model-serving` scope in
    # app.yaml, and each user needs CAN_QUERY on the endpoint.
    # return get_user_workspace_client()
    return None


def get_client() -> DatabricksOpenAI:
    return DatabricksOpenAI(workspace_client=get_endpoint_workspace_client())


def _auto_approvals(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build approval responses for pending requests naming an auto-approved tool."""
    return [
        {
            "type": "mcp_approval_response",
            "approval_request_id": item["id"],
            "approve": True,
        }
        for item in items
        if item.get("type") == "mcp_approval_request" and item.get("name") in AUTO_APPROVED_TOOLS
    ]


def _as_function_call(item: dict[str, Any]) -> dict[str, Any]:
    """Render an auto-approved request as a plain function_call.

    The UI turns `mcp_approval_request` into an Allow/Deny prompt. Once we have approved on the
    user's behalf there is nothing to decide, so present it as a normal tool call instead — the
    `function_call_output` the endpoint returns next carries a matching `call_id` and pairs with it.
    """
    return {
        "type": "function_call",
        "id": item["id"],
        "call_id": item["id"],
        "name": item["name"],
        "arguments": item.get("arguments", "{}"),
    }


def _normalize_output_item(item: dict[str, Any], seen_ids: set[str]) -> dict[str, Any]:
    """Give each output item a unique id.

    The supervisor endpoint reuses one id across the message and the function_call it
    emits in the same step. The chat UI keys items by id, so duplicates make a tool call
    overwrite the message it arrived with. Text deltas reference the message's id, so the
    first item to claim an id keeps it and later collisions are reassigned.
    """
    item_id = item.get("id")
    if item_id is None:
        return item
    if item_id in seen_ids:
        return {**item, "id": str(uuid4())}
    seen_ids.add(item_id)
    return item


@invoke()
def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    if session_id := get_session_id(request):
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})

    client = get_client()
    conversation = [i.model_dump(exclude_none=True) for i in request.input]
    output: list[dict[str, Any]] = []

    # Each auto-approval needs another round trip: the endpoint stops at the approval request and
    # only runs the tool once the approval is sent back. Bounded so a tool that keeps asking for
    # approval cannot loop forever.
    for _ in range(MAX_AUTO_APPROVAL_ROUNDS):
        # exclude_none: the endpoint sends explicit nulls for unset fields (e.g. `annotations`),
        # which fail ResponsesAgentResponse validation for fields typed as lists.
        items = [
            item.model_dump(exclude_none=True)
            for item in client.responses.create(
                model=ENDPOINT, input=conversation, stream=False
            ).output
        ]
        approvals = _auto_approvals(items)
        output.extend(
            _as_function_call(i)
            if any(a["approval_request_id"] == i.get("id") for a in approvals)
            else i
            for i in items
        )
        if not approvals:
            break
        conversation = conversation + items + approvals
    else:
        logger.warning(
            "Hit MAX_AUTO_APPROVAL_ROUNDS (%s) with approvals still pending; "
            "the reply may be cut short.",
            MAX_AUTO_APPROVAL_ROUNDS,
        )

    seen_ids: set[str] = set()
    return ResponsesAgentResponse(
        output=[_normalize_output_item(item, seen_ids) for item in output]
    )


@stream()
def stream_handler(
    request: ResponsesAgentRequest,
) -> Generator[ResponsesAgentStreamEvent, None, None]:
    if session_id := get_session_id(request):
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})

    client = get_client()
    conversation = [i.model_dump(exclude_none=True) for i in request.input]
    seen_ids: set[str] = set()

    for _ in range(MAX_AUTO_APPROVAL_ROUNDS):
        items: list[dict[str, Any]] = []
        pending_approvals: list[dict[str, Any]] = []

        for event in client.responses.create(model=ENDPOINT, input=conversation, stream=True):
            event_data = event if isinstance(event, dict) else event.model_dump(exclude_none=True)
            event_type = event_data.get("type")
            item = event_data.get("item") or {}

            # Drop the tool sub-agent's own narration. After a tool runs, its raw answer is streamed
            # as `step: 0` text *and* delivered as the function_call_output holding the same content,
            # so forwarding both shows the result twice. The supervisor's own messages are step >= 1.
            if event_type == "response.output_text.delta" and event_data.get("step") == 0:
                continue

            if item.get("type") == "mcp_approval_request" and item.get("name") in AUTO_APPROVED_TOOLS:
                # Hold the approval prompt back: show it as an ordinary tool call instead.
                if event_type == "response.output_item.done":
                    items.append(item)
                    pending_approvals.extend(_auto_approvals([item]))
                    event_data = {**event_data, "item": _as_function_call(item)}
                else:
                    continue
            elif event_type == "response.output_item.done" and item:
                items.append(item)

            if event_type == "response.output_item.done" and event_data.get("item"):
                event_data = {
                    **event_data,
                    "item": _normalize_output_item(event_data["item"], seen_ids),
                }
            yield event_data

        if not pending_approvals:
            return
        conversation = conversation + items + pending_approvals

    logger.warning(
        "Hit MAX_AUTO_APPROVAL_ROUNDS (%s) with approvals still pending; "
        "the reply may be cut short.",
        MAX_AUTO_APPROVAL_ROUNDS,
    )
