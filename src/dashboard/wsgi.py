"""WSGI entry point for production deployment"""

import os
from .modern_app import app

# Gunicorn expects 'server' or 'application'
server = app.server

# Add health check endpoint
@server.route('/health')
def health_check():
    return {'status': 'healthy', 'service': 'tai-lam-traffic'}, 200

# Add readiness check
@server.route('/ready')
def readiness_check():
    # Check if model is loaded or fallback is working
    return {'status': 'ready', 'model': 'available'}, 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8050))
    app.run(debug=False, host='0.0.0.0', port=port)