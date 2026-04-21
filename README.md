# llm-policy-monitor

RHCL/Kuadrant Policy Status Monitor for use in llm-playground

A containerized backend service that provides a REST API to monitor rate-limit policies from the Kuadrant Limitador service.

## Overview

This service acts as a bridge between the `llm-playground` namespace and the `kuadrant-system` namespace, exposing rate-limit counter information via a REST API.

### Key Features

- **REST API Interface**: Simple HTTP endpoints for policy monitoring
- **Container-Ready**: Multi-stage Docker build for optimized images
- **Kubernetes/OpenShift Native**: Full deployment manifests and configurations
- **High Availability**: Pod anti-affinity and horizontal pod autoscaling
- **Security**: Non-root user, read-only filesystem, network policies
- **Health Checks**: Liveness and readiness probes for Kubernetes
- **Resilient**: Automatic retries and timeout handling

## Architecture

```
┌─────────────────────┐
│   Client App        │  (llm-playground namespace)
│ (llm-playground)    │
└──────────┬──────────┘
           │ HTTP GET /v1/api/rlpstatus
           ▼
┌─────────────────────────────────────────┐
│  llm-policy-monitor Service             │ (llm-playground namespace)
│  - Deployment (2 replicas)              │
│  - Service (ClusterIP)                  │
│  - ConfigMap (Configuration)            │
│  - NetworkPolicy (Ingress/Egress)       │
└──────────┬──────────────────────────────┘
           │ HTTP GET /counters/llm%2Fmaas-route
           ▼
┌─────────────────────────────────────────┐
│  Limitador Service                      │ (kuadrant-system namespace)
│  http://limitador-limitador:8080        │
└─────────────────────────────────────────┘
```

## API Endpoints

### GET /v1/api/rlpstatus

Retrieves the current rate-limit policy status from Kuadrant Limitador.

**Request:**
```bash
curl -X GET http://llm-policy-monitor:8080/v1/api/rlpstatus
```

**Response (200 OK):**
```json
[
  {
    "limit": {
      "id": null,
      "namespace": "llm/maas-route",
      "max_value": 200000,
      "seconds": 60,
      "name": "gold",
      "conditions": ["descriptors[0][\"tokenlimit.gold__54a3a50a\"] == \"1\""],
      "variables": ["descriptors[0][\"auth.identity.userid\"]"]
    },
    "set_variables": {
      "descriptors[0][\"auth.identity.userid\"]": "user1"
    },
    "remaining": 199414,
    "expires_in_seconds": 50
  }
]
```

**Response (Empty - no limits):**
```json
[]
```

**Error Responses:**
- `503 Service Unavailable`: Limitador service is unreachable
- `504 Gateway Timeout`: Limitador service timeout
- `500 Internal Server Error`: Unexpected error

### GET /health

Health check endpoint for Kubernetes liveness probes.

**Response (200 OK):**
```json
{"status": "healthy"}
```

### GET /ready

Readiness check endpoint for Kubernetes readiness probes. Attempts to reach Limitador.

**Response (200 OK):**
```json
{"ready": true}
```

**Response (503 Service Unavailable):**
```json
{"ready": false, "error": "Connection error message"}
```

## Deployment

### Prerequisites

- OpenShift/Kubernetes cluster (v1.21+)
- Access to `llm-playground` namespace
- Access to `kuadrant-system` namespace for Limitador service
- Container registry for storing images

### Build Docker Image

```bash
# Build the image
docker build -t llm-policy-monitor:latest .

# Tag for your registry
docker tag llm-policy-monitor:latest quay.io/your-org/llm-policy-monitor:latest

# Push to registry
docker push quay.io/your-org/llm-policy-monitor:latest
```

### Deploy to OpenShift

#### 1. Update Deployment Image Reference

Edit [k8s/deployment.yaml](k8s/deployment.yaml) to use your registry:

```yaml
spec:
  template:
    spec:
      containers:
      - name: llm-policy-monitor
        image: quay.io/your-org/llm-policy-monitor:latest
```

#### 2. Apply Manifests

```bash
# Apply the deployment manifest (includes namespace, configmap, deployment, service, RBAC)
oc apply -f k8s/deployment.yaml

# Apply network policies
oc apply -f k8s/network-policy.yaml

# Apply OpenShift route and HPA
oc apply -f k8s/openshift-route.yaml
```

#### 3. Verify Deployment

