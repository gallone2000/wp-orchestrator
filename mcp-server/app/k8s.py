from __future__ import annotations

import re
import secrets
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Settings

SITE_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,28}[a-z0-9])?$")
TEMPLATE_ORDER = (
    "namespace.yaml.tpl",
    "secrets.yaml.tpl",
    "mariadb-pvc.yaml.tpl",
    "wordpress-pvc.yaml.tpl",
    "mariadb.yaml.tpl",
    "wordpress.yaml.tpl",
    "ingress.yaml.tpl",
)


@dataclass(frozen=True)
class SiteSpec:
    name: str
    namespace: str
    host: str


def validate_site_name(name: str) -> str:
    normalized = name.strip().lower()
    if not SITE_NAME_RE.fullmatch(normalized):
        raise ValueError(
            "Invalid site name. Use lowercase letters, numbers, dash; no leading/trailing dash; max 30 chars."
        )
    return normalized


def make_site_spec(name: str, base_domain: str) -> SiteSpec:
    normalized_name = validate_site_name(name)
    return SiteSpec(
        name=normalized_name,
        namespace=f"wp-{normalized_name}",
        host=f"{normalized_name}.{base_domain}",
    )


def run_kubectl(args: list[str], *, stdin: str | None = None) -> str:
    return run_kubectl_with_context(args, settings=None, stdin=stdin)


def run_kubectl_with_context(args: list[str], *, settings: Settings | None, stdin: str | None = None) -> str:
    command = ["kubectl"]
    if settings and settings.kube_context:
        command.extend(["--context", settings.kube_context])
    command.extend(args)

    completed = subprocess.run(
        command,
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        error = completed.stderr.strip() or completed.stdout.strip() or "kubectl command failed"
        if "localhost:8080" in error:
            raise RuntimeError(
                "Kubernetes context is not configured. "
                "kubectl is trying localhost:8080. "
                "Set a valid current-context in kubeconfig or set KUBE_CONTEXT for wp-mcp."
            )
        raise RuntimeError(f"kubectl {' '.join(args)} failed: {error}")
    return completed.stdout.strip()


def namespace_exists(namespace: str, settings: Settings) -> bool:
    command = ["kubectl"]
    if settings.kube_context:
        command.extend(["--context", settings.kube_context])
    command.extend(["get", "namespace", namespace])
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def render_template(template_path: Path, context: dict[str, str]) -> str:
    content = template_path.read_text(encoding="utf-8")
    for key, value in context.items():
        content = content.replace(f"__{key}__", value)
    unresolved = re.findall(r"__[A-Z0-9_]+__", content)
    if unresolved:
        unresolved_str = ", ".join(sorted(set(unresolved)))
        raise ValueError(f"Unresolved placeholders in {template_path.name}: {unresolved_str}")
    return content


def build_context(spec: SiteSpec, settings: Settings) -> dict[str, str]:
    root_password = secrets.token_urlsafe(18)
    wp_db_password = root_password
    return {
        "SITE_NAME": spec.name,
        "NAMESPACE": spec.namespace,
        "HOST": spec.host,
        "MARIADB_ROOT_PASSWORD": root_password,
        "WORDPRESS_DB_PASSWORD": wp_db_password,
        "MARIADB_IMAGE": settings.mariadb_image,
        "WORDPRESS_IMAGE": settings.wordpress_image,
        "MARIADB_SERVICE_PORT": str(settings.mariadb_service_port),
        "WORDPRESS_SERVICE_PORT": str(settings.wordpress_service_port),
        "MARIADB_REPLICA_COUNT": str(settings.mariadb_replica_count),
        "WORDPRESS_REPLICA_COUNT": str(settings.wordpress_replica_count),
        "MARIADB_DATABASE": settings.mariadb_database,
        "WORDPRESS_DB_USER": settings.wordpress_db_user,
        "WORDPRESS_DB_NAME": settings.mariadb_database,
        "MARIADB_PVC_SIZE": settings.mariadb_pvc_size,
        "WORDPRESS_PVC_SIZE": settings.wordpress_pvc_size,
        "INGRESS_CLASS_NAME": settings.ingress_class_name,
    }


def create_site(spec: SiteSpec, settings: Settings) -> None:
    if namespace_exists(spec.namespace, settings):
        raise ValueError(f"Namespace '{spec.namespace}' already exists.")

    context = build_context(spec, settings)
    for template_name in TEMPLATE_ORDER:
        template_path = settings.manifests_dir / template_name
        manifest = render_template(template_path, context)
        run_kubectl_with_context(["apply", "-f", "-"], settings=settings, stdin=manifest)

    run_kubectl_with_context(["rollout", "status", "deployment/mariadb", "-n", spec.namespace], settings=settings)
    run_kubectl_with_context(["rollout", "status", "deployment/wordpress", "-n", spec.namespace], settings=settings)


def status_site(spec: SiteSpec, settings: Settings) -> tuple[str, str, str]:
    if not namespace_exists(spec.namespace, settings):
        raise ValueError(f"Site '{spec.name}' does not exist (namespace '{spec.namespace}' not found).")
    resources = run_kubectl_with_context(["get", "all", "-n", spec.namespace], settings=settings)
    pvc = run_kubectl_with_context(["get", "pvc", "-n", spec.namespace], settings=settings)
    ingress = run_kubectl_with_context(["get", "ingress", "-n", spec.namespace], settings=settings)
    return resources, pvc, ingress


def delete_site(spec: SiteSpec, settings: Settings) -> None:
    run_kubectl_with_context(["delete", "namespace", spec.namespace, "--ignore-not-found=true"], settings=settings)
