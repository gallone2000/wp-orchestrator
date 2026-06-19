apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mariadb-pvc
  namespace: __NAMESPACE__
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: __MARIADB_PVC_SIZE__
