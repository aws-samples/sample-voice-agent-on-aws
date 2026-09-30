.PHONY: serve serve-frontend install-frontend lint fmt init plan apply \
       docker-build docker-push create-agent deploy-agent agent-status \
       deploy-frontend setup-env

AWS_PROFILE ?= default
AWS_REGION := us-east-1
IMAGE_NAME := voice-recipe-agent
TF_DIR := infrastructure

# --- Local dev ---

# Run the server (WebRTC signaling + BidiAgent)
serve:
	cd src && AWS_PROFILE=$(AWS_PROFILE) uv run python -m uvicorn server:app --host 0.0.0.0 --port 8080 --reload

# Run the frontend dev server
serve-frontend:
	cd frontend && npm run dev

# Install frontend dependencies
install-frontend:
	cd frontend && npm install

# Install Python dependencies
init:
	uv sync

# Lint with ruff
lint:
	uv run ruff check src/

# Format with ruff
fmt:
	uv run ruff format src/

# --- Terraform ---

plan:
	cd $(TF_DIR) && AWS_PROFILE=$(AWS_PROFILE) terraform plan -var="aws_profile=$(AWS_PROFILE)"

apply:
	cd $(TF_DIR) && AWS_PROFILE=$(AWS_PROFILE) terraform apply -var="aws_profile=$(AWS_PROFILE)"

# --- Docker ---

# Build ARM64 Docker image for AgentCore
docker-build:
	$(eval KB_ID := $(shell cd $(TF_DIR) && AWS_PROFILE=$(AWS_PROFILE) terraform output -raw knowledge_base_id 2>/dev/null || echo ""))
	docker build --platform linux/arm64 --provenance=false --build-arg BEDROCK_KB_ID=$(KB_ID) -t $(IMAGE_NAME) -f src/Dockerfile src/

# Push image to ECR
docker-push:
	$(eval ECR_URL := $(shell cd $(TF_DIR) && AWS_PROFILE=$(AWS_PROFILE) terraform output -raw ecr_repository_url))
	$(eval ACCOUNT := $(shell echo $(ECR_URL) | cut -d. -f1))
	$(eval REGISTRY := $(shell echo $(ECR_URL) | cut -d/ -f1))
	AWS_PROFILE=$(AWS_PROFILE) aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(REGISTRY)
	docker tag $(IMAGE_NAME):latest $(ECR_URL):latest
	docker push $(ECR_URL):latest

# --- AgentCore ---

# Create AgentCore runtime (first time only)
create-agent:
	$(eval ECR_URL := $(shell cd $(TF_DIR) && AWS_PROFILE=$(AWS_PROFILE) terraform output -raw ecr_repository_url))
	$(eval ROLE_ARN := $(shell cd $(TF_DIR) && AWS_PROFILE=$(AWS_PROFILE) terraform output -raw agentcore_role_arn))
	AWS_PROFILE=$(AWS_PROFILE) aws bedrock-agentcore-control create-agent-runtime \
		--agent-runtime-name voice-recipe-agent \
		--description "Family Recipe Voice Assistant" \
		--role-arn $(ROLE_ARN) \
		--network-configuration '{"networkMode":"PUBLIC"}' \
		--protocol-configuration '{"supportedProtocols":["WEBSOCKET"]}' \
		--agent-runtime-artifact '{"containerConfiguration":{"containerUri":"$(ECR_URL):latest","protocol":"WEBSOCKET"}}' \
		--region $(AWS_REGION)

