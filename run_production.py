import os
import sys
import subprocess
import time
from config import get_config

def main():
    config = get_config()
    server_config = config.get('server', {})
    
    host = os.getenv('HOST', server_config.get('host', '0.0.0.0'))
    port = str(os.getenv('PORT', server_config.get('port', 5000)))
    ssl_port = str(os.getenv('SSL_PORT', server_config.get('ssl_port', 5001)))
    
    ssl_config = config.get('ssl', {})
    ssl_enabled = ssl_config.get('enabled', False)
    
    processes = []
    
    try:
        if ssl_enabled:
            cert_file = ssl_config.get('cert_file')
            key_file = ssl_config.get('key_file')
            
            if not cert_file or not key_file or not os.path.exists(cert_file) or not os.path.exists(key_file):
                print("ERROR: SSL is enabled but certificates were not found!")
                sys.exit(1)
            
            print(f"Starting Gunicorn HTTP Server (Redirector) on {host}:{port}...")
            p_http = subprocess.Popen([
                "gunicorn",
                "app:redirect_app",
                "--bind", f"{host}:{port}",
                "-k", "gevent",
                "-w", "1",
                "--worker-connections", "1000"
            ])
            processes.append(p_http)
            
            print(f"Starting Gunicorn HTTPS Server (Main) on {host}:{ssl_port}...")
            p_https = subprocess.Popen([
                "gunicorn",
                "app:app",
                "--bind", f"{host}:{ssl_port}",
                "-k", "gevent",
                "-w", "1",
                "--worker-connections", "1000",
                "--certfile", cert_file,
                "--keyfile", key_file
            ])
            processes.append(p_https)
            
        else:
            print(f"Starting Gunicorn HTTP Server on {host}:{port}...")
            p_http = subprocess.Popen([
                "gunicorn",
                "app:app",
                "--bind", f"{host}:{port}",
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
