from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .config import load_settings
from .k8s import create_site, delete_site, make_site_spec, status_site
from .models import CreateSiteRequest, SiteResponse, SiteStatusResponse

app = FastAPI(title="wp-orchestrator-mcp", version="0.1.0")
settings = load_settings()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tools/create_site", response_model=SiteResponse)
def create_site_tool(payload: CreateSiteRequest) -> SiteResponse:
    try:
        spec = make_site_spec(payload.name, settings.base_domain)
        create_site(spec, settings)
        return SiteResponse(
            name=spec.name,
            namespace=spec.namespace,
            host=spec.host,
            message=f"Site creation requested. URL: http://{spec.host}. Check status endpoint for readiness.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/tools/status_site/{name}", response_model=SiteStatusResponse)
def status_site_tool(name: str) -> SiteStatusResponse:
    try:
        spec = make_site_spec(name, settings.base_domain)
        resources, pvc, ingress = status_site(spec, settings)
        return SiteStatusResponse(
            name=spec.name,
            namespace=spec.namespace,
            resources=resources,
            pvc=pvc,
            ingress=ingress,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/tools/delete_site/{name}", response_model=SiteResponse)
def delete_site_tool(name: str) -> SiteResponse:
    try:
        spec = make_site_spec(name, settings.base_domain)
        delete_site(spec, settings)
        return SiteResponse(
            name=spec.name,
            namespace=spec.namespace,
            host=spec.host,
            message="Namespace deletion requested.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
