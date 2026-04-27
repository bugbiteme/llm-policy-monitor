"""
LLM Policy Monitor - Backend Service
REST API for monitoring rate limit policies via Kuadrant Limitador
"""

import os
import logging
from typing import Any, List
from flask import Flask, jsonify
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yaml
from kubernetes import client, config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
LIMITADOR_BASE_URL = os.getenv(
    'LIMITADOR_BASE_URL',
    'http://limitador-limitador.kuadrant-system.svc.cluster.local:8080'
)
LIMITADOR_COUNTER_PATH = os.getenv(
    'LIMITADOR_COUNTER_PATH',
    'llm%2Fmaas-route'
)

LIMITADOR_CONFIGMAP_NAME = os.getenv(
    'LIMITADOR_CONFIGMAP_NAME',
    'limitador-limits-config-limitador'
)
LIMITADOR_CONFIGMAP_NAMESPACE = os.getenv(
    'LIMITADOR_CONFIGMAP_NAMESPACE',
    'kuadrant-system'
)

# Create requests session with retry strategy for resilience
def create_session() -> requests.Session:
    """Create a requests session with retry strategy."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        backoff_factor=1
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_rate_limit_status() -> tuple[Any, int]:
    """
    Call Kuadrant Limitador to get rate limit counters.
    
    Returns:
        tuple: (response_data, status_code)
    """
    try:
        session = create_session()
        url = f"{LIMITADOR_BASE_URL}/counters/{LIMITADOR_COUNTER_PATH}"
        
        logger.info(f"Fetching rate limit status from: {url}")
        response = session.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Successfully retrieved rate limit status: {len(data) if isinstance(data, list) else 1} limit(s)")
        
        return data, 200
        
    except requests.exceptions.Timeout:
        logger.error("Timeout while calling Limitador service")
        return {"error": "Timeout calling Limitador service"}, 504
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error: {str(e)}")
        return {"error": "Failed to connect to Limitador service"}, 503
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error: {str(e)}")
        return {"error": f"HTTP error from Limitador: {response.status_code}"}, response.status_code
    except ValueError as e:
        logger.error(f"Failed to parse JSON response: {str(e)}")
        return {"error": "Invalid JSON response from Limitador service"}, 502
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"error": "Internal server error"}, 500


@app.route('/v1/api/limits', methods=['GET'])
def limits() -> tuple[dict, int]:
    """Debug endpoint: reads Limitador ConfigMap and returns unique namespaces."""
    try:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        # Debug: log what we're actually using
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace") as f:
            pod_namespace = f.read().strip()
        with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
            token = f.read().strip()

        logger.info(f"Pod namespace: {pod_namespace}")
        logger.info(f"Looking for ConfigMap '{LIMITADOR_CONFIGMAP_NAME}' in '{LIMITADOR_CONFIGMAP_NAMESPACE}'")
        logger.info(f"Token (first 50 chars): {token[:50]}")

        v1 = client.CoreV1Api()
        cm = v1.read_namespaced_config_map(
            name=LIMITADOR_CONFIGMAP_NAME,
            namespace=LIMITADOR_CONFIGMAP_NAMESPACE,
        )
        limit_entries = yaml.safe_load(cm.data["limitador-config.yaml"])
        namespaces = sorted({limit["namespace"] for limit in limit_entries})
        return jsonify({"namespaces": namespaces}), 200

    except client.exceptions.ApiException as e:
        logger.error(f"K8s API error reading ConfigMap: {e}")
        logger.error(f"Status: {e.status}, Reason: {e.reason}, Body: {e.body}")
        return jsonify({"error": f"K8s API error: {e.reason}"}), e.status
    except KeyError as e:
        logger.error(f"ConfigMap missing expected key: {e}")
        return jsonify({"error": f"ConfigMap missing key: {e}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in /limits: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/v1/api/rlpstatus', methods=['GET'])
def rlpstatus() -> tuple[dict, int]:
    """
    GET endpoint for retrieving rate limit policy status.
    
    Returns the rate limit counters from Kuadrant Limitador service.
    
    Response:
        - 200: Array of rate limit objects or empty array
        - 503: Service unavailable (Limitador unreachable)
        - 504: Gateway timeout (Limitador timeout)
        - 500: Internal server error
    """
    data, status_code = get_rate_limit_status()
    return jsonify(data), status_code


@app.route('/health', methods=['GET'])
def health() -> tuple[dict, int]:
    """Health check endpoint for Kubernetes liveness/readiness probes."""
    return jsonify({"status": "healthy"}), 200


@app.route('/ready', methods=['GET'])
def ready() -> tuple[dict, int]:
    """Readiness check endpoint for Kubernetes readiness probes."""
    try:
        # Try to reach Limitador service to ensure it's ready
        session = create_session()
        url = f"{LIMITADOR_BASE_URL}/counters/{LIMITADOR_COUNTER_PATH}"
        response = session.get(url, timeout=5)
        response.raise_for_status()
        return jsonify({"ready": True}), 200
    except Exception as e:
        logger.warning(f"Readiness check failed: {str(e)}")
        return jsonify({"ready": False, "error": str(e)}), 503


@app.errorhandler(404)
def not_found(error: Any) -> tuple[dict, int]:
    """Handle 404 errors."""
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(405)
def method_not_allowed(error: Any) -> tuple[dict, int]:
    """Handle 405 errors."""
    return jsonify({"error": "Method not allowed"}), 405


@app.errorhandler(500)
def internal_error(error: Any) -> tuple[dict, int]:
    """Handle 500 errors."""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
