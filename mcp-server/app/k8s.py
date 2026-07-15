from __future__ import annotations

import re
import secrets
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from kubernetes import client
from kubernetes.client.rest import ApiException
from kubernetes.config import ConfigException, load_kube_config
from kubernetes.utils import FailToCreateError, create_from_yaml

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


def _build_config_error(settings: Settings, exc: Exception) -> RuntimeError:
    context_hint = f" with context '{settings.kube_context}'" if settings.kube_context else ""
    return RuntimeError(
        f"Unable to load Kubernetes configuration{context_hint}: {exc}"
    )


def _build_api_error(action: str, exc: ApiException) -> RuntimeError:
    detail = (exc.body or "").strip()
    if detail:
        return RuntimeError(f"{action} failed: {detail}")
    return RuntimeError(f"{action} failed (HTTP {exc.status}).")


def _build_api_client(settings: Settings) -> client.ApiClient:
    try:
        load_kube_config(context=settings.kube_context)
    except ConfigException as exc:
        raise _build_config_error(settings, exc) from exc
    return client.ApiClient()


def _apply_manifest(api_client: client.ApiClient, manifest: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as temp_file:
        temp_file.write(manifest)
        temp_path = Path(temp_file.name)
    try:
        create_from_yaml(api_client, str(temp_path), verbose=False)
    except FailToCreateError as exc:
        messages = [str(error).strip() for error in exc.api_exceptions if str(error).strip()]
        reason = "; ".join(messages) if messages else str(exc)
        raise RuntimeError(f"Failed to apply Kubernetes manifest: {reason}") from exc
    finally:
        temp_path.unlink(missing_ok=True)


def _wait_for_deployment_ready(
    apps_api: client.AppsV1Api,
    namespace: str,
    deployment_name: str,
    *,
    timeout_seconds: int = 300,
    poll_seconds: float = 2.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            deployment = apps_api.read_namespaced_deployment(deployment_name, namespace)
        except ApiException as exc:
            if exc.status == 404:
                time.sleep(poll_seconds)
                continue
            raise _build_api_error(f"Reading deployment '{deployment_name}'", exc) from exc

        desired = deployment.spec.replicas or 0
        ready = deployment.status.ready_replicas or 0
        updated = deployment.status.updated_replicas or 0
        available = deployment.status.available_replicas or 0
        generation = deployment.metadata.generation or 0
        observed = deployment.status.observed_generation or 0
        if desired > 0 and ready >= desired and updated >= desired and available >= desired and observed >= generation:
            return
        time.sleep(poll_seconds)

    raise RuntimeError(
        f"Timeout waiting for deployment '{deployment_name}' in namespace '{namespace}' to become ready."
    )


def namespace_exists(namespace: str, settings: Settings) -> bool:
    with _build_api_client(settings) as api_client:
        core_v1 = client.CoreV1Api(api_client)
        try:
            core_v1.read_namespace(namespace)
            return True
        except ApiException as exc:
            if exc.status == 404:
                return False
            raise _build_api_error(f"Reading namespace '{namespace}'", exc) from exc


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
    with _build_api_client(settings) as api_client:
        apps_v1 = client.AppsV1Api(api_client)
        for template_name in TEMPLATE_ORDER:
            template_path = settings.manifests_dir / template_name
            manifest = render_template(template_path, context)
            _apply_manifest(api_client, manifest)

        _wait_for_deployment_ready(apps_v1, spec.namespace, "mariadb")
        _wait_for_deployment_ready(apps_v1, spec.namespace, "wordpress")


def _format_pod_rows(pods: list[client.V1Pod]) -> str:
    lines = ["NAME\tREADY\tSTATUS\tRESTARTS"]
    for pod in sorted(pods, key=lambda item: item.metadata.name):
        statuses = pod.status.container_statuses or []
        ready_count = sum(1 for status in statuses if status.ready)
        total_count = len(statuses)
        restarts = sum(status.restart_count for status in statuses)
        status = pod.status.phase or "Unknown"
        lines.append(f"{pod.metadata.name}\t{ready_count}/{total_count}\t{status}\t{restarts}")
    return "\n".join(lines)


def _format_service_rows(services: list[client.V1Service]) -> str:
    lines = ["NAME\tTYPE\tCLUSTER-IP\tPORT(S)"]
    for service in sorted(services, key=lambda item: item.metadata.name):
        ports = ",".join(
            f"{port.port}/{(port.protocol or 'TCP').lower()}" for port in (service.spec.ports or [])
        )
        lines.append(
            f"{service.metadata.name}\t{service.spec.type or 'ClusterIP'}\t{service.spec.cluster_ip or '-'}\t{ports or '-'}"
        )
    return "\n".join(lines)


def _format_deployment_rows(deployments: list[client.V1Deployment]) -> str:
    lines = ["NAME\tREADY\tUP-TO-DATE\tAVAILABLE"]
    for deployment in sorted(deployments, key=lambda item: item.metadata.name):
        desired = deployment.spec.replicas or 0
        ready = deployment.status.ready_replicas or 0
        updated = deployment.status.updated_replicas or 0
        available = deployment.status.available_replicas or 0
        lines.append(f"{deployment.metadata.name}\t{ready}/{desired}\t{updated}\t{available}")
    return "\n".join(lines)


def _format_pvc_rows(pvcs: list[client.V1PersistentVolumeClaim]) -> str:
    lines = ["NAME\tSTATUS\tVOLUME\tCAPACITY\tACCESS MODES"]
    for pvc in sorted(pvcs, key=lambda item: item.metadata.name):
        capacity = (pvc.status.capacity or {}).get("storage", "-")
        modes = ",".join(pvc.status.access_modes or [])
        lines.append(
            f"{pvc.metadata.name}\t{pvc.status.phase or 'Unknown'}\t{pvc.spec.volume_name or '-'}\t{capacity}\t{modes or '-'}"
        )
    return "\n".join(lines)


def _format_ingress_rows(ingresses: list[client.V1Ingress]) -> str:
    lines = ["NAME\tCLASS\tHOSTS\tADDRESS"]
    for ingress in sorted(ingresses, key=lambda item: item.metadata.name):
        hosts = ",".join(rule.host for rule in (ingress.spec.rules or []) if rule.host)
        addresses = []
        for status in ingress.status.load_balancer.ingress or [] if ingress.status and ingress.status.load_balancer else []:
            if status.ip:
                addresses.append(status.ip)
            elif status.hostname:
                addresses.append(status.hostname)
        lines.append(
            f"{ingress.metadata.name}\t{ingress.spec.ingress_class_name or '-'}\t{hosts or '-'}\t{','.join(addresses) or '-'}"
        )
    return "\n".join(lines)


def status_site(spec: SiteSpec, settings: Settings) -> tuple[str, str, str]:
    if not namespace_exists(spec.namespace, settings):
        raise ValueError(f"Site '{spec.name}' does not exist (namespace '{spec.namespace}' not found).")

    with _build_api_client(settings) as api_client:
        core_v1 = client.CoreV1Api(api_client)
        apps_v1 = client.AppsV1Api(api_client)
        networking_v1 = client.NetworkingV1Api(api_client)
        try:
            pods = core_v1.list_namespaced_pod(spec.namespace).items
            services = core_v1.list_namespaced_service(spec.namespace).items
            deployments = apps_v1.list_namespaced_deployment(spec.namespace).items
            pvcs = core_v1.list_namespaced_persistent_volume_claim(spec.namespace).items
            ingresses = networking_v1.list_namespaced_ingress(spec.namespace).items
        except ApiException as exc:
            raise _build_api_error(f"Reading resources for namespace '{spec.namespace}'", exc) from exc

    resources = "\n\n".join(
        (
            _format_pod_rows(pods),
            _format_service_rows(services),
            _format_deployment_rows(deployments),
        )
    )
    pvc = _format_pvc_rows(pvcs)
    ingress = _format_ingress_rows(ingresses)
    return resources, pvc, ingress


def delete_site(spec: SiteSpec, settings: Settings) -> None:
    with _build_api_client(settings) as api_client:
        core_v1 = client.CoreV1Api(api_client)
        try:
            core_v1.delete_namespace(
                name=spec.namespace,
                body=client.V1DeleteOptions(propagation_policy="Foreground"),
            )
        except ApiException as exc:
            if exc.status == 404:
                return
            raise _build_api_error(f"Deleting namespace '{spec.namespace}'", exc) from exc
