# Setting Up a Custom GPT with DevOps Control Tower

This guide walks through creating a ChatGPT custom GPT that can submit and track tasks in your DevOps Control Tower (JCT) instance.

## Prerequisites

- A running JCT instance accessible over HTTPS on a public domain (e.g. `https://api.yourdomain.com`)
- A ChatGPT Plus or Enterprise account (custom GPTs require a paid plan)

## 1. Configure the JCT Server

Set these environment variables on your JCT deployment:

```bash
# A secret key ChatGPT will use to authenticate. Generate one with:
#   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
JCT_API_KEY=your-generated-secret-key

# The public HTTPS URL where your JCT API is reachable
JCT_API_BASE_URL=https://api.yourdomain.com
```

Both go in your `.env` file or however you inject env vars in production.

When `JCT_API_KEY` is set, the three task endpoints (`POST /tasks/enqueue`, `GET /tasks`, `GET /tasks/{id}`) require a bearer token. All other endpoints (health checks, CWOM, etc.) remain unauthenticated.

## 2. Verify the OpenAPI Spec

JCT serves a ChatGPT-compatible OpenAPI spec at `/openapi-gpt.json`. Verify it's working:

```bash
curl https://api.yourdomain.com/openapi-gpt.json | python3 -m json.tool
```

You should see a JSON document with:
- `info.title`: "DevOps Control Tower - Task API"
- `servers[0].url`: your `JCT_API_BASE_URL`
- `paths`: only `/tasks/enqueue`, `/tasks`, `/tasks/{task_id}`
- `components.securitySchemes.BearerAuth`

## 3. Create the Custom GPT

1. Go to [https://chatgpt.com/gpts/editor](https://chatgpt.com/gpts/editor)
2. Click **Create a GPT**

### Name and Description

- **Name**: DevOps Control Tower (or whatever you prefer)
- **Description**: Submit and track development tasks via JCT

### Instructions

Copy the contents of [`docs/gpt-actions-instructions.md`](gpt-actions-instructions.md) into the **Instructions** field. This tells the GPT what actions are available, what fields are required, and how to behave.

### Actions

1. Click **Create new action**
2. Under **Authentication**, select:
   - **Authentication type**: API Key
   - **Auth Type**: Bearer
   - **API Key**: paste your `JCT_API_KEY` value
3. Under **Schema**, click **Import from URL** and enter:
   ```
   https://api.yourdomain.com/openapi-gpt.json
   ```
   Alternatively, copy the JSON from that URL and paste it into the schema editor.
4. You should see three actions detected:
   - `enqueueTask` - Submit a task for execution
   - `listTasks` - List tasks with filters
   - `getTask` - Get a task by ID
5. Click **Test** on any action to verify connectivity

### Privacy Policy

If publishing the GPT publicly, you'll need a privacy policy URL. For internal/private use this can be skipped.

## 4. Test the GPT

Open a conversation with your new GPT and try:

> "List all queued tasks"

The GPT should call `listTasks` and show results. Then try:

> "Submit a code_change task for testorg/my-repo to add a healthcheck endpoint"

The GPT should confirm the details with you, then call `enqueueTask`.

## 5. Using a Tunnel for Local Development

If you want to test against a local JCT instance without deploying, use a tunnel:

```bash
# Start JCT locally
python -m devops_control_tower.main

# In another terminal, expose it via ngrok
ngrok http 8000
```

Then set `JCT_API_BASE_URL` to the ngrok HTTPS URL (e.g. `https://abc123.ngrok-free.app`) and restart JCT. Update the GPT action schema URL accordingly.

Note: ngrok URLs change each time you restart the tunnel (unless you have a paid ngrok plan with a fixed domain), so you'll need to re-import the schema in the GPT editor.

## Reference

| Resource | Location |
|----------|----------|
| GPT system prompt / instructions | [`docs/gpt-actions-instructions.md`](gpt-actions-instructions.md) |
| OpenAPI spec endpoint | `GET /openapi-gpt.json` |
| Auth dependency | `devops_control_tower/auth.py` |
| Spec builder | `devops_control_tower/gpt_openapi.py` |
| Config settings | `JCT_API_KEY`, `JCT_API_BASE_URL` in `devops_control_tower/config.py` |
| Tests | `tests/test_gpt_actions.py` |

## Troubleshooting

**GPT says "could not connect" or times out**
- Verify your server is reachable: `curl https://api.yourdomain.com/health`
- Check that port 443 with TLS is configured (ChatGPT requires HTTPS)
- If using ngrok, make sure the tunnel is running

**GPT gets 401 Unauthorized**
- Verify the API key in the GPT action settings matches `JCT_API_KEY` exactly
- Make sure auth type is set to "Bearer" (not "Basic" or "Custom")

**GPT gets 422 policy violation on enqueueTask**
- The target repo must match `JCT_ALLOWED_REPO_PREFIXES`
- `allow_network` and `allow_secrets` must be `false`
- `time_budget_seconds` must be between 30 and 86400

**Schema import fails**
- Ensure `/openapi-gpt.json` returns valid JSON: `curl -s https://api.yourdomain.com/openapi-gpt.json | python3 -m json.tool`
- ChatGPT requires the schema to be served over HTTPS
