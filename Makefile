.PHONY: help build run test clean docker-build docker-run docker-push deploy deploy-localrun-local format lint

# Variables
IMAGE_NAME ?= llm-policy-monitor
IMAGE_TAG ?= latest
REGISTRY ?= quay.io/your-org
FULL_IMAGE ?= $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
PYTHON ?= python3
PIP ?= pip3
VENV_DIR ?= venv

help: ## Show this help message
	@echo "llm-policy-monitor - Development Tasks"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development tasks
setup: ## Set up development environment
	$(PYTHON) -m venv $(VENV_DIR)
	. $(VENV_DIR)/bin/activate && $(PIP) install -r requirements.txt

run-local: ## Run application locally
	$(PYTHON) app.py

format: ## Format code with black (if installed)
	$(PYTHON) -m black app.py --line-length 100 || echo "black not installed, skipping"

lint: ## Lint code with flake8 (if installed)
	$(PYTHON) -m flake8 app.py || echo "flake8 not installed, skipping"

clean: ## Clean up Python cache and temporary files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".pytest_cache" -delete
	rm -rf $(VENV_DIR)
	rm -rf .coverage htmlcov .pytest_cache

# Docker tasks
docker-build: ## Build Docker image
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

docker-tag: docker-build ## Tag image for registry
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(FULL_IMAGE)

docker-run: docker-build ## Run Docker container locally
	docker run -p 8080:8080 \
		-e LIMITADOR_BASE_URL="http://host.docker.internal:8080" \
		$(IMAGE_NAME):$(IMAGE_TAG)

docker-push: docker-tag ## Push image to registry
	docker push $(FULL_IMAGE)

docker-clean: ## Clean up Docker images
	docker rmi $(IMAGE_NAME):$(IMAGE_TAG) || true
	docker rmi $(FULL_IMAGE) || true

# Kubernetes/OpenShift tasks
deploy: ## Deploy to OpenShift cluster
	@echo "Deploying to llm-playground namespace..."
	oc apply -f k8s/deployment.yaml
	oc apply -f k8s/network-policy.yaml
	oc apply -f k8s/openshift-route.yaml
	@echo "Deployment complete. Checking status..."
	oc get deployment -n llm-playground llm-policy-monitor

deploy-check: ## Check deployment status
	@echo "Deployment Status:"
	oc get deployment -n llm-playground llm-policy-monitor
	@echo ""
	@echo "Pod Status:"
	oc get pods -n llm-playground -l app=llm-policy-monitor
	@echo ""
	@echo "Service Status:"
	oc get svc -n llm-playground llm-policy-monitor

deploy-logs: ## Show deployment logs
	oc logs -n llm-playground -l app=llm-policy-monitor -f

deploy-clean: ## Remove deployment from OpenShift
	oc delete -f k8s/deployment.yaml
	oc delete -f k8s/network-policy.yaml
	oc delete -f k8s/openshift-route.yaml

# Testing tasks
test-api-local: ## Test API locally (requires app running on localhost:8080)
	@echo "Testing /health endpoint..."
	curl -s http://localhost:8080/health | python3 -m json.tool
	@echo ""
	@echo "Testing /ready endpoint..."
	curl -s http://localhost:8080/ready | python3 -m json.tool
	@echo ""
	@echo "Testing /v1/api/rlpstatus endpoint..."
	curl -s http://localhost:8080/v1/api/rlpstatus | python3 -m json.tool

test-api-cluster: ## Test API in cluster (requires oc login)
	@POD=$$(oc get pods -n llm-playground -l app=llm-policy-monitor -o jsonpath='{.items[0].metadata.name}'); \
	echo "Testing with pod: $$POD"; \
	echo ""; \
	echo "Health check:"; \
	oc exec -n llm-playground $$POD -- curl -s http://localhost:8080/health | python3 -m json.tool; \
	echo ""; \
	echo "Readiness check:"; \
	oc exec -n llm-playground $$POD -- curl -s http://localhost:8080/ready | python3 -m json.tool; \
	echo ""; \
	echo "RLP Status:"; \
	oc exec -n llm-playground $$POD -- curl -s http://localhost:8080/v1/api/rlpstatus | python3 -m json.tool

# All-in-one tasks
build-and-push: format lint docker-push ## Build, format, lint, and push image
	@echo "✓ Build, format, lint, and push complete"

.PHONY: help setup run-local format lint clean docker-build docker-tag docker-run docker-push docker-clean deploy deploy-check deploy-logs deploy-clean test-api-local test-api-cluster build-and-push