```bash
# Check deployment status
oc get deployment -n llm-playground llm-policy-monitor

# Check pods
oc get pods -n llm-playground -l app=llm-policy-monitor

# Check logs
oc logs -n llm-playground -l app=llm-policy-monitor -f

# Check service
oc get svc -n llm-playground llm-policy-monitor

# Check route
oc get route -n llm-playground llm-policy-monitor
```

### Configuration

Configuration is managed via the ConfigMap `llm-policy-monitor-config` in the deployment manifest.

**Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `LIMITADOR_BASE_URL` | `http://limitador-limitador.kuadrant-system.svc.cluster.local:8080` | Limitador service URL |
| `LIMITADOR_COUNTER_PATH` | `llm%2Fmaas-route` | Endpoint path for rate limit counters |
| `PORT` | `8080` | Port to listen on |
| `DEBUG` | `False` | Enable Flask debug mode |

To modify configuration:

```bash
oc edit configmap llm-policy-monitor-config -n llm-playground
```

Then restart pods:

```bash
oc rollout restart deployment llm-policy-monitor -n llm-playground
```

## Development

### Local Development

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run application
export FLASK_ENV=development
export FLASK_APP=app.py
python app.py
```

The service will be available at `http://localhost:8080`

### Testing the API

```bash
# Test rlpstatus endpoint
curl http://localhost:8080/v1/api/rlpstatus

# Test health endpoint
curl http://localhost:8080/health

# Test readiness endpoint
curl http://localhost:8080/ready
```

### Docker Build and Test

```bash
# Build image
docker build -t llm-policy-monitor:test .

# Run container
docker run -p 8080:8080 \
  -e LIMITADOR_BASE_URL="http://host.docker.internal:8080" \
  llm-policy-monitor:test

# Test in another terminal
curl http://localhost:8080/v1/api/rlpstatus
```

## Project Structure

```
llm-policy-monitor/
├── app.py                           # Main Flask application
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Multi-stage Docker build
├── .dockerignore                    # Files to exclude from Docker image
├── .gitignore                       # Git ignore rules
├── README.md                        # This file
├── k8s/
│   ├── deployment.yaml              # Kubernetes Deployment, Service, ConfigMap, RBAC
│   ├── network-policy.yaml          # Kubernetes NetworkPolicy
│   └── openshift-route.yaml         # OpenShift Route and HPA
└── docs/
    └── API.md                       # API documentation (optional, future)
```

## Production Considerations

### Security

- ✅ Non-root user (UID 1001)
- ✅ Read-only filesystem (except /tmp)
- ✅ NetworkPolicy for ingress/egress control
- ✅ Pod security context with dropped capabilities
- ✅ RBAC for least privilege
- ✅ No hardcoded secrets (use ConfigMap and Secrets)

### Scalability

- ✅ Horizontal Pod Autoscaling (HPA) configured
- ✅ Resource requests and limits set
- ✅ Pod anti-affinity for better distribution
- ✅ Gunicorn with multiple workers

### Resilience

- ✅ Health and readiness probes
- ✅ Connection retry logic with exponential backoff
- ✅ Request timeouts
- ✅ Graceful error handling

### Observability

- ✅ Structured logging with timestamps
- ✅ Prometheus scrape annotations
- ✅ Health check endpoints

## Troubleshooting

### Pods not reaching Ready state

```bash
# Check readiness probe logs
oc logs -n llm-playground -l app=llm-policy-monitor

# Check if Limitador is reachable
oc exec -n llm-playground <pod-name> -- \
  curl -v http://limitador-limitador.kuadrant-system.svc.cluster.local:8080/counters/llm%2Fmaas-route
```

### Service not responding

1. Verify the service is running:
   ```bash
   oc get svc -n llm-playground llm-policy-monitor
   ```

2. Check for network policies blocking traffic:
   ```bash
   oc describe networkpolicy -n llm-playground
   ```

3. Review pod logs:
   ```bash
   oc logs -n llm-playground -l app=llm-policy-monitor
   ```

### Connection to Limitador fails

1. Verify Limitador is running:
   ```bash
   oc get svc -n kuadrant-system limitador-limitador
   ```

2. Test connectivity from the pod:
   ```bash
   oc exec -n llm-playground <pod-name> -- \
     curl -v http://limitador-limitador.kuadrant-system.svc.cluster.local:8080/health
   ```

3. Check NetworkPolicy allows egress to kuadrant-system:
   ```bash
   oc describe networkpolicy llm-policy-monitor -n llm-playground
   ```

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -am 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Create a Pull Request

## License

[Specify your license here]

## Support

For issues or questions, please open an issue on the repository or contact the team.
