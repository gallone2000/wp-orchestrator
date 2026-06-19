apiVersion: v1
kind: Service
metadata:
  name: wordpress
  namespace: __NAMESPACE__
spec:
  selector:
    app: wordpress
  ports:
    - port: __WORDPRESS_SERVICE_PORT__
      targetPort: __WORDPRESS_SERVICE_PORT__

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: wordpress
  namespace: __NAMESPACE__
spec:
  replicas: __WORDPRESS_REPLICA_COUNT__
  selector:
    matchLabels:
      app: wordpress
  template:
    metadata:
      labels:
        app: wordpress
    spec:
      containers:
        - name: wordpress
          image: "__WORDPRESS_IMAGE__"
          env:
            - name: WORDPRESS_DB_HOST
              value: "mariadb:__MARIADB_SERVICE_PORT__"
            - name: WORDPRESS_DB_USER
              value: "__WORDPRESS_DB_USER__"
            - name: WORDPRESS_DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: wordpress-secret
                  key: WORDPRESS_DB_PASSWORD
            - name: WORDPRESS_DB_NAME
              value: "__WORDPRESS_DB_NAME__"
            - name: WORDPRESS_CONFIG_EXTRA
              value: |
                define('WP_HOME', 'http://__HOST__');
                define('WP_SITEURL', 'http://__HOST__');
          ports:
            - containerPort: __WORDPRESS_SERVICE_PORT__
          volumeMounts:
            - name: wordpress-storage
              mountPath: /var/www/html/wp-content
      volumes:
        - name: wordpress-storage
          persistentVolumeClaim:
            claimName: wordpress-pvc