# Full deploy: build, push with unique tag, update runtime
deploy-agent: docker-build docker-push
	$(eval ECR_URL := $(shell cd $(TF_DIR) && AWS_PROFILE=$(AWS_PROFILE) terraform output -raw ecr_repository_url))
	$(eval ROLE_ARN := $(shell cd $(TF_DIR) && AWS_PROFILE=$(AWS_PROFILE) terraform output -raw agentcore_role_arn))
	$(eval RUNTIME_ARN := $(shell cd $(TF_DIR) && AWS_PROFILE=$(AWS_PROFILE) terraform output -raw agent_runtime_arn 2>/dev/null || echo ""))
	$(eval IMAGE_TAG := v$(shell date +%Y%m%d%H%M%S))
	@if [ -z "$(RUNTIME_ARN)" ]; then \
		echo "Error: agent_runtime_arn not set in Terraform. Run 'make create-agent' first."; \
		exit 1; \
	fi
	docker tag $(IMAGE_NAME):latest $(ECR_URL):$(IMAGE_TAG)
	AWS_PROFILE=$(AWS_PROFILE) aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(shell echo $(ECR_URL) | cut -d/ -f1)
	docker push $(ECR_URL):$(IMAGE_TAG)
	AWS_PROFILE=$(AWS_PROFILE) aws bedrock-agentcore-control update-agent-runtime \
		--agent-runtime-id $(shell echo $(RUNTIME_ARN) | awk -F/ '{print $$NF}') \
		--role-arn $(ROLE_ARN) \
		--network-configuration '{"networkMode":"PUBLIC"}' \
		--protocol-configuration '{"serverProtocol":"HTTP"}' \
		--agent-runtime-artifact '{"containerConfiguration":{"containerUri":"$(ECR_URL):$(IMAGE_TAG)"}}' \
		--region $(AWS_REGION)

# Check runtime status
agent-status:
	$(eval RUNTIME_ARN := $(shell cd $(TF_DIR) && AWS_PROFILE=$(AWS_PROFILE) terraform output -raw agent_runtime_arn 2>/dev/null || echo ""))
	@if [ -z "$(RUNTIME_ARN)" ]; then \
		echo "agent_runtime_arn not set in Terraform."; \
		exit 1; \
	fi
	AWS_PROFILE=$(AWS_PROFILE) aws bedrock-agentcore-control get-agent-runtime \
		--agent-runtime-id $(shell echo $(RUNTIME_ARN) | awk -F/ '{print $$NF}') \
		--region $(AWS_REGION)

# --- Frontend deployment ---

# Build and deploy frontend to S3 + invalidate CloudFront cache
deploy-frontend:
	cd frontend && npm run build
	$(eval BUCKET := $(shell cd $(TF_DIR) && AWS_PROFILE=$(AWS_PROFILE) terraform output -raw frontend_bucket_id))
	$(eval DIST_ID := $(shell cd $(TF_DIR) && AWS_PROFILE=$(AWS_PROFILE) terraform output -raw cloudfront_distribution_id))
	AWS_PROFILE=$(AWS_PROFILE) aws s3 sync frontend/dist/ s3://$(BUCKET)/ --delete --region $(AWS_REGION)
	AWS_PROFILE=$(AWS_PROFILE) aws cloudfront create-invalidation --distribution-id $(DIST_ID) --paths "/*" --region $(AWS_REGION)

# --- Environment setup ---

# Generate .env files from Terraform outputs
setup-env:
	@echo "Generating frontend/.env from Terraform outputs..."
	@cd $(TF_DIR) && \
	echo "VITE_USER_POOL_ID=$$(AWS_PROFILE=$(AWS_PROFILE) terraform output -raw user_pool_id)" > ../frontend/.env && \
	echo "VITE_USER_POOL_CLIENT_ID=$$(AWS_PROFILE=$(AWS_PROFILE) terraform output -raw user_pool_client_id)" >> ../frontend/.env && \
	echo "VITE_IDENTITY_POOL_ID=$$(AWS_PROFILE=$(AWS_PROFILE) terraform output -raw identity_pool_id)" >> ../frontend/.env && \
	echo "VITE_REGION=$(AWS_REGION)" >> ../frontend/.env && \
	RUNTIME_ARN=$$(AWS_PROFILE=$(AWS_PROFILE) terraform output -raw agent_runtime_arn 2>/dev/null || echo ""); \
	if [ -n "$$RUNTIME_ARN" ]; then \
		echo "VITE_AGENT_RUNTIME_ARN=$$RUNTIME_ARN" >> ../frontend/.env; \
	fi
	@echo "Done. Frontend .env:"
	@cat frontend/.env
