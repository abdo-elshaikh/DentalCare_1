# main.py
import subprocess
import sys
import os

def dev_server():
    """
    Starts the FastAPI development server.
    Uses `uvicorn` with hot-reload enabled.
    """
    print("🚀 Starting FastAPI server in development mode...")
    print("🔄 Hot-reload is enabled for automatic restarts on code changes")

    # Load environment variables from .env if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # Read host and port from environment variables
    host = os.getenv("API_HOST")
    port_str = os.getenv("API_PORT")

    # If not explicitly specified, try to parse from CEPHALO_API_URL
    if not host or not port_str:
        cephalo_url = os.getenv("CEPHALO_API_URL")
        if cephalo_url:
            from urllib.parse import urlparse
            try:
                parsed = urlparse(cephalo_url)
                if parsed.hostname:
                    if not host:
                        host = parsed.hostname
                        if host == 'localhost':
                            host = '127.0.0.1'
                if parsed.port and not port_str:
                    port_str = str(parsed.port)
            except Exception:
                pass

    # Safe defaults
    if not host:
        host = "127.0.0.1"
    if not port_str:
        port_str = "8000"

    # Build absolute path to the directory containing api/main.py
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # The module to run is api.main in package context
    # or "api.main" when running as a script
    cmd = [
        sys.executable, 
        "-m", 
        "uvicorn", 
        "api.main:app",
        "--reload",
        "--host", host,
        "--port", port_str,
        "--log-level", "info"
    ]

    print(f"Command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    # Automatically start the server when running this script
    dev_server()
