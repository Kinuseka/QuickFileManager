from functools import wraps
from flask import session, redirect, url_for, request, jsonify, g
from config import get_config, save_config
import datetime
import json # Added for JSON logging
import os   # Added for path check
import hashlib # For generating browser identity

LOG_FILE = "logs.json"
MAX_LOG_ENTRIES = 1000 # Max number of log entries to keep
MAX_BROWSER_HISTORY = 5 # Maximum number of browser entries to keep per user

# --- JSON Log Handling Functions ---
def read_logs():
    """Reads all logs from the JSON log file."""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            logs = json.load(f)
            return logs
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading log file '{LOG_FILE}': {e}")
        return [] # Return empty list on error or if file is corrupted/empty

def write_logs(logs_data):
    """Writes logs data to the JSON log file."""
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs_data, f, indent=4)
    except IOError as e:
        print(f"Error writing to log file '{LOG_FILE}': {e}")

# --- Browser Fingerprinting ---
def generate_browser_fingerprint():
    """Generate a simple browser fingerprint based on request data."""
    user_agent = request.headers.get('User-Agent', '')
    ip_address = request.remote_addr
    accept_language = request.headers.get('Accept-Language', '')
    
    # Create a unique identifier from these components
    fingerprint_data = f"{user_agent}|{ip_address}|{accept_language}"
    return hashlib.md5(fingerprint_data.encode()).hexdigest()

def get_browser_data():
    """Get current browser data for tracking."""
    now = datetime.datetime.now().isoformat()
    return {
        "ip_address": request.remote_addr,
        "user_agent": request.headers.get('User-Agent', 'Unknown'),
        "browser_identity": generate_browser_fingerprint(),
        "session_id": request.cookies.get('session', ''),
        "first_login": now,
        "last_login": now
    }

# --- Authentication and User Management ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify(error="Unauthorized", message="User not logged in."), 401
            return redirect(url_for('login', next=request.url))
        
        # Populate g.user with current user information
        g.user = get_current_user_info()
        if g.user is None:
            # Session exists but user info is missing - invalid session
            session.clear()
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify(error="Unauthorized", message="Invalid session."), 401
            return redirect(url_for('login', next=request.url))
            
        return f(*args, **kwargs)
    return decorated_function

def handle_login(username, password):
    """Handles user login with browser tracking."""
    config = get_config()
    if password == config.get("app_password"):
        # Store username in session
        session['username'] = username
        
        # Ensure users dictionary exists
        if 'users' not in config or config['users'] is None:
            config['users'] = {}
        
        # Get or create user entry
        if username not in config['users']:
            config['users'][username] = {
                "browsers": []
            }
        
        # Get current browser data
        current_browser = get_browser_data()
        browser_id = current_browser["browser_identity"]
        
        # Check if this browser is already in the list
        browser_found = False
        for browser in config['users'][username].get("browsers", []):
            if browser["browser_identity"] == browser_id:
                # Update last login time
                browser["last_login"] = current_browser["last_login"]
                browser["ip_address"] = current_browser["ip_address"]  # Update IP in case it changed
                browser["session_id"] = current_browser["session_id"]  # Update session ID
                browser_found = True
                break
        
        # If browser not found, add it to the list
        if not browser_found:
            browsers = config['users'][username].get("browsers", [])
            browsers.append(current_browser)
            
            # Keep only the most recent MAX_BROWSER_HISTORY browsers
            if len(browsers) > MAX_BROWSER_HISTORY:
                browsers = sorted(browsers, key=lambda x: x["last_login"], reverse=True)[:MAX_BROWSER_HISTORY]
            
            config['users'][username]["browsers"] = browsers
        
        save_config(config)
        return True
    return False

def handle_logout():
    """Handles user logout."""
    session.pop('username', None)
    return True

def get_current_user_info():
    if 'username' in session:
        username = session['username']
        config = get_config()
        
        # Ensure users exists and is a dictionary
        users_dict = config.get('users', {})
        if not isinstance(users_dict, dict):
            users_dict = {}
        
        user_details = users_dict.get(username)
        if user_details:
            # Find the current browser
            browser_id = generate_browser_fingerprint()
            current_browser = None
            
            for browser in user_details.get("browsers", []):
                if browser["browser_identity"] == browser_id:
                    current_browser = browser
                    break
            
            return {
                "username": username,
                "ip_address": current_browser["ip_address"] if current_browser else request.remote_addr,
                "browser": current_browser
            }
    return None

def get_active_users_count():
    """Count users with recent activity (within the last hour)."""
    config = get_config()
    users_dict = config.get('users', {})
    if not isinstance(users_dict, dict):
        return 0
    
    # This function no longer counts active users since that's now handled by socket connections
    # It's kept for backward compatibility
    return len(users_dict)

def add_activity_log(username, ip_address, action, details=""):
    """Adds an activity to the logs.json file."""
    logs = read_logs()
    
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "username": username,
        "ip_address": ip_address,
        "action": action,
        "details": details
    }
    logs.insert(0, log_entry) # Add to the beginning to show newest first
    
    # Keep log size manageable
    logs = logs[:MAX_LOG_ENTRIES] 
    
    write_logs(logs)

def get_recent_logs(count=20):
    """Gets a specified number of recent logs."""
    all_logs = read_logs()
    return all_logs[:count]

# Need to import datetime for add_activity_log
import datetime 