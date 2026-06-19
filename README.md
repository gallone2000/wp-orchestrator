# wp-orchestrator

MVP to create WordPress sites on Kubernetes via chatbot, without Helm.

## Project layout

- `manifests/`: parameterized YAML templates using `__PLACEHOLDER__` tokens
- `mcp-server/`: FastAPI server exposing tool-style endpoints

## API tools

- `POST /tools/create_site`
  ```json
  { "name": "demo" }
  ```
- `GET /tools/status_site/{name}`
- `DELETE /tools/delete_site/{name}`

Valid site name: lowercase letters, numbers, and `-`, up to 30 chars.

## Quick start

```bash
cd mcp-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

OpenAPI docs: `http://localhost:8000/docs`

## LibreChat + Llama + MCP quick start

```bash
cd infra/compose
cp .env.example .env
# edit .env and set HOST_KUBE_DIR to your local kubeconfig dir (usually ~/.kube)
# if your kubeconfig has no current-context, set KUBE_CONTEXT explicitly
docker compose up -d --build
docker exec -it wp-ollama ollama pull llama3.1:8b
```

LibreChat UI: `http://localhost:3080`

### Tool policy prompt (recommended)

Use the policy file:

`apps/librechat/wp-tool-policy.prompt.txt`

Paste it into your LibreChat system instructions / agent instructions.
If your current UI does not expose system instructions, paste it as the first message in a new conversation.

## Runtime requirements

- `kubectl` available in PATH
- valid kubeconfig/context on the host running the server

If `kubectl` inside `wp-mcp` falls back to `localhost:8080`, your kubeconfig has no active context.
Set it in `infra/compose/.env`, for example:

```bash
KUBE_CONTEXT=<your-context-name>
```

## Deployment conventions

- namespace: `wp-<name>`
- host: `<name>.<BASE_DOMAIN>`
