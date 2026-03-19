import os
import sys
import subprocess
import time
from config import get_config

DEFAULT_HTTP_PORT = 5000
DEFAULT_HTTPS_PORT = 5001


def _safe_int_port(value, fallback):
    try:
        port = int(value)
        if 1 <= port <= 65535:
            return port
    except (TypeError, ValueError):
        pass
    return fallback

def main():
    config = get_config()
    server_config = config.get('server', {})

    host = os.getenv('HOST', server_config.get('host', '0.0.0.0'))
    http_port = _safe_int_port(
        os.getenv('HTTP_PORT') or os.getenv('PORT') or server_config.get('port', DEFAULT_HTTP_PORT),
        DEFAULT_HTTP_PORT
    )
    https_port = _safe_int_port(
        os.getenv('HTTPS_PORT') or os.getenv('SSL_PORT') or server_config.get('ssl_port', DEFAULT_HTTPS_PORT),
        DEFAULT_HTTPS_PORT
    )
    
    ssl_config = config.get('ssl', {})
    ssl_enabled = bool(ssl_config.get('enabled', False))
    force_https = bool(ssl_config.get('force_https', False))
    
    processes = []
    
    try:
        if ssl_enabled:
            if http_port == https_port:
                print("ERROR: HTTP and HTTPS ports must be different when SSL is enabled.")
                sys.exit(1)

            cert_file = ssl_config.get('cert_file')
            key_file = ssl_config.get('key_file')
            
            if not cert_file or not key_file or not os.path.exists(cert_file) or not os.path.exists(key_file):
                print("ERROR: SSL is enabled but certificates were not found!")
                sys.exit(1)
            
            http_target = "app:redirect_app" if force_https else "app:app"
            http_mode = "Redirector" if force_https else "Lenient (no forced HTTPS redirect)"

            print(f"Starting Gunicorn HTTP Server ({http_mode}) on {host}:{http_port}...")
            p_http = subprocess.Popen([
                "gunicorn",
                http_target,
                "--bind", f"{host}:{http_port}",
                "-k", "gevent",
                "-w", "1",
                "--worker-connections", "1000"
            ])
            processes.append(p_http)
            
            print(f"Starting Gunicorn HTTPS Server (Main) on {host}:{https_port}...")
            p_https = subprocess.Popen([
                "gunicorn",
                "app:app",
                "--bind", f"{host}:{https_port}",
                "-k", "gevent",
                "-w", "1",
                "--worker-connections", "1000",
                "--certfile", cert_file,
                "--keyfile", key_file
            ])
            processes.append(p_https)
            
        else:
            print(f"Starting Gunicorn HTTP Server on {host}:{http_port}...")
            p_http = subprocess.Popen([
                "gunicorn",
                "app:app",
                "--bind", f"{host}:{http_port}",
                "-k", "gevent",
                "-w", "1",
                "--worker-connections", "1000"
            ])
            processes.append(p_http)
            
        # Keep main thread alive waiting for subprocesses
        for p in processes:
            p.wait()
            
    except KeyboardInterrupt:
        print("\nShutting down Gunicorn servers...")
        for p in processes:
            p.terminate()
            
if __name__ == "__main__":
    # Ensure gunicorn is actually installed
    try:
        subprocess.run(["gunicorn", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: Gunicorn is not installed or not in PATH. Please run `pip install gunicorn eventlet`.")
        sys.exit(1)
        
    main()
