# QuickFileManager

QuickFileManager is a fast-to-deploy, web-based remote file manager that allows you to host and manage files quickly on your computer through a modern, intuitive web interface. Built with Flask and featuring real-time updates via WebSocket connections, it provides a comprehensive solution for remote file management with multi-user support and activity logging.

## Features

- **Web-based Interface**: Access your files from any device with a web browser
- **Complete File Management**: Upload, download, rename, move, delete files and folders
- **Multi-user Support**: Authentication system with activity logging
- **Real-time Updates**: Live activity log and user count via WebSocket connections
- **Archive Support**: Create and extract ZIP files, with extended archive format support available
- **File Preview**: Preview images, videos, text files, and archive contents
- **Dark/Light Mode**: Toggle between dark and light themes
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Activity Monitoring**: Real-time activity logging with user tracking

## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Kinuseka/QuickFileManager.git
   cd QuickFileManager
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure the application:**
   - Copy or rename `config.yml` and modify it according to your needs
   - The default configuration should work for most setups

5. **Run the application:**
   ```bash
   python app.py
   ```

6. **Access the file manager:**
   - Open your web browser and navigate to `http://localhost:5000`
   - Use the default credentials or set up your own in the configuration

### Extended Archive Support (Optional)

For support of additional archive formats (RAR, 7Z, etc.), install the extended dependencies:

```bash
pip install -r requirements-archive.txt
```

Then run the archive support installer:

```bash
python install_archive_support.py
```

### Configuration

The application uses `config.yml` for configuration. Key settings include:

- **managed_directory**: The root directory that will be managed by the file manager
- **server**: Server binding configuration (host, port, domain)
- **authentication**: User credentials and session settings
- **ssl**: HTTPS/SSL configuration
- **security**: Security settings including CSRF protection and session timeout

### Environment Variables

You can optionally create a `.env` file for sensitive configuration:

```
FLASK_SECRET_KEY=your-secret-key-here
HOST=0.0.0.0
PORT=5000
SSL_ENABLED=false
SSL_CERT_FILE=/path/to/certificate.pem
SSL_KEY_FILE=/path/to/private.key
```

### Security Features

QuickFileManager includes basic security measures:

- **CSRF Protection**: Cross-Site Request Forgery protection for all POST requests
- **Session Management**: Configurable session timeout 
- **Domain Awareness**: Server knows its configured domain for proper redirects
- **HTTPS Support**: SSL/TLS encryption with Let's Encrypt integration

Security can be configured in `config.yml`:

```yaml
server:
  domain: "your-domain.com"
  host: "0.0.0.0"
  port: 5000

security:
  csrf_enabled: true
  session_timeout: 3600
```

### HTTPS Setup with Let's Encrypt

QuickFileManager supports HTTPS with Let's Encrypt certificates. To set up HTTPS:

1. **Install certbot** (if not already installed):
   ```bash
   # Ubuntu/Debian
   sudo apt-get install certbot
   
   # CentOS/RHEL
   sudo yum install certbot
   ```

2. **Run the SSL setup helper**:
   ```bash
   python setup_letsencrypt.py
   ```
   This interactive script will guide you through the process and can automatically update your configuration.

3. **Manual setup** (alternative):
   - Obtain certificates: `sudo certbot certonly --standalone -d yourdomain.com`
   - Update config.yml or set environment variables:
     ```yaml
     ssl:
       enabled: true
       cert_file: "/etc/letsencrypt/live/yourdomain.com/fullchain.pem"
       key_file: "/etc/letsencrypt/live/yourdomain.com/privkey.pem"
       force_https: true
     ```
   - Start with HTTPS port: `PORT=443 sudo python app.py`

4. **Set up automatic renewal**:
   ```bash
   sudo crontab -e
   # Add: 0 12 * * * /usr/bin/certbot renew --quiet
   ```

## Usage

1. **Authentication**: Log in with your configured credentials
2. **File Navigation**: Use the explorer panel to browse directories
3. **File Operations**: Upload, download, rename, move, or delete files using the toolbar
4. **Batch Operations**: Select multiple items for batch deletion or archiving
5. **File Preview**: Click on files to preview their contents
6. **Activity Monitoring**: Monitor real-time activity in the activity log panel

## API Endpoints

The application provides a RESTful API for programmatic access:

- `GET /api/files/<path>` - List directory contents
- `GET /api/file/content?path=<path>` - Get file content
- `POST /api/upload` - Upload files
- `POST /api/create/folder` - Create directories
- `POST /api/delete` - Delete files/folders
- `POST /api/rename` - Rename files/folders
- `POST /api/move` - Move files/folders
- `POST /api/zip` - Create archives
- `POST /api/unzip` - Extract archives

## Technical Stack

- **Backend**: Flask (Python web framework)
- **Real-time Communication**: Flask-SocketIO
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **File Operations**: Custom FileManager class
- **Configuration**: YAML-based configuration system
- **Authentication**: Session-based authentication with activity logging

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Developed by [Kinuseka](https://github.com/Kinuseka)

## Disclaimer

**IMPORTANT NOTICE:**

This software was developed with functionality in mind, **NOT security**. Security considerations were not a primary focus during development. Please be aware of the following:

- **No Security Focus**: This application was not designed with security as a priority. Use at your own risk.
- **Network Exposure**: Be extremely cautious when exposing this application to networks, especially the internet.
- **Authentication**: The built-in authentication is basic and should not be relied upon for protection of sensitive data.
- **File System Access**: This application provides web-based access to your file system - consider the implications carefully.
- **Testing Recommended**: Thoroughly test in a safe environment before using with important data.

This software is provided "as is" without warranty of any kind. The authors and contributors are not responsible for any data loss, unauthorized access, or other damages that may occur from the use of this software. Always maintain proper backups of your important files.
