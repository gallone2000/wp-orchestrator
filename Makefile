SHELL := /bin/bash

COMPOSE_DIR := infra/compose
COMPOSE_FILE := $(COMPOSE_DIR)/docker-compose.yml
ENV_FILE := $(COMPOSE_DIR)/.env
ENV_EXAMPLE := $(COMPOSE_DIR)/.env.example

KUBE_DIR ?= $(HOME)/.kube
KUBE_CONTEXT ?= minikube
MODEL ?= llama3.1:8b

.PHONY: help bootstrap check-deps init-env set-base-domain minikube-start minikube-enable-ingress minikube-wait-ingress ensure-minikube-network compose-up compose-down compose-logs wait-mcp pull-model status k8s-ns k8s-sites k8s-site

help:
	@echo "Ordered quick start (fresh clone):"
	@echo "  1) make init-env"
	@echo "  2) make minikube-start"
	@echo "  3) make minikube-enable-ingress"
	@echo "  4) make minikube-wait-ingress"
	@echo "  5) make set-base-domain"
	@echo "  6) make compose-up"
	@echo "  7) make pull-model"
	@echo "  8) make status"
	@echo ""
	@echo "One-shot alternative:"
	@echo "  make bootstrap"
	@echo ""
	@echo "Cluster shortcuts:"
	@echo "  make k8s-ns"
	@echo "  make k8s-sites"
	@echo "  make k8s-site SITE=<name>"

bootstrap: check-deps init-env minikube-start minikube-enable-ingress minikube-wait-ingress set-base-domain ensure-minikube-network compose-up wait-mcp pull-model status

check-deps:
	@command -v docker >/dev/null || { echo "docker is required"; exit 1; }
	@command -v minikube >/dev/null || { echo "minikube is required"; exit 1; }
	@command -v kubectl >/dev/null || { echo "kubectl is required"; exit 1; }
	@command -v curl >/dev/null || { echo "curl is required"; exit 1; }

init-env:
	@[ -f "$(ENV_FILE)" ] || cp "$(ENV_EXAMPLE)" "$(ENV_FILE)"
	@if grep -q '^HOST_KUBE_DIR=' "$(ENV_FILE)"; then \
		sed -i "s#^HOST_KUBE_DIR=.*#HOST_KUBE_DIR=$(KUBE_DIR)#" "$(ENV_FILE)"; \
	else \
		echo "HOST_KUBE_DIR=$(KUBE_DIR)" >> "$(ENV_FILE)"; \
	fi
	@if grep -q '^KUBE_CONTEXT=' "$(ENV_FILE)"; then \
		sed -i "s#^KUBE_CONTEXT=.*#KUBE_CONTEXT=$(KUBE_CONTEXT)#" "$(ENV_FILE)"; \
	else \
		echo "KUBE_CONTEXT=$(KUBE_CONTEXT)" >> "$(ENV_FILE)"; \
	fi
	@echo "Prepared $(ENV_FILE)"

minikube-start:
	@minikube start

minikube-enable-ingress:
	@minikube addons enable ingress

minikube-wait-ingress:
	@kubectl --context "$(KUBE_CONTEXT)" wait --namespace ingress-nginx \
		--for=condition=ready pod \
		--selector=app.kubernetes.io/component=controller \
		--timeout=240s

set-base-domain:
	@[ -f "$(ENV_FILE)" ] || $(MAKE) init-env
	@MINIKUBE_IP="$$(minikube ip)"; \
	[ -n "$$MINIKUBE_IP" ] || { echo "minikube ip unavailable"; exit 1; }; \
	if grep -q '^BASE_DOMAIN=' "$(ENV_FILE)"; then \
		sed -i "s#^BASE_DOMAIN=.*#BASE_DOMAIN=$$MINIKUBE_IP.nip.io#" "$(ENV_FILE)"; \
	else \
		echo "BASE_DOMAIN=$$MINIKUBE_IP.nip.io" >> "$(ENV_FILE)"; \
	fi; \
	echo "BASE_DOMAIN set to $$MINIKUBE_IP.nip.io"

ensure-minikube-network:
	@docker network inspect minikube >/dev/null 2>&1 || { \
		echo "Docker network 'minikube' not found."; \
		echo "Start Minikube first: make minikube-start"; \
		exit 1; \
	}

compose-up:
	@docker compose -f "$(COMPOSE_FILE)" up -d --build

wait-mcp:
	@for i in {1..30}; do \
		if curl -fsS http://localhost:8000/health >/dev/null; then \
			echo "wp-mcp is healthy"; \
			exit 0; \
		fi; \
		sleep 2; \
	done; \
	echo "wp-mcp health endpoint not ready in time"; \
	exit 1

pull-model:
	@docker exec -i wp-ollama ollama pull "$(MODEL)"

status:
	@echo "Minikube:"
	@minikube status
	@echo ""
	@echo "Docker services:"
	@docker compose -f "$(COMPOSE_FILE)" ps
	@echo ""
	@echo "MCP health:"
	@curl -fsS http://localhost:8000/health
	@echo ""
	@echo "LibreChat URL: http://localhost:3080"

compose-logs:
	@docker compose -f "$(COMPOSE_FILE)" logs -f --tail=100

compose-down:
	@docker compose -f "$(COMPOSE_FILE)" down

k8s-ns:
	@kubectl --context "$(KUBE_CONTEXT)" get ns

k8s-sites:
	@kubectl --context "$(KUBE_CONTEXT)" get ns | grep '^wp-' || true

k8s-site:
	@[ -n "$(SITE)" ] || { echo "Usage: make k8s-site SITE=<name>"; exit 1; }
	@kubectl --context "$(KUBE_CONTEXT)" get all,pvc,ingress -n "wp-$(SITE)"
