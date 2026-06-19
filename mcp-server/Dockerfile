FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN ARCH="$(dpkg --print-architecture)" \
    && case "${ARCH}" in \
        amd64) KARCH="amd64" ;; \
        arm64) KARCH="arm64" ;; \
        *) echo "Unsupported architecture: ${ARCH}" && exit 1 ;; \
      esac \
    && curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/v1.31.0/bin/linux/${KARCH}/kubectl" \
    && chmod +x /usr/local/bin/kubectl

COPY mcp-server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-server/app ./app
COPY manifests ./manifests

EXPOSE 8000

CMD ["python", "-m", "app.mcp_server"]
