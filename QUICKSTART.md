# Quick Start Guide

Get the llm-policy-monitor service up and running in minutes.

## 5-Minute Local Setup

### Option 1: Python Virtual Environment (Fastest)

```bash
# Clone or navigate to the project
cd llm-policy-monitor

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py

# In another terminal, test it
curl http://localhost:8080/health
```

The service will respond with an error for `/v1/api/rlpstatus` since there's no real Limitador, but the health endpoint works.

### Option 2: Docker Compose (With Mock Limitador)

```bash
# Start services with mock Limitador
docker-compose up -d

# Wait a few seconds for services to start
sleep 5

# Test the API
curl http://localhost:8080/v1/api/rlpstatus

# View logs
docker-compose logs -f llm-policy-monitor

# Stop when done
docker-compose down
```

This includes a mock Limitador service that responds with test data.

## Development Workflow

### Using Make Commands

```bash
# Set up dev environment
make setup

# Run locally
make run-local

# Test API
make test-api-local

# Format code
make format

# Clean up
make clean
```

### Common Development Tasks

```bash
# Edit code
vim app.py

# Test changes
curl http://localhost:8080/v1/api/rlpstatus

# View application logs
# (Check terminal where you ran `python app.py`)
```

## Building and Pushing Docker Image

```bash
# Build image
make docker-build

# Run container
make docker-run

# Tag and push to registry
export REGISTRY=quay.io/your-org
make docker-push
```

## Deploying to OpenShift

### Prerequisites

```bash
# Login to OpenShift
oc login https://your-cluster:6443

# Update the image URL in k8s/deployment.yaml
# Change: image: llm-policy-monitor:latest
# To: image: quay.io/your-org/llm-policy-monitor:latest
```

### Deploy

```bash
# Deploy all resources
make deploy

# Check deployment status
make deploy-check

# View logs
make deploy-logs

# Test API in cluster
make test-api-cluster
```

## What's Running

Once deployed, you have:

- **Service**: `llm-policy-monitor` in namespace `llm-playground`
- **Endpoint**: `http://llm-policy-monitor.llm-playground.svc.cluster.local:8080`
- **API**: `GET /v1/api/rlpstatus` - returns Kuadrant rate limit status
- **Health**: `GET /health` - liveness check
- **Ready**: `GET /ready` - readiness check (tests Limitador connectivity)

## API Usage Examples

### From Local Machine

```bash
# Basic request
curl http://localhost:8080/v1/api/rlpstatus

# Pretty print
curl -s http://localhost:8080/v1/api/rlpstatus | jq .

# With headers
curl -v http://localhost:8080/v1/api/rlpstatus
```

### From Within Cluster

```bash
# From client pod to service
curl http://llm-policy-monitor:8080/v1/api/rlpstatus

# Using full DNS name
curl http://llm-policy-monitor.llm-playground.svc.cluster.local:8080/v1/api/rlpstatus
```

### From External Client

```bash
# Get the route
oc get route -n llm-playground llm-policy-monitor

# Use the host from the route
curl https://llm-policy-monitor.apps.example.com/v1/api/rlpstatus
```

## Expected Responses

### Successful Response

```json
[
  {
    "limit": {
      "namespace": "llm/maas-route",
      "name": "gold",
      "max_value": 200000,
      ...
    },
    "remaining": 199414,
    "expires_in_seconds": 50
  }
]
```

### Empty Response (No Active Limits)

```json
[]
```

### Error: Service Unavailable

```
Status: 503
Body: {"error": "Failed to connect to Limitador service"}
```

## Configuration

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` for local testing:

```
LIMITADOR_BASE_URL=http://localhost:9090
LIMITADOR_COUNTER_PATH=llm%2Fmaas-route
DEBUG=True
PORT=8080
```

## Next Steps

1. **Read the full README** for in-depth documentation
2. **Check TESTING.md** for comprehensive testing guide
3. **Review app.py** to understand the implementation
4. **Explore k8s/** for Kubernetes manifests
5. **Try the Makefile** - all available commands are documented

## Troubleshooting

### "Connection refused" on /v1/api/rlpstatus

This is normal in development without a real Limitador service. Use docker-compose with the mock service:

```bash
docker-compose up -d
make test-api-local
```

### Port 8080 already in use

```bash
# Find process using port
lsof -i :8080

# Kill it
kill -9 <PID>

# Or use a different port
PORT=8081 python app.py
```

### Import errors

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Deployment fails on OpenShift

```bash
# Check pod status
oc get pods -n llm-playground

# View error details
oc describe pod -n llm-playground <pod-name>

# Check logs
oc logs -n llm-playground <pod-name>

# Verify image can be pulled
# Edit deployment.yaml to use correct registry URL
```

## Getting Help

- See **TESTING.md** for detailed testing procedures
- Check **README.md** for architecture and deployment details
- Review **app.py** source code for implementation details
- Check pod logs: `oc logs -n llm-playground -l app=llm-policy-monitor -f`
