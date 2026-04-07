"""Pytest bootstrap configuration.

Ensure mandatory environment variables are set before test collection
and module imports that depend on application settings.
"""

import os

# Mandatory secret key for settings validation
os.environ.setdefault("SECRET_KEY", "test-secret-key")
