from __future__ import annotations

from pydantic import BaseModel, Field


class CreateSiteRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=30)


class SiteResponse(BaseModel):
    name: str
    namespace: str
    host: str
    message: str


class SiteStatusResponse(BaseModel):
    name: str
    namespace: str
    resources: str
    pvc: str
    ingress: str
