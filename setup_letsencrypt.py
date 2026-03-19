#!/usr/bin/env python3
"""
Let's Encrypt SSL Certificate Setup Helper for QuickFileManager

This script helps you set up HTTPS with Let's Encrypt certificates.
It provides guidance and can update your config.yml automatically.

Prerequisites:
- Domain name pointing to your server
- Certbot installed (sudo apt-get install certbot)
- Server running on standard HTTP port initially
"""

import os
import sys
import yaml
import subprocess
from config import get_config, save_config

def print_banner():
    print("=" * 60)
    print("QuickFileManager - Let's Encrypt SSL Setup Helper")
    print("=" * 60)
    print()

def check_certbot():
    """Check if certbot is installed"""
    try:
        result = os.system("certbot --version > /dev/null 2>&1")
        return result == 0
    except:
        return False

def get_cert_path(domain):
    """Get the expected certificate paths for a domain inside local ssl directory"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ssl_dir = os.path.join(current_dir, "ssl")
    cert_path = os.path.join(ssl_dir, "live", domain, "fullchain.pem")
    key_path = os.path.join(ssl_dir, "live", domain, "privkey.pem")
    return cert_path, key_path

def check_certificates(domain):
    """Check if certificates exist for the domain"""
    cert_path, key_path = get_cert_path(domain)
    return os.path.exists(cert_path) and os.path.exists(key_path)

def update_config_ssl(domain, ip="0.0.0.0", port="80"):
    """Update config.yml with SSL settings"""
    config = get_config()
    
    # Use relative paths for the config file to be portable
    cert_path = f"./ssl/live/{domain}/fullchain.pem"
    key_path = f"./ssl/live/{domain}/privkey.pem"
    
    # Update server configuration
    if 'server' not in config:
        config['server'] = {}
    config['server']['domain'] = domain
    if ip:
        config['server']['host'] = ip
    if port:
        config['server']['port'] = int(port) if str(port).isdigit() else port
    
    # Update SSL configuration
    config['ssl'] = {
        'enabled': True,
        'cert_file': cert_path,
        'key_file': key_path,
        'force_https': True
    }
    
    save_config(config)
    print(f"✓ Updated config.yml with SSL settings and domain for {domain}")
    return True

def get_certbot_command(domain, ip="0.0.0.0", port="80"):
    """Generate the certbot command with local directories and binding options"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ssl_dir = os.path.join(current_dir, "ssl")
    
    cmd = [
        "certbot", "certonly", "--standalone", "-d", domain,
        "--config-dir", ssl_dir,
        "--work-dir", ssl_dir,
        "--logs-dir", ssl_dir,
        "--non-interactive", "--agree-tos", "-m", f"admin@{domain}"
    ]
    
    if ip and ip != "0.0.0.0":
        cmd.extend(["--http-01-address", ip])
    if port and port != "80":
        cmd.extend(["--http-01-port", port])
        
    return cmd

def print_instructions(domain, ip="0.0.0.0", port="80"):
    """Print step-by-step instructions"""
    print(f"Instructions for setting up Let's Encrypt SSL for {domain}:")
    print()
    print("1. STOP QuickFileManager if it's running")
    print()
    print("2. Run certbot to obtain certificates:")
    cmd = get_certbot_command(domain, ip, port)
    # Filter out non-interactive flags for manual run instructions 
    manual_cmd = [c for c in cmd if c not in ["--non-interactive", "--agree-tos", "-m", f"admin@{domain}"]]
    print(f"   sudo {' '.join(manual_cmd)}")
    print()
    print("3. If successful, certificates will be saved to:")
    cert_path, key_path = get_cert_path(domain)
    print(f"   Certificate: {cert_path}")
    print(f"   Private Key: {key_path}")
    print()
    print("4. Set environment variables or update config:")
    print("   Option A - Let this script update config.yml automatically")
    print("     Run this script again after generating the certificates.")
    print()
    print("   Option B - Update config.yml manually:")
    print("     ssl:")
    print("       enabled: true")
    print(f"       cert_file: ./ssl/live/{domain}/fullchain.pem")
    print(f"       key_file: ./ssl/live/{domain}/privkey.pem")
    print()
    print("5. Start QuickFileManager:")
    print("   sudo python app.py")
    print("   (sudo may be needed if binding to port 443; adjust config to standard ports if needed)")
    print()

