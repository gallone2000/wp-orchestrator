apiVersion: v1
kind: Secret
metadata:
  name: mariadb-secret
  namespace: __NAMESPACE__
type: Opaque
stringData:
  MARIADB_ROOT_PASSWORD: "__MARIADB_ROOT_PASSWORD__"

---
apiVersion: v1
kind: Secret
metadata:
  name: wordpress-secret
  namespace: __NAMESPACE__
type: Opaque
stringData:
  WORDPRESS_DB_PASSWORD: "__WORDPRESS_DB_PASSWORD__"
