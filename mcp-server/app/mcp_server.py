from __future__ import annotations

import os

from fastmcp import FastMCP

from .config import load_settings
from .k8s import create_site, delete_site, make_site_spec, status_site

mcp = FastMCP("wp-orchestrator-mcp")
settings = load_settings()


@mcp.tool
def create_wordpress_site(name: str) -> dict:
    """
    Create a new WordPress site in Kubernetes.

    Use this tool when the user asks to create or deploy a WordPress site/blog.
    """
    spec = make_site_spec(name, settings.base_domain)
    create_site(spec, settings)
    return {
        "name": spec.name,
        "namespace": spec.namespace,
        "host": spec.host,
        "url": f"http://{spec.host}",
        "message": "Site created successfully.",
    }


@mcp.tool
def get_wordpress_site_status(name: str) -> dict:
    """
    Get Kubernetes status for a WordPress site.

    Use this tool when the user asks for health/status/troubleshooting of a site.
    """
    spec = make_site_spec(name, settings.base_domain)
    resources, pvc, ingress = status_site(spec, settings)
    return {
        "name": spec.name,
        "namespace": spec.namespace,
        "host": spec.host,
        "resources": resources,
        "pvc": pvc,
        "ingress": ingress,
    }


@mcp.tool
def delete_wordpress_site(name: str) -> dict:
    """
    Delete a WordPress site by deleting its namespace.

    Use this tool when the user explicitly asks to remove/delete a site.
    """
    spec = make_site_spec(name, settings.base_domain)
    delete_site(spec, settings)
    return {
        "name": spec.name,
        "namespace": spec.namespace,
        "host": spec.host,
        "message": "Namespace deletion requested.",
    }


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "http").strip().lower()
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))

    if transport == "http":
        mcp.run(transport="http", host=host, port=port)
        return

    if transport == "sse":
        mcp.run(transport="sse", host=host, port=port)
        return

    mcp.run()


if __name__ == "__main__":
    main()
