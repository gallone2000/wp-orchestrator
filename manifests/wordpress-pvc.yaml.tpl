apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: wordpress-pvc
  namespace: __NAMESPACE__
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: __WORDPRESS_PVC_SIZE__
