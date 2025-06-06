#!/usr/bin/env python3
"""
Optional Archive Support Installer for File Manager

This script helps install additional libraries for extended archive format support.
"""

import subprocess
import sys
import platform
import os

def run_command(command):
    """Run a command and return success status."""
    try:
        subprocess.run(command, check=True, shell=True)
        return True
    except subprocess.CalledProcessError:
        return False

def install_package(package_name):
    """Install a Python package using pip."""
    print(f"Installing {package_name}...")
    return run_command(f"{sys.executable} -m pip install {package_name}")

def check_unrar():
    """Check if unrar utility is available (needed for RAR support)."""
    try:
        subprocess.run(["unrar"], capture_output=True, check=False)
        return True
    except FileNotFoundError:
        return False

def print_platform_instructions():
    """Print platform-specific installation instructions for unrar."""
    system = platform.system().lower()
    
    print("\n" + "="*60)
    print("PLATFORM-SPECIFIC INSTALLATION INSTRUCTIONS")
    print("="*60)
    
    if system == "windows":
        print("Windows:")
        print("1. Download WinRAR from: https://www.win-rar.com/download.html")
        print("2. Install WinRAR (includes unrar.exe)")
        print("3. Add WinRAR installation directory to your PATH")
        print("   (Usually: C:\\Program Files\\WinRAR\\)")
        
    elif system == "darwin":  # macOS
        print("macOS:")
        print("Option 1 - Using Homebrew:")
        print("  brew install unrar")
        print("")
        print("Option 2 - Using MacPorts:")
        print("  sudo port install unrar")
        
    elif system == "linux":
        print("Linux:")
        print("Ubuntu/Debian:")
        print("  sudo apt-get install unrar")
        print("")
        print("CentOS/RHEL/Fedora:")
        print("  sudo yum install unrar")
        print("  # or for newer versions:")
        print("  sudo dnf install unrar")
        print("")
        print("Arch Linux:")
        print("  sudo pacman -S unrar")
        
    else:
        print(f"Unknown platform: {system}")
        print("Please install 'unrar' utility using your system's package manager.")

def main():
    print("File Manager - Optional Archive Support Installer")
    print("="*50)
    print("\nThis will install additional libraries for archive format support:")
    print("• rarfile - for RAR archive support")
    print("• py7zr - for 7Z archive support")
    print("\nBuilt-in support (no installation needed):")
    print("• ZIP, TAR, GZ, BZ2, XZ archives")
    
    # Ask for confirmation
    response = input("\nDo you want to proceed? (y/N): ").strip().lower()
    if response not in ['y', 'yes']:
        print("Installation cancelled.")
        return
    
    print("\n" + "-"*50)
    print("INSTALLING PYTHON PACKAGES")
    print("-"*50)
    
    # Install py7zr (pure Python, should work everywhere)
    success_7z = install_package("py7zr>=0.20.0")
    if success_7z:
        print("✓ py7zr installed successfully - 7Z support enabled")
    else:
        print("✗ Failed to install py7zr - 7Z support not available")
    
    # Install rarfile
    success_rar = install_package("rarfile>=4.0")
    if success_rar:
        print("✓ rarfile installed successfully")
        
        # Check if unrar utility is available
        if check_unrar():
            print("✓ unrar utility found - RAR support fully enabled")
        else:
            print("⚠ unrar utility not found - RAR support requires additional setup")
            print_platform_instructions()
    else:
        print("✗ Failed to install rarfile - RAR support not available")
    
    print("\n" + "="*50)
    print("INSTALLATION SUMMARY")
    print("="*50)
    
    print("Archive Format Support Status:")
    print("• ZIP files: ✓ Built-in support")
    print("• TAR/GZ/BZ2/XZ files: ✓ Built-in support")
    print(f"• 7Z files: {'✓ Enabled' if success_7z else '✗ Failed'}")
    
    if success_rar:
        if check_unrar():
            print("• RAR files: ✓ Enabled")
        else:
            print("• RAR files: ⚠ Partially enabled (needs unrar utility)")
    else:
        print("• RAR files: ✗ Failed")
    
    print("\nRestart your File Manager application to use the new archive support.")
    
    if not check_unrar() and success_rar:
        print("\nNote: To complete RAR support, install the 'unrar' utility for your platform.")

if __name__ == "__main__":
    main()