def generate_ssl(domain, ip="0.0.0.0", port="80"):
    """Automatically run certbot to generate SSL certificates"""
    print(f"Generating SSL certificates for {domain}...")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ssl_dir = os.path.join(current_dir, "ssl")
    os.makedirs(ssl_dir, exist_ok=True)
    
    cmd = get_certbot_command(domain, ip, port)
    try:
        # Use sudo if we are on Unix and not root
        if os.name != 'nt' and hasattr(os, 'geteuid') and os.geteuid() != 0:
            cmd = ["sudo"] + cmd
            print("Running certbot with sudo. You may be prompted for your password.")
            
        subprocess.run(cmd, check=True)
        print("\n✓ Certificates generated successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error generating certificates. Certbot exited with code {e.returncode}")
        print("Make sure port 80 is not in use and your domain points to this server.")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False

def main():
    print_banner()
    
    # Check if certbot is available
    if not check_certbot():
        print("❌ Certbot not found!")
        print("Please install certbot first:")
        print("  Ubuntu/Debian: sudo apt-get install certbot")
        print("  CentOS/RHEL: sudo yum install certbot")
        print("  Other: https://certbot.eff.org/instructions")
        sys.exit(1)
    
    print("✓ Certbot found")
    print()
    
    # Get domain name
    domain = input("Enter your domain name (e.g., filemanager.example.com): ").strip()
    if not domain:
        print("Domain name is required!")
        sys.exit(1)
    
    print(f"\nDomain: {domain}")
    
    config = get_config()
    server_config = config.get('server', {})
    default_ip = server_config.get('host', '0.0.0.0')
    default_port = str(server_config.get('port', '80'))
    
    # Check if certificates already exist
    if check_certificates(domain):
        print(f"✓ Certificates found for {domain}")
        cert_path, key_path = get_cert_path(domain)
        print(f"  Certificate: {cert_path}")
        print(f"  Private Key: {key_path}")
        
        update_choice = input("\nUpdate config.yml with these certificate paths? (y/n): ").lower()
        if update_choice == 'y':
            update_config_ssl(domain, default_ip, default_port)
            print("\n✓ Configuration updated!")
            print("You can now start QuickFileManager with HTTPS (ensure port config is suitable):")
            print("  python app.py")
        else:
            print("\nManual configuration:")
            print(f"ssl config:\n  enabled: true\n  cert_file: ./ssl/live/{domain}/fullchain.pem\n  key_file: ./ssl/live/{domain}/privkey.pem")
    else:
        print(f"❌ No certificates found for {domain}")
        print("\nCertbot standalone configuration:")
        ip = input(f"Enter listening IP for Certbot [default: {default_ip}]: ").strip()
        if not ip:
            ip = default_ip
        
        port = input(f"Enter listening Port for Certbot [default: {default_port}]: ").strip()
        if not port:
            port = default_port
            
        print("\nWould you like to:")
        print("1. Automatically generate SSL certificates now")
        print("2. See step-by-step setup instructions")
        print("3. Exit")
        
        choice = input("Choose (1-3): ").strip()
        if choice == '1':
            print()
            if generate_ssl(domain, ip, port):
                update_choice = input("\nUpdate config.yml automatically? (y/n): ").lower()
                if update_choice == 'y':
                    update_config_ssl(domain, ip, port)
                    print("\n✓ Setup complete! You can now start QuickFileManager.")
        elif choice == '2':
            print()
            print_instructions(domain, ip, port)
            print(f"\nAfter obtaining certificates, run this script again to update config.yml")

if __name__ == "__main__":
    main() 