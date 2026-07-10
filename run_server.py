"""
CALIBER v3 — production launcher.
Reads PORT from environment (Replit sets this automatically).
Run: python run_server.py
"""
import os
import subprocess
import sys

port = os.environ.get("PORT", "8000")
sys.exit(subprocess.call([
    sys.executable, "-m", "uvicorn", "web.app:app",
    "--host", "0.0.0.0",
    "--port", port,
]))
