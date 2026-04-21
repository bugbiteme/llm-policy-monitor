"""
Mock Limitador Service for local testing
Simulates the Kuadrant Limitador API responses
"""

from flask import Flask, jsonify
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Mock responses matching the Kuadrant Limitador API
MOCK_RESPONSES = {
    "empty": [],
    "single": [
        {
            "limit": {
                "id": None,
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
    ],
    "multiple": [
        {
            "limit": {
                "id": None,
                "namespace": "llm/maas-route",
                "max_value": 50,
                "seconds": 60,
                "name": "free",
                "conditions": ["descriptors[0][\"tokenlimit.free__0fbc686c\"] == \"1\""],
                "variables": ["descriptors[0][\"auth.identity.userid\"]"]
            },
            "set_variables": {
                "descriptors[0][\"auth.identity.userid\"]": "user1"
            },
            "remaining": 18446744073709551406,
            "expires_in_seconds": 54
        },
        {
            "limit": {
                "id": None,
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
            "expires_in_seconds": 6
        }
    ]
}

# State for cycling through responses
response_state = "empty"


@app.route('/counters/<path:counter_path>', methods=['GET'])
def get_counters(counter_path):
    """Mock Limitador counters endpoint"""
    global response_state
    
    logger.info(f"GET /counters/{counter_path} - Returning '{response_state}' response")
    
    # Cycle through responses on each call
    if response_state == "empty":
        response_state = "single"
        return jsonify(MOCK_RESPONSES["empty"])
    elif response_state == "single":
        response_state = "multiple"
        return jsonify(MOCK_RESPONSES["single"])
    else:
        response_state = "empty"
        return jsonify(MOCK_RESPONSES["multiple"])


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200


@app.route('/reset', methods=['POST'])
def reset():
    """Reset response state (useful for testing)"""
    global response_state
    response_state = "empty"
    logger.info("Response state reset to 'empty'")
    return jsonify({"message": "State reset"}), 200


if __name__ == '__main__':
    logger.info("Starting mock Limitador service on port 8080")
    app.run(host='0.0.0.0', port=8080, debug=True)
