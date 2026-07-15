# wp-orchestrator

Deploy and manage WordPress sites on Kubernetes by chatting with an LLM.
No Helm, no shell scripts — just natural language.

## Architecture

```
User (browser)
    │
    ▼
LibreChat UI  ──►  Ollama (llama3.1:8b)
                        │
                        │  MCP tool calls
                        ▼
                   wp-mcp (FastMCP server)
                        │
                        │  Kubernetes API
                        ▼
                   Kubernetes cluster
                        │
                   ┌────┴────┐
                 wp-<name>  wp-<name2>  ...
               (namespace per site)
```

Each WordPress site lives in its own namespace (`wp-<name>`) and includes:
MariaDB + WordPress deployments, PVCs, ClusterIP services, and an Nginx Ingress.

## Project layout

```
wp-orchestrator/
├── apps/
│   └── librechat/
│       ├── librechat.yaml          # LibreChat config (Ollama + MCP wiring)
│       └── wp-tool-policy.prompt.txt  # system prompt / tool policy
├── infra/
│   └── compose/
│       ├── docker-compose.yml      # full stack: LibreChat, Ollama, wp-mcp, MongoDB, ...
│       └── .env.example            # environment template
├── manifests/                      # parameterized YAML templates (__PLACEHOLDER__)
│   ├── namespace.yaml.tpl
│   ├── secrets.yaml.tpl
│   ├── mariadb-pvc.yaml.tpl
│   ├── wordpress-pvc.yaml.tpl
│   ├── mariadb.yaml.tpl
│   ├── wordpress.yaml.tpl
│   └── ingress.yaml.tpl
└── mcp-server/
    ├── app/
    │   ├── config.py               # settings from environment
    │   ├── k8s.py                  # Kubernetes API wrappers and deploy logic
    │   ├── mcp_server.py           # FastMCP tool definitions (entrypoint)
    │   ├── main.py                 # FastAPI REST endpoints (optional direct use)
    │   └── models.py               # Pydantic request/response models
    ├── Dockerfile
    ├── requirements.txt
    └── .env.example
```

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose v2
- A running Kubernetes cluster reachable from the host (e.g. [Minikube](https://minikube.sigs.k8s.io/docs/start/))
- A valid kubeconfig mounted in `wp-mcp` (`KUBECONFIG=/root/.kube/config`) with a reachable context
- Minikube ingress addon enabled (if using Minikube):
  ```bash
  minikube addons enable ingress
  ```

## Quick start

```bash
# 1. clone and enter the project
cd infra/compose

# 2. create your local env file
cp .env.example .env
```

Edit `.env` and set at minimum:

| Variable | Description | Example |
|---|---|---|
| `HOST_KUBE_DIR` | path to your kubeconfig directory | `/home/your-user/.kube` |
| `KUBE_CONTEXT` | kubeconfig context to use | `minikube` |
| `BASE_DOMAIN` | base domain for site URLs | `192.168.49.2.nip.io` |

> **Tip:** for a local Minikube setup use `BASE_DOMAIN=$(minikube ip).nip.io` — no `/etc/hosts` edits needed.

```bash
# 3. start the full stack
docker compose up -d --build

# 4. pull the LLM model (first time only, ~5 GB)
docker exec -it wp-ollama ollama pull llama3.1:8b
```

Open LibreChat: **http://localhost:3080**

## Tool policy prompt

For best results, paste the contents of `apps/librechat/wp-tool-policy.prompt.txt`
into LibreChat system instructions or as the first message of a new conversation.

This tells the model when to call each tool and how to format responses.

## Available MCP tools

| Tool | Description |
|---|---|
| `create_wordpress_site(name)` | Deploy a new WordPress site |
| `get_wordpress_site_status(name)` | Get pod/PVC/ingress status |
| `delete_wordpress_site(name)` | Delete the site namespace and all resources |

**Site name rules:** lowercase letters, numbers, and `-` only; no leading/trailing dash; max 30 chars.

## Deployment conventions

| Resource | Pattern |
|---|---|
| Namespace | `wp-<name>` |
| Host | `<name>.<BASE_DOMAIN>` |
| MariaDB secret | `mariadb-secret` (in namespace) |
| WordPress secret | `wordpress-secret` (in namespace) |

## Environment variables reference

All variables are optional and fall back to sensible defaults.

| Variable | Default | Description |
|---|---|---|
| `HOST_KUBE_DIR` | — | **Required.** Host path mounted as `/root/.kube` in `wp-mcp` |
| `KUBE_CONTEXT` | _(current-context)_ | kubeconfig context name |
| `BASE_DOMAIN` | `wordpress.local` | Base domain for ingress hosts |
| `INGRESS_CLASS_NAME` | `nginx` | Ingress class |
| `MARIADB_IMAGE` | `mariadb:11.8.6` | MariaDB image |
| `WORDPRESS_IMAGE` | `wordpress:php8.5-apache` | WordPress image |
| `MARIADB_PVC_SIZE` | `1Gi` | MariaDB PVC size |
| `WORDPRESS_PVC_SIZE` | `1Gi` | WordPress PVC size |

## Troubleshooting

**MCP server cannot load Kubernetes config/context**
Set `KUBE_CONTEXT` in `infra/compose/.env` and restart `wp-mcp`:
```bash
docker compose up -d --force-recreate wp-mcp
```

**Site unreachable after creation**
Ensure the ingress addon is enabled and `BASE_DOMAIN` matches your cluster IP.
With Minikube:
```bash
minikube addons enable ingress
kubectl get ingress -n wp-<name>   # ADDRESS column must be populated
```

**Minikube cert errors in `wp-mcp`**
Embed certs into kubeconfig so the container can read them without external file paths:
```bash
kubectl config view --raw --flatten > ~/.kube/config
```
