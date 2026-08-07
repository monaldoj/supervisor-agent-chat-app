# Responses API Agent

This template defines a conversational agent app. The app comes with a built-in chat UI, but also exposes an API endpoint for invoking the agent so that you can serve your UI elsewhere (e.g. on your website or in a mobile app).

The agent in this template implements the [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses) interface. It ships with a sample `get_current_time` tool. The agent code includes commented-out examples showing how to connect to [Databricks MCP servers](https://docs.databricks.com/aws/en/generative-ai/agent-framework/agent-tool) (including the built-in code interpreter, Vector Search, Genie, and UC functions). You can customize agent code and test it via the API or UI.

The agent input and output format are defined by MLflow's ResponsesAgent interface, which closely follows the [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses) interface. See [the MLflow docs](https://mlflow.org/docs/latest/genai/flavors/responses-agent-intro/) for input and output formats for streaming and non-streaming requests, tracing requirements, and other agent authoring details.

## Build with AI Assistance

We recommend using AI coding assistants (Claude Code, Cursor, GitHub Copilot) to customize and deploy this template. Agent Skills in `.claude/skills/` provide step-by-step guidance for common tasks like setup, adding tools, and deployment. These skills are automatically detected by Claude, Cursor, and GitHub Copilot.

## Quick start

Run the `uv run quickstart` script to quickly set up your local environment and start the agent server. At any step, if there are issues, refer to the manual local development loop setup below.

This script will:

1. Verify uv, nvm, and Databricks CLI installations
2. Configure Databricks authentication
3. Configure agent tracing, by creating and linking an MLflow experiment to your app
4. Start the agent server and chat app

```bash
uv run quickstart
```

After the setup is complete, you can start the agent server and the chat app locally with:

```bash
uv run start-app
```

This will start the agent server and the chat app at http://localhost:8000.

**Next steps**: see [modifying your agent](#modifying-your-agent) to customize and iterate on the agent code.

## Manual local development loop setup

1. **Set up your local environment**
   Install `uv` (python package manager), `nvm` (node version manager), and the Databricks CLI:

   - [`uv` installation docs](https://docs.astral.sh/uv/getting-started/installation/)
   - [`nvm` installation](https://github.com/nvm-sh/nvm?tab=readme-ov-file#installing-and-updating)
     - Run the following to use Node 20 LTS:
       ```bash
       nvm use 20
       ```
   - [`databricks CLI` installation](https://docs.databricks.com/aws/en/dev-tools/cli/install)

2. **Set up local authentication to Databricks**

   In order to access Databricks resources from your local machine while developing your agent, you need to authenticate with Databricks. Choose one of the following options:

   **Option 1: OAuth via Databricks CLI (Recommended)**

   Authenticate with Databricks using the CLI. See the [CLI OAuth documentation](https://docs.databricks.com/aws/en/dev-tools/cli/authentication#oauth-user-to-machine-u2m-authentication).

   ```bash
   databricks auth login
   ```

   Set the `DATABRICKS_CONFIG_PROFILE` environment variable in your .env file to the profile you used to authenticate:

   ```bash
   DATABRICKS_CONFIG_PROFILE="DEFAULT" # change to the profile name you chose
   ```

   **Option 2: Personal Access Token (PAT)**

   See the [PAT documentation](https://docs.databricks.com/aws/en/dev-tools/auth/pat#databricks-personal-access-tokens-for-workspace-users).

   ```bash
   # Add these to your .env file
   DATABRICKS_HOST="https://host.databricks.com"
   DATABRICKS_TOKEN="dapi_token"
   ```

   See the [Databricks SDK authentication docs](https://docs.databricks.com/aws/en/dev-tools/sdk-python#authenticate-the-databricks-sdk-for-python-with-your-databricks-account-or-workspace).

3. **Create and link an MLflow experiment to your app**

   Create an MLflow experiment to enable tracing and version tracking. This is automatically done by the `uv run quickstart` script.

   Create the MLflow experiment via the CLI:

   ```bash
   DATABRICKS_USERNAME=$(databricks current-user me | jq -r .userName)
   databricks experiments create-experiment /Users/$DATABRICKS_USERNAME/agents-on-apps
   ```

   Make a copy of `.env.example` to `.env` and update the `MLFLOW_EXPERIMENT_ID` in your `.env` file with the experiment ID you created. The `.env` file will be automatically loaded when starting the server.

   ```bash
   cp .env.example .env
   # Edit .env and fill in your experiment ID
   ```

   See the [MLflow experiments documentation](https://docs.databricks.com/aws/en/mlflow/experiments#create-experiment-from-the-workspace).

4. **Test your agent locally**

   Start up the agent server and chat UI locally:

   ```bash
   uv run start-app
   ```

   Query your agent via the UI (http://localhost:8000) or REST API:

   **Advanced server options:**

   ```bash
   uv run start-server --reload   # hot-reload the server on code changes
   uv run start-server --port 8001 # change the port the server listens on
   uv run start-server --workers 4 # run the server with multiple workers
   ```

   - Example streaming request:
     ```bash
     curl -X POST http://localhost:8000/invocations \
     -H "Content-Type: application/json" \
     -d '{ "input": [{ "role": "user", "content": "hi" }], "stream": true }'
     ```
   - Example non-streaming request:
     ```bash
     curl -X POST http://localhost:8000/invocations  \
     -H "Content-Type: application/json" \
     -d '{ "input": [{ "role": "user", "content": "hi" }] }'
     ```

## Modifying your agent

This app does not run its own agent loop. `agent.py` forwards each request to a Databricks
Supervisor Agent serving endpoint (set via `ENDPOINT`), which does tool selection and
orchestration server-side. To change the agent's tools, instructions, or sub-agents, edit the
Multi-Agent Supervisor in the Databricks UI — see the
[Multi-Agent Supervisor documentation](https://docs.databricks.com/aws/en/generative-ai/agent-bricks/multi-agent-supervisor).

To point this app at a different endpoint, change `ENDPOINT` in `backend_agent_server/agent.py` and update
the `supervisor-endpoint` resource in `databricks.yml`.

### Tool approvals

The endpoint pauses before every MCP tool call and asks for approval. The chat UI renders these as
an **Allow / Deny** prompt, and approving sends the answer back so the tool runs.

Tools named in `AUTO_APPROVED_TOOLS` (in `backend_agent_server/agent.py`) skip that prompt — the app
approves them itself and shows them as an ordinary tool call. `web_search` is auto-approved by
default because it is read-only. Any tool not listed still requires the user to click Allow, so add
a tool only if it is safe to run unattended.

Required files for hosting with MLflow `AgentServer`:

- `agent.py`: Contains your agent logic. Modify this file to create your custom agent. For example, you can [add agent tools](https://docs.databricks.com/aws/en/generative-ai/agent-framework/agent-tool) to give your agent additional capabilities
- `start_server.py`: Initializes and runs the MLflow `AgentServer` with agent_type="ResponsesAgent". You don't have to modify this file for most common use cases, but can add additional server routes (e.g. a `/metrics` endpoint) here

**Common customization questions:**

**Q: Can I add additional files or folders to my agent?**
Yes. Add additional files or folders as needed. Ensure the script within `pyproject.toml` runs the correct script that starts the server and sets up MLflow tracing.

**Q: How do I add dependencies to my agent?**
Run `uv add <package_name>` (e.g., `uv add "mlflow-skinny[databricks]"`). See the [python pyproject.toml guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#dependencies-and-requirements).

**Q: Can I add custom tracing beyond the built-in tracing?**
Yes. This template uses MLflow's agent server, which comes with automatic tracing for agent logic decorated with `@invoke()` and `@stream()`. It also uses [MLflow autologging APIs](https://mlflow.org/docs/latest/genai/tracing/#one-line-auto-tracing-integrations) to capture traces from LLM invocations. However, you can add additional instrumentation to capture more granular trace information when your agent runs. See the [MLflow tracing documentation](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/app-instrumentation/).

**Q: How can I extend this example with additional tools and capabilities?**
This template can be extended by integrating additional MCP servers, Vector Search Indexes, UC Functions, and other Databricks tools. See the ["Agent Framework Tools Documentation"](https://docs.databricks.com/aws/en/generative-ai/agent-framework/agent-tool).

## Evaluating your agent

Evaluate your agent by calling the invoke function you defined for the agent locally.

- Update your `evaluate_agent.py` file with the preferred evaluation dataset and scorers.

Run the evaluation using the evaluation script:

```bash
uv run agent-evaluate
```

After it completes, open the MLflow UI link for your experiment to inspect results.

## Chat history: Persistent vs Ephemeral mode

The chat UI runs in one of two modes depending on whether a Postgres/Lakebase database is reachable:

- **Persistent mode** — chat history is stored in Lakebase and shown in the sidebar. Active when
  the database connection env vars (`PGDATABASE`/`PGHOST`, or `POSTGRES_URL`) are present.
- **Ephemeral mode** — history lives in memory and is lost on restart; an "Ephemeral" badge shows
  in the UI. This is the fallback when no database is configured.

The frontend detects the mode automatically from the environment — you don't set a flag.

**In a Databricks Apps deployment**, the `databricks.yml` bundle stands up a Lakebase instance and
binds it to the app, so the platform injects the `PG*` variables and the app runs in **Persistent
mode** by default.

**Locally**, set `LAKEBASE_INSTANCE_NAME` in `.env` to a Lakebase instance you can access. On
`uv run start-app` the launcher resolves the instance's host via the Databricks CLI and enters
Persistent mode; if the instance can't be found (or the var is unset and no `PGHOST`/`POSTGRES_URL`
is provided), it falls back to **Ephemeral mode**. You can also set the `PG*` variables explicitly
to skip auto-resolution — see `.env.example`.

## Deploying to Databricks Apps

This template uses [Databricks Asset Bundles (DABs)](https://docs.databricks.com/aws/en/dev-tools/bundles/) for deployment. The `databricks.yml` file defines the app configuration and resource permissions, and provisions a **Lakebase instance** (`sa-chat-lakebase-<suffix>`, capacity `CU_1`) bound to the app for persistent chat history.

### Required environment variables

There are two different configuration contexts:

- **Local development (`.env`)**: `DATABRICKS_CONFIG_PROFILE`, `MLFLOW_EXPERIMENT_ID`, and
  `SUPERVISOR_ENDPOINT_NAME` are read by local commands such as `uv run preflight`. The `.env` file
  is not used as the deployed app's runtime environment.
- **Bundle deployment (your shell)**: `BUNDLE_VAR_supervisor_endpoint_name` supplies the required
  `supervisor_endpoint_name` bundle variable. The bundle injects its value into the deployed app as
  `SUPERVISOR_ENDPOINT_NAME` when `bundle run` starts the app.

Load `.env`, then reuse the local endpoint name for the bundle:

```bash
set -a
source .env
set +a

export BUNDLE_VAR_supervisor_endpoint_name="$SUPERVISOR_ENDPOINT_NAME"
```

`DATABRICKS_CONFIG_PROFILE` selects the workspace used by every Databricks CLI command. Always pass
it with `--profile` to avoid deploying to a different workspace.

The deployed app receives the remaining runtime variables automatically:

- `MLFLOW_TRACKING_URI` and `MLFLOW_REGISTRY_URI` come from the app configuration.
- `MLFLOW_EXPERIMENT_ID` comes from the bound experiment resource.
- `PGHOST`, `PGUSER`, `PGDATABASE`, and `PGPORT` come from the bound Lakebase resource.

Do not manually copy these deployed values into `.env`.

> **`app.yaml` vs `databricks.yml`**: `app.yaml` is used when deploying via `databricks apps deploy` (manual path). When deploying via DABs (`databricks bundle deploy`), the `config:` section in `databricks.yml` takes precedence. If you change environment variables or the start command, update `databricks.yml` — that's what DABs reads.

Ensure you have the [Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/tutorial) installed and configured.

1. **Run the pre-flight check**

   Start the agent locally, send a test request, and verify the response to catch configuration and code errors early:

   ```bash
   uv run preflight
   ```

2. **Validate the bundle configuration**

   Catch any configuration errors before deploying:

   ```bash
   databricks bundle validate --profile "$DATABRICKS_CONFIG_PROFILE"
   ```

3. **Deploy the bundle**

   This configures the resources (MLflow experiment, serving endpoint permission, Lakebase instance,
   etc.) defined in `databricks.yml`. The exported `BUNDLE_VAR_supervisor_endpoint_name` is resolved
   into the app configuration:

   ```bash
   databricks bundle deploy --profile "$DATABRICKS_CONFIG_PROFILE"
   ```

   > **First deploy provisions Lakebase**, which takes ~5–10 minutes and incurs cost (~$0.70/hr for `CU_1`). The app becomes reachable once the instance is ready.

4. **Start or restart the app**

   Upload the source and start the app with the bundle-generated runtime environment:

   ```bash
   databricks bundle run agent_supervisor_chat \
     --profile "$DATABRICKS_CONFIG_PROFILE"
   ```

   > **Important:** `bundle deploy` alone does not apply the runtime environment or start the new
   > source deployment. `bundle run` is required. Keep
   > `BUNDLE_VAR_supervisor_endpoint_name` exported for both commands; restarting from the Apps UI
   > does not resolve bundle variables.

   To grant access to additional resources (serving endpoints, genie spaces, UC Functions, Vector Search), add them to `databricks.yml` and redeploy. See the [Databricks Apps resources documentation](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/resources).

   **On-behalf-of (OBO) User Authentication**: Use `get_user_workspace_client()` from `backend_agent_server.utils` to authenticate as the requesting user instead of the app service principal. See the [OBO authentication documentation](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth?language=Streamlit#retrieve-user-authorization-credentials).

5. **Query your agent hosted on Databricks Apps**

   You must use a Databricks OAuth token to query agents hosted on Databricks Apps. See [Query an agent](https://docs.databricks.com/aws/en/generative-ai/agent-framework/query-agent) for full details.

   **Using the Databricks OpenAI client (Python):**

   ```bash
   uv pip install databricks-openai
   ```

   ```python
   from databricks.sdk import WorkspaceClient
   from databricks_openai import DatabricksOpenAI

   w = WorkspaceClient()
   client = DatabricksOpenAI(workspace_client=w)

   # Non-streaming
   response = client.responses.create(
       model="apps/<app-name>",
       input=[{"role": "user", "content": "hi"}],
   )
   print(response)

   # Streaming
   streaming_response = client.responses.create(
       model="apps/<app-name>",
       input=[{"role": "user", "content": "hi"}],
       stream=True,
   )
   for chunk in streaming_response:
       print(chunk)
   ```

   **Using curl:**

   ```bash
   # Generate an OAuth token
   databricks auth login --host <https://host.databricks.com>
   databricks auth token
   ```

   ```bash
   # Streaming request
   curl --request POST \
     --url <app-url>.databricksapps.com/responses \
     --header "Authorization: Bearer <oauth-token>" \
     --header "Content-Type: application/json" \
     --data '{
       "input": [{ "role": "user", "content": "hi" }],
       "stream": true
     }'
   ```

   ```bash
   # Non-streaming request
   curl --request POST \
     --url <app-url>.databricksapps.com/responses \
     --header "Authorization: Bearer <oauth-token>" \
     --header "Content-Type: application/json" \
     --data '{
       "input": [{ "role": "user", "content": "hi" }]
     }'
   ```

For future updates, load `.env`, export `BUNDLE_VAR_supervisor_endpoint_name`, then run both
deployment commands:

```bash
set -a
source .env
set +a
export BUNDLE_VAR_supervisor_endpoint_name="$SUPERVISOR_ENDPOINT_NAME"

databricks bundle deploy --profile "$DATABRICKS_CONFIG_PROFILE"
databricks bundle run agent_supervisor_chat \
  --profile "$DATABRICKS_CONFIG_PROFILE"
```

### Common Issues

- **`databricks bundle deploy` fails with "An app with the same name already exists"**

  This happens when an app with the same name was previously created outside of DABs. To fix, bind the existing app to your bundle:

  ```bash
  # 1. Get the existing app's config (note the budget_policy_id if present)
  databricks apps get <app-name> --output json \
    --profile "$DATABRICKS_CONFIG_PROFILE" |
    jq '{name, budget_policy_id, description}'

  # 2. Update databricks.yml to include budget_policy_id if it was returned above

  # 3. Bind the existing app to your bundle
  databricks bundle deployment bind agent_supervisor_chat <app-name> \
    --auto-approve \
    --profile "$DATABRICKS_CONFIG_PROFILE"

  # 4. Deploy and start (after exporting BUNDLE_VAR_supervisor_endpoint_name)
  databricks bundle deploy --profile "$DATABRICKS_CONFIG_PROFILE"
  databricks bundle run agent_supervisor_chat \
    --profile "$DATABRICKS_CONFIG_PROFILE"
  ```

  Alternatively, delete the existing app and deploy fresh: `databricks apps delete <app-name>` (this permanently removes the app's URL and service principal).

- **`databricks bundle deploy` fails with "Provider produced inconsistent result after apply"**

  The existing app has server-side configuration (like `budget_policy_id`) that doesn't match your `databricks.yml`. Run `databricks apps get <app-name> --output json` and sync any missing fields to your `databricks.yml`.

- **App is running old code after `databricks bundle deploy`**

  `bundle deploy` configures resources, but `bundle run` uploads and starts the source deployment.
  Run both commands shown above.

- **Startup fails with `SUPERVISOR_ENDPOINT_NAME is not set`**

  Export `BUNDLE_VAR_supervisor_endpoint_name` before both `bundle deploy` and `bundle run`. The
  similarly named `SUPERVISOR_ENDPOINT_NAME` in `.env` is only loaded automatically by local
  application commands. Avoid restarting the app from the UI when its configuration depends on
  bundle variables.

### FAQ

- For a streaming response, I see a 200 OK in the logs, but an error in the actual stream. What's going on?
  - This is expected behavior. The initial 200 OK confirms stream setup; streaming errors don't affect this status.
- When querying my agent, I get a 302 error. What's going on?
  - Use an OAuth token. PATs are not supported for querying agents.
