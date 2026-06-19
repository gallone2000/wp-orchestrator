apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: wordpress
  namespace: __NAMESPACE__
spec:
  ingressClassName: __INGRESS_CLASS_NAME__
  rules:
    - host: __HOST__
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: wordpress
                port:
                  number: __WORDPRESS_SERVICE_PORT__
