# Testing Guide

## Overview

This guide covers testing strategies for the llm-policy-monitor service at different levels:
- Local development testing
- Docker container testing  
- Kubernetes cluster testing
- Integration testing

## Local Development Testing

### Prerequisites

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

```bash
# Run with default configuration
python app.py

# Run in debug mode
DEBUG=True python app.py

# Run with custom Limitador endpoint (for testing with mock)
LIMITADOR_BASE_URL=http://localhost:9090 python app.py
```

### Testing Endpoints

```bash
# Health check
curl http://localhost:8080/health

# Readiness check
curl http://localhost:8080/ready

# Main API endpoint
curl http://localhost:8080/v1/api/rlpstatus

# Pretty print JSON response
curl -s http://localhost:8080/v1/api/rlpstatus | jq .
```

## Docker Testing

### Using Docker Compose (Recommended for Local Testing)

The easiest way to test locally without needing an actual Limitador service:

```bash
# Start services (app + mock Limitador)
docker-compose up -d

# Check logs
docker-compose logs -f llm-policy-monitor

# Test the API
curl http://localhost:8080/v1/api/rlpstatus

# Stop services
docker-compose down
```

The mock Limitador service cycles through 3 response states on each request:
1. Empty array `[]`
2. Single limit object
3. Multiple limit objects

To reset the state:
```bash
curl -X POST http://localhost:9090/reset
```

### Testing with Real Limitador Service

If you have a real Limitador running on your machine:

```bash
# Build the image
docker build -t llm-policy-monitor:test .

# Run with Limitador on host
docker run -p 8080:8080 \
  -e LIMITADOR_BASE_URL="http://host.docker.internal:8080" \
  llm-policy-monitor:test

# Test
curl http://localhost:8080/v1/api/rlpstatus
```

## Kubernetes/OpenShift Testing

### Prerequisites

```bash
# Ensure you're logged into your OpenShift cluster
oc login https://your-cluster:6443

# Ensure llm-playground and kuadrant-system namespaces exist
oc create namespace llm-playground || true
oc create namespace kuadrant-system || true
```

### Deploy and Test

```bash
# Deploy the service
make deploy

# Check deployment status
make deploy-check

# View logs
make deploy-logs

# Test API from cluster
make test-api-cluster
```

### Manual Testing in Cluster

```bash
# Get pod name
POD=$(oc get pods -n llm-playground -l app=llm-policy-monitor -o jsonpath='{.items[0].metadata.name}')

# Test health endpoint
oc exec -n llm-playground $POD -- curl -s http://localhost:8080/health

# Test readiness endpoint
oc exec -n llm-playground $POD -- curl -s http://localhost:8080/ready

# Test main API endpoint
oc exec -n llm-playground $POD -- curl -s http://localhost:8080/v1/api/rlpstatus | jq .

# Check pod logs
oc logs -n llm-playground $POD -f

# Execute shell in pod
oc exec -it -n llm-playground $POD -- /bin/bash
```

### Test Connectivity to Limitador

From within a running pod:

```bash
# Get running pod
POD=$(oc get pods -n llm-playground -l app=llm-policy-monitor -o jsonpath='{.items[0].metadata.name}')

# Test if Limitador is reachable
oc exec -n llm-playground $POD -- \
  curl -v http://limitador-limitador.kuadrant-system.svc.cluster.local:8080/counters/llm%2Fmaas-route

# Test DNS resolution
oc exec -n llm-playground $POD -- \
  nslookup limitador-limitador.kuadrant-system.svc.cluster.local
```

### Test Network Policies

```bash
# Check applied network policies
oc get networkpolicies -n llm-playground

# Describe the policy
oc describe networkpolicy llm-policy-monitor -n llm-playground

# Test ingress from another pod
POD=$(oc get pods -n llm-playground -l app=llm-policy-monitor -o jsonpath='{.items[0].metadata.name}')
oc exec -n llm-playground $POD -- curl -s http://llm-policy-monitor:8080/v1/api/rlpstatus
```

## Troubleshooting Tests

### Pod is not Ready

```bash
# Check events
oc describe pod -n llm-playground <pod-name>

# View pod logs
oc logs -n llm-playground <pod-name>

# Check if readiness probe is passing
oc exec -n llm-playground <pod-name> -- \
  curl -v http://localhost:8080/ready
```

### Service is not accessible

```bash
# Check service definition
oc get svc -n llm-playground llm-policy-monitor

# Check service endpoints
oc get endpoints -n llm-playground llm-policy-monitor

# Test DNS from pod
oc exec -n llm-playground <pod-name> -- \
  nslookup llm-policy-monitor llm-playground.svc.cluster.local
```

### Connection to Limitador fails

```bash
# Check if Limitador service exists
oc get svc -n kuadrant-system limitador-limitador

# Test connectivity from our pod
oc exec -n llm-playground <pod-name> -- \
  curl -v http://limitador-limitador.kuadrant-system.svc.cluster.local:8080/health

# Check network policies
oc get networkpolicies -n llm-playground
oc get networkpolicies -n kuadrant-system
```

## Performance Testing

### Load Testing with Apache Bench

```bash
# Install ab (Apache Bench)
# macOS: brew install httpd
# Linux: apt-get install apache2-utils

# Run load test against local service
ab -n 1000 -c 10 http://localhost:8080/v1/api/rlpstatus

# Against cluster service (requires port-forward)
oc port-forward -n llm-playground svc/llm-policy-monitor 8080:8080
ab -n 1000 -c 10 http://localhost:8080/v1/api/rlpstatus
```

### Load Testing with curl in loop

```bash
# Simple loop test
for i in {1..100}; do
  curl -s http://localhost:8080/v1/api/rlpstatus > /dev/null
  echo "Request $i complete"
done
```

## Integration Testing

### Test workflow from client application

Assuming you have a client app in the same namespace:

```bash
# From client pod, test the service
oc exec -n llm-playground <client-pod> -- \
  curl -s http://llm-policy-monitor:8080/v1/api/rlpstatus
```

### Test with real client application

1. Deploy client application to the same namespace
2. Client should be able to call `http://llm-policy-monitor:8080/v1/api/rlpstatus`
3. Verify responses are correctly formatted and parseable

## Automated Testing (Future)

Consider adding unit tests:

```python
# tests/test_app.py
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json == {'status': 'healthy'}

def test_ready(client):
    response = client.get('/ready')
    assert response.status_code == 200

def test_rlpstatus(client):
    response = client.get('/v1/api/rlpstatus')
    assert response.status_code in [200, 500, 503, 504]
```

## Test Checklist

- [ ] Health endpoint returns 200
- [ ] Readiness endpoint returns 200 when Limitador is available
- [ ] Readiness endpoint returns 503 when Limitador is unavailable
- [ ] Main API endpoint returns valid JSON
- [ ] Main API endpoint handles empty responses
- [ ] Main API endpoint handles single and multiple limits
- [ ] API correctly proxies Limitador responses
- [ ] Service is discoverable via DNS in cluster
- [ ] Network policy allows ingress from same namespace
- [ ] Network policy allows egress to kuadrant-system
- [ ] Liveness probe passes consistently
- [ ] Readiness probe works correctly
- [ ] Pod autoscales under load
- [ ] Service has proper logging
