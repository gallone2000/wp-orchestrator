apiVersion: v1
kind: Service
metadata:
  name: mariadb
  namespace: __NAMESPACE__
spec:
  selector:
    app: mariadb
  ports:
    - port: __MARIADB_SERVICE_PORT__
      targetPort: __MARIADB_SERVICE_PORT__

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mariadb
  namespace: __NAMESPACE__
spec:
  replicas: __MARIADB_REPLICA_COUNT__
  selector:
    matchLabels:
      app: mariadb
  template:
    metadata:
      labels:
        app: mariadb
    spec:
      containers:
        - name: mariadb
          image: "__MARIADB_IMAGE__"
          env:
            - name: MARIADB_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: mariadb-secret
                  key: MARIADB_ROOT_PASSWORD
            - name: MARIADB_DATABASE
              value: "__MARIADB_DATABASE__"
          ports:
            - containerPort: __MARIADB_SERVICE_PORT__
          volumeMounts:
            - name: mariadb-storage
              mountPath: /var/lib/mysql
      volumes:
        - name: mariadb-storage
          persistentVolumeClaim:
            claimName: mariadb-pvc
