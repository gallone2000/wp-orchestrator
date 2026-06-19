from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    manifests_dir: Path
    base_domain: str
    ingress_class_name: str
    mariadb_image: str
    wordpress_image: str
    mariadb_service_port: int
    wordpress_service_port: int
    mariadb_replica_count: int
    wordpress_replica_count: int
    mariadb_database: str
    wordpress_db_user: str
    mariadb_pvc_size: str
    wordpress_pvc_size: str
    kube_context: str | None


def load_settings() -> Settings:
    current_dir = Path(__file__).resolve().parent
    candidate_dirs = (
        current_dir.parent / "manifests",
        current_dir.parent.parent / "manifests",
    )
    default_manifests_dir = next((path for path in candidate_dirs if path.exists()), candidate_dirs[0])
    manifests_dir = Path(os.getenv("MANIFESTS_DIR", str(default_manifests_dir))).resolve()
    return Settings(
        manifests_dir=manifests_dir,
        base_domain=os.getenv("BASE_DOMAIN", "wordpress.local"),
        ingress_class_name=os.getenv("INGRESS_CLASS_NAME", "nginx"),
        mariadb_image=os.getenv("MARIADB_IMAGE", "mariadb:11.8.6"),
        wordpress_image=os.getenv("WORDPRESS_IMAGE", "wordpress:php8.5-apache"),
        mariadb_service_port=int(os.getenv("MARIADB_SERVICE_PORT", "3306")),
        wordpress_service_port=int(os.getenv("WORDPRESS_SERVICE_PORT", "80")),
        mariadb_replica_count=int(os.getenv("MARIADB_REPLICA_COUNT", "1")),
        wordpress_replica_count=int(os.getenv("WORDPRESS_REPLICA_COUNT", "1")),
        mariadb_database=os.getenv("MARIADB_DATABASE", "wordpress"),
        wordpress_db_user=os.getenv("WORDPRESS_DB_USER", "root"),
        mariadb_pvc_size=os.getenv("MARIADB_PVC_SIZE", "1Gi"),
        wordpress_pvc_size=os.getenv("WORDPRESS_PVC_SIZE", "1Gi"),
        kube_context=(os.getenv("KUBE_CONTEXT", "").strip() or None),
    )
