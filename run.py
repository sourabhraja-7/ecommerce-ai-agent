"""
Launcher — starts both the FastAPI server and Streamlit UI with one command.

Usage:
    python run.py

Press Ctrl+C to stop both.
"""
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable  # whichever interpreter (venv or not) launched this script

print("🚀 Starting E-Commerce Support Agent...\n")

api = subprocess.Popen(
    [PY, "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"],
    cwd=ROOT,
)
print(f"   ✅ FastAPI      http://localhost:8000/docs  (PID {api.pid})")

ui = subprocess.Popen(
    [PY, "-m", "streamlit", "run", "src/ui/streamlit_app.py",
     "--server.port", "8501", "--server.headless", "true"],
    cwd=ROOT,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
print(f"   ✅ Streamlit    http://localhost:8501  (PID {ui.pid})")

time.sleep(3)
webbrowser.open("http://localhost:8501")
print("\n✨ Both servers are running. Press Ctrl+C to stop.\n")

try:
    while api.poll() is None and ui.poll() is None:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Shutting down...")
finally:
    for p in (api, ui):
        if p.poll() is None:
            p.terminate()
    for p in (api, ui):
        p.wait()
