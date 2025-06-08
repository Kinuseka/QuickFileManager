from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, g
from flask_socketio import SocketIO, emit
import os
from dotenv import load_dotenv
import datetime # Added for logging
import mimetypes
import threading
import time
import atexit

from config import get_config, save_config # save_config is needed for updating user SIDs
from auth import login_required, handle_login, handle_logout, get_current_user_info, get_active_users_count, add_activity_log, read_logs, get_recent_logs, get_real_ip, generate_browser_fingerprint, get_browser_data # Added read_logs, get_recent_logs, get_real_ip, generate_browser_fingerprint, get_browser_data
from file_manager import FileManager

# File system monitoring
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    print("WARNING: watchdog library not installed. External file changes will not be detected.")
    print("Install with: pip install watchdog")
    WATCHDOG_AVAILABLE = False

load_dotenv() # Load environment variables from .env if present

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24)) # Important for session management
socketio = SocketIO(app)

# Initialize FileManager - it will load its own config for managed_directory
try:
    file_manager = FileManager()
except ValueError as e:
    print(f"CRITICAL ERROR initializing FileManager: {e}")
    # Potentially exit or run in a degraded mode if file management is core
    # For now, we'll let it continue, but file operations will likely fail.
    file_manager = None 

# Active connections tracking
active_connections = {
    '/updates': set(),  # Set of SIDs connected to /updates namespace
    '/logs': set()      # Set of SIDs connected to /logs namespace
}

# External file monitoring system removed as requested

def get_active_users_count():
    """
    Get the count of active users based on unique connections to the /updates namespace.
    This is more accurate than using config.yml since it reflects actual active connections.
    """
    return len(active_connections['/updates'])

# --- Utility ---
def log_user_activity(action, details="", username=None, ip_address=None):
    """
    Log user or system activity and broadcast it.
    Can be called with specific user info, or will try to get it from the request context.
    """
    try:
        if username is None or ip_address is None:
            # Try to get info from Flask's request context
            user_info = get_current_user_info()
            if user_info:
                username = user_info.get('username', 'Unknown')
                ip_address = user_info.get('ip_address', get_real_ip())
            else:
                # Fallback for contexts without a logged-in user (e.g., system events)
                username = username or "SYSTEM"
                ip_address = ip_address or "N/A"
        
        # Add entry to the persistent log file
        add_activity_log(username, ip_address, action, details)
        
        # Prepare data for SocketIO broadcast
        log_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'username': username,
            'ip_address': ip_address,
            'action': action,
            'details': details
        }
        
        # Always broadcast the activity via SocketIO
        socketio.emit('new_activity', log_data, namespace='/logs')
        
    except Exception as e:
        print(f"Error logging user activity: {e}")
        # Don't let logging errors break the application
        pass


# --- Authentication Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('index'))
    
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            error = "Username and password are required."
        elif handle_login(username, password):
            log_user_activity("login", f"Username: {username}")
            socketio.emit('user_count_update', {'count': get_active_users_count()}, namespace='/updates')
            next_url = request.args.get('next')
            # Security: Only allow relative URLs to prevent open redirect attacks
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect(url_for('index'))
        else:
            error = "Invalid credentials. Please try again."
            add_activity_log(username or "Unknown_User", get_real_ip(), "login_fail")
            
    return render_template('login.html', error=error)

@app.route('/logout')
@login_required
def logout():
    user_info = get_current_user_info() # Get info before logout
    if user_info:
        log_user_activity("logout", f"Username: {user_info.get('username', 'Unknown')}")
    
    handle_logout() # This function in auth.py removes the user from config['users'] and saves config
    
    # After user is removed by handle_logout, get the fresh count and broadcast
    current_active_users = get_active_users_count()
    socketio.emit('user_count_update', {'count': current_active_users}, room=None, namespace='/updates')
    print(f"INFO: User {user_info.get('username' if user_info else 'Unknown')} logged out. Broadcasted count: {current_active_users}")
    return redirect(url_for('login'))

# --- Main Application Routes (File Management) ---
@app.route('/')
@login_required
def index():
    # user_info = get_user_info(session.get('user_id')) # This line will be removed or commented out
    # Use g.user which is populated by the @login_required decorator
    username_to_display = g.user.get('username', 'User') if hasattr(g, 'user') and g.user else 'User'
    return render_template('index.html', username=username_to_display)

# Handle listing the root of the managed directory
@app.route('/api/files', methods=['GET'])
@app.route('/api/files/', methods=['GET'])
@login_required
def list_files_root_api():
    # This function will specifically handle requests to /api/files and /api/files/
    # It calls the main list_files_api logic with an empty path.
    return list_files_api(req_path='')

# Handle listing subdirectories and files
@app.route('/api/files/<path:req_path>', methods=['GET'])
@login_required
def list_files_api(req_path):
    if not file_manager:
        return jsonify({"error": "FileManager not initialized"}), 500
    try:
        # req_path can be empty if called from list_files_root_api
        # It will have a value if matched by /api/files/<path:req_path>
        req_path = req_path.strip('/') 
        data = file_manager.list_directory(req_path)
        
        if data.get("error"):
            # Distinguish between path not found/not a dir and other errors for status codes
            if "Path does not exist" in data["error"] or "Path is not a directory" in data["error"]:
                return jsonify(data), 404
            elif "Cannot access directory contents" in data["error"]:
                 return jsonify(data), 403 # Forbidden if permission issue
            return jsonify(data), 400 # Bad request for other logical errors from FileManager
        
        log_user_activity("list_dir", f"Path: /{req_path if req_path else ''}")
        return jsonify(data)
    except PermissionError as e: # Raised by _get_safe_path for traversal attempts
        log_user_activity("access_denied", f"Attempted: View Directory, Path: /{req_path}, Error: {str(e)}")
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        # Generic catch-all for unexpected errors
        print(f"UNEXPECTED ERROR in list_files_api for path '{req_path}': {e}")
        log_user_activity("operation_error", f"Operation: List Files, Path: /{req_path}, Error: {str(e)}")
        return jsonify({"error": "An unexpected server error occurred while listing files."}), 500


@app.route('/api/file/content', methods=['GET', 'POST'])
@login_required
def file_content_api():
    if not file_manager:
        return jsonify({"error": "FileManager not initialized"}), 500
    
    if request.method == 'GET':
        file_path = request.args.get('path')
        if not file_path:
            return jsonify({"error": "File path is required."}), 400
        try:
            content_data = file_manager.get_file_content(file_path)
            if content_data.get("error"):
                return jsonify(content_data), 404
            log_user_activity("preview", f"Path: {file_path}")
            return jsonify(content_data)
        except PermissionError as e:
            log_user_activity("access_denied", f"Attempted: View File, Path: {file_path}, Error: {str(e)}")
            return jsonify({"error": str(e)}), 403
        except Exception as e:
            log_user_activity("operation_error", f"Operation: Get File Content, Path: {file_path}, Error: {str(e)}")
            return jsonify({"error": "An error occurred."}), 500

    elif request.method == 'POST':
        data = request.json
        file_path = data.get('path')
        content = data.get('content', '') # Default to empty string for new files
        if not file_path:
            return jsonify({"error": "File path is required."}), 400
        try:
            result = file_manager.save_file_content(file_path, content)
            if result.get("error"):
                return jsonify(result), 400
            log_user_activity("save_file", f"Path: {file_path}")
            

                
            socketio.emit('file_changed', {'path': file_path, 'action': 'modified'}, namespace='/updates')
            return jsonify(result)
        except PermissionError as e:
            log_user_activity("access_denied", f"Attempted: Save File, Path: {file_path}, Error: {str(e)}")
            return jsonify({"error": str(e)}), 403
        except Exception as e:
            log_user_activity("operation_error", f"Operation: Save File, Path: {file_path}, Error: {str(e)}")
            return jsonify({"error": "An error occurred saving the file."}), 500


@app.route('/api/create/folder', methods=['POST'])
@login_required
def create_folder_api():
    if not file_manager:
        return jsonify({"error": "FileManager not initialized"}), 500
    data = request.json
    folder_path = data.get('path')
    if not folder_path:
        return jsonify({"error": "Folder path is required."}), 400
    try:
        result = file_manager.create_folder(folder_path)
        if result.get("error"):
            return jsonify(result), 400
        log_user_activity("create_folder", f"Path: {folder_path}")
        

            
        socketio.emit('file_changed', {'path': folder_path, 'action': 'created', 'type': 'folder'}, namespace='/updates')
        return jsonify(result)
    except PermissionError as e:
        log_user_activity("access_denied", f"Attempted: Create Folder, Path: {folder_path}, Error: {str(e)}")
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        log_user_activity("operation_error", f"Operation: Create Folder, Path: {folder_path}, Error: {str(e)}")
        return jsonify({"error": "An error occurred creating the folder."}), 500


@app.route('/api/delete', methods=['POST']) # Changed to POST for item path in body
@login_required
def delete_item_api():
    if not file_manager:
        return jsonify({"error": "FileManager not initialized"}), 500
    data = request.json
    item_path = data.get('path')
    if not item_path:
        return jsonify({"error": "Item path is required for deletion."}), 400
    try:
        result = file_manager.delete_item(item_path)
        if result.get("error"):
            return jsonify(result), 400 # Or 404 if not found
        log_user_activity("delete", f"Path: {item_path}")
        socketio.emit('file_changed', {'path': item_path, 'action': 'deleted'}, namespace='/updates')
        return jsonify(result)
    except PermissionError as e:
        log_user_activity("access_denied", f"Attempted: Delete Item, Path: {item_path}, Error: {str(e)}")
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        log_user_activity("operation_error", f"Operation: Delete Item, Path: {item_path}, Error: {str(e)}")
        return jsonify({"error": "An error occurred deleting the item."}), 500
        
@app.route('/api/batch-delete', methods=['POST'])
@login_required
def batch_delete_api():
    if not file_manager:
        return jsonify({"error": "FileManager not initialized"}), 500
    data = request.json
    item_paths = data.get('paths')
    if not item_paths or not isinstance(item_paths, list):
        return jsonify({"error": "A list of item paths is required."}), 400
    try:
        results = file_manager.batch_delete_items(item_paths)
        # Log each successful deletion or overall attempt
        deleted_paths = [res['path'] for res in results.get('results', []) if res['status'] == 'success']
        if deleted_paths:
            log_user_activity("batch_delete", f"Paths: {', '.join(deleted_paths)}")
            for path in deleted_paths: # Emit change for each deleted item
                 socketio.emit('file_changed', {'path': path, 'action': 'deleted'}, namespace='/updates')
        if not results.get("success"): # If any operation failed
            failed_paths = [res['path'] for res in results.get('results', []) if res['status'] == 'error']
            log_user_activity("operation_error", f"Operation: Batch Delete, Failed paths: {', '.join(failed_paths)}")
            # Consider returning a more specific error code if all fail vs some fail
            return jsonify(results), 400 # Or 207 (Multi-Status) if some succeed
        return jsonify(results)

    except PermissionError as e: # This might be caught within FileManager now
        log_user_activity("access_denied", f"Attempted: Batch Delete, Error: {str(e)}")
        return jsonify({"error": "Permission denied during batch delete."}), 403
    except Exception as e:
        log_user_activity("operation_error", f"Operation: Batch Delete, Error: {str(e)}")
        return jsonify({"error": "An unexpected error occurred during batch delete."}), 500


@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file_api():
    if not file_manager:
        return jsonify({"error": "FileManager not initialized"}), 500
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request."}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file."}), 400

    # Check file size limit
    config = get_config()
    upload_config = config.get('upload', {})
    max_file_size_gb = upload_config.get('max_file_size_gb', 8)
    max_file_size_bytes = max_file_size_gb * 1024 * 1024 * 1024
    
    # Get file size from Content-Length header or seek to end if available
    file_size = None
    if hasattr(file, 'content_length') and file.content_length:
        file_size = file.content_length
    elif hasattr(file, 'seek') and hasattr(file, 'tell'):
        # Try to get size by seeking (this might not work in all cases)
        current_pos = file.tell()
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(current_pos)  # Restore position
    
    if file_size and file_size > max_file_size_bytes:
        return jsonify({"error": f"File size ({file_size / (1024*1024*1024):.2f}GB) exceeds maximum allowed size of {max_file_size_gb}GB."}), 413

    # Get target sub_path from form data (e.g., current directory in file manager)
    upload_sub_path = request.form.get('path', '') # Default to root of managed_dir

    try:
        result = file_manager.upload_file(file, upload_sub_path)
        if result.get("error"):
            return jsonify(result), 400
        log_user_activity("upload", f"Filename: {file.filename}, Path: {upload_sub_path}")
        socketio.emit('file_changed', {'path': result.get('path'), 'action': 'uploaded', 'filename': result.get('filename')}, namespace='/updates')
        return jsonify(result)
    except PermissionError as e:
        log_user_activity("access_denied", f"Attempted: Upload File, Filename: {file.filename}, Path: {upload_sub_path}, Error: {str(e)}")
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        log_user_activity("operation_error", f"Operation: Upload File, Filename: {file.filename}, Path: {upload_sub_path}, Error: {str(e)}")
        return jsonify({"error": "An error occurred uploading the file."}), 500

@app.route('/api/upload/chunk', methods=['POST'])
@login_required
def upload_chunk_api():
    """Handle chunked file uploads."""
    if not file_manager:
        return jsonify({"error": "FileManager not initialized"}), 500
    
    # Get chunk data from request
    chunk_data = request.files.get('chunk')
    if not chunk_data:
        return jsonify({"error": "No chunk data provided"}), 400
    
    upload_id = request.form.get('uploadId')
    chunk_index = request.form.get('chunkIndex')
    total_chunks = request.form.get('totalChunks')
    filename = request.form.get('filename')
    upload_path = request.form.get('path', '')
    
    if not all([upload_id, chunk_index is not None, total_chunks, filename]):
        return jsonify({"error": "Missing required chunk parameters"}), 400
    
    try:
        chunk_index = int(chunk_index)
        total_chunks = int(total_chunks)
    except ValueError:
        return jsonify({"error": "Invalid chunk parameters"}), 400
    
    try:
        result = file_manager.upload_chunk(
            chunk_data, upload_id, chunk_index, total_chunks, filename, upload_path
        )
        if result.get("error"):
            return jsonify(result), 400
        
        # Log activity for the final chunk
        if result.get("completed"):
            log_user_activity("chunked_upload", f"Filename: {filename}, Path: {upload_path}")
            socketio.emit('file_changed', {
                'path': result.get('path'), 
                'action': 'uploaded', 
                'filename': result.get('filename')
            }, namespace='/updates')
        
        return jsonify(result)
    except PermissionError as e:
        log_user_activity("access_denied", f"Attempted: Chunked Upload, Filename: {filename}, Error: {str(e)}")
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        log_user_activity("operation_error", f"Operation: Chunked Upload, Filename: {filename}, Error: {str(e)}")
        return jsonify({"error": "An error occurred during chunked upload."}), 500

@app.route('/api/upload/cancel', methods=['POST'])
@login_required
def cancel_upload_api():
    """Cancel an ongoing chunked upload and clean up temporary files."""
    if not file_manager:
        return jsonify({"error": "FileManager not initialized"}), 500
    
    data = request.json or {}
    upload_id = data.get('uploadId')
    
    if not upload_id:
        return jsonify({"error": "Upload ID is required"}), 400
    
    try:
        result = file_manager.cancel_chunked_upload(upload_id)
        log_user_activity("upload_cancelled", f"Upload ID: {upload_id}")
        return jsonify(result)
    except Exception as e:
        log_user_activity("operation_error", f"Operation: Cancel Upload, Upload ID: {upload_id}, Error: {str(e)}")
        return jsonify({"error": "An error occurred cancelling the upload."}), 500

@app.route('/api/upload/config', methods=['GET'])
@login_required
def get_upload_config():
    """Get upload configuration for the client."""
    config = get_config()
    upload_config = config.get('upload', {})
    
    return jsonify({
        "chunked_upload_enabled": upload_config.get('enable_chunked_upload', True),
        "chunk_size_mb": upload_config.get('chunk_size_mb', 10),
        "max_concurrent_chunks": upload_config.get('max_concurrent_chunks', 3),
        "max_file_size_gb": upload_config.get('max_file_size_gb', 8)
    })
        
@app.route('/download/<path:file_path>')
@login_required
def download_file(file_path):
    if not file_manager:
        return "FileManager not initialized", 500
    try:
        abs_file_path = file_manager._get_safe_path(file_path) 
        if not os.path.isfile(abs_file_path):
            return "File not found.", 404
        
        context = request.args.get('context', 'download')
        force_download = request.args.get('force_download', 'false').lower() == 'true'
        is_preview = context == 'preview'
        
        # Log actual downloads (not previews)
        # force_download=true always counts as a download regardless of context
        should_log = force_download or not is_preview
        
        if should_log:
            log_user_activity("download", f"Path: {file_path}")
        
        mimetype, _ = mimetypes.guess_type(abs_file_path)
        if mimetype is None:
            mimetype = 'application/octet-stream' 

        if is_preview and not force_download:
            return send_from_directory(os.path.dirname(abs_file_path), os.path.basename(abs_file_path), mimetype=mimetype)
        elif force_download or not mimetype.startswith(('image/', 'video/', 'audio/', 'text/', 'application/pdf')):
             return send_from_directory(os.path.dirname(abs_file_path), os.path.basename(abs_file_path), as_attachment=True, mimetype=mimetype)
        else: 
             return send_from_directory(os.path.dirname(abs_file_path), os.path.basename(abs_file_path), mimetype=mimetype)
            
    except PermissionError as e:
        log_user_activity("access_denied", f"Attempted: Download File, Path: {file_path}, Error: {str(e)}")
        return str(e), 403
    except Exception as e:
        log_user_activity("operation_error", f"Operation: Download File, Path: {file_path}, Error: {str(e)}")
        print(f"Error in download_file for {file_path}: {e}")
        return "An error occurred.", 500

@app.route('/api/zip', methods=['POST'])
@login_required
def zip_items_api():
    if not file_manager: return jsonify({"error": "FileManager not initialized"}), 500
    data = request.json
    items_to_zip = data.get('items') # List of relative paths
    archive_name = data.get('archive_name')
    output_sub_path = data.get('output_path', '') # Relative path for zip output
    delete_after_zip = data.get('delete_after_zip', False) # Whether to delete original files

    if not items_to_zip or not isinstance(items_to_zip, list) or not archive_name:
        return jsonify({"error": "Required parameters: 'items' (list) and 'archive_name'."}), 400
    
    try:
        result = file_manager.zip_items(items_to_zip, archive_name, output_sub_path)
        if result.get("error"):
            return jsonify(result), 400
        
        # If successful and delete_after_zip is requested, delete the original files
        if delete_after_zip and result.get("success"):
            try:
                delete_results = file_manager.batch_delete_items(items_to_zip)
                if delete_results.get("success"):
                    log_user_activity("zip_with_delete", f"Archive: {result.get('archive_path')}, Items count: {len(items_to_zip)}, Original files deleted")
                    # Emit delete events for each original file
                    for item_path in items_to_zip:
                        socketio.emit('file_changed', {'path': item_path, 'action': 'deleted'}, namespace='/updates')
                else:
                    log_user_activity("zip", f"Archive: {result.get('archive_path')}, Items count: {len(items_to_zip)}, Warning: Could not delete some original files")
            except Exception as delete_error:
                print(f"Error deleting files after zip: {delete_error}")
                log_user_activity("zip", f"Archive: {result.get('archive_path')}, Items count: {len(items_to_zip)}, Warning: Could not delete original files")
        else:
            log_user_activity("zip", f"Archive: {result.get('archive_path')}, Items count: {len(items_to_zip)}")
        
        socketio.emit('file_changed', {'path': result.get('archive_path'), 'action': 'created', 'type': 'file'}, namespace='/updates') # A zip is a file
        return jsonify(result)
    except PermissionError as e:
        log_user_activity("access_denied", f"Attempted: Zip Items, Archive: {archive_name}, Error: {str(e)}")
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        log_user_activity("operation_error", f"Operation: Zip Items, Archive: {archive_name}, Error: {str(e)}")
        return jsonify({"error": "An error occurred while zipping items."}), 500

@app.route('/api/unzip', methods=['POST'])
@login_required
def unzip_file_api():
    if not file_manager: return jsonify({"error": "FileManager not initialized"}), 500
    data = request.json
    zip_file_path = data.get('zip_path') # Relative path to the zip file
    extract_to_sub_path = data.get('extract_path', '') # Relative path for extraction output, default to zip's dir

    if not zip_file_path:
        return jsonify({"error": "Required parameter: 'zip_path'."}), 400

    try:
        result = file_manager.unzip_file(zip_file_path, extract_to_sub_path)
        if result.get("error"):
            return jsonify(result), 400
        log_user_activity("unzip", f"Zip: {zip_file_path}, Target: {extract_to_sub_path if extract_to_sub_path else os.path.dirname(zip_file_path)}")
        # Emitting a general update for the directory where files were extracted
        # A more granular update would list all extracted files/folders
        target_path_for_update = extract_to_sub_path if extract_to_sub_path else os.path.dirname(zip_file_path)
        if target_path_for_update == ".": target_path_for_update = "" # normalize for root
        socketio.emit('file_changed', {'path': target_path_for_update, 'action': 'unzipped_into'}, namespace='/updates')
        return jsonify(result)
    except PermissionError as e:
        log_user_activity("access_denied", f"Attempted: Unzip File, Zip: {zip_file_path}, Error: {str(e)}")
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        log_user_activity("operation_error", f"Operation: Unzip File, Zip: {zip_file_path}, Error: {str(e)}")
        return jsonify({"error": "An error occurred while unzipping the file."}), 500

@app.route('/api/rename', methods=['POST'])
@login_required
def rename_item_api():
    if not file_manager:
        return jsonify({"error": "FileManager not initialized"}), 500

    data = request.json
    current_relative_path = data.get('current_path')
    new_name = data.get('new_name')
    item_type = data.get('type') # 'file' or 'folder', useful for logging

    if not current_relative_path or new_name is None: # new_name can be empty string initially before secure_filename, so check for None
        return jsonify({"error": "Required parameters: 'current_path' and 'new_name'"}), 400

    # It's good practice to get the old name for logging *before* the rename operation
    old_name_for_log = os.path.basename(current_relative_path)

    try:
        result = file_manager.rename_item(current_relative_path, new_name)
        if result.get("error"):
            return jsonify(result), 400 # e.g., item not found, name exists, invalid name
        
        # Log the successful rename activity
        log_user_activity("rename", f"From: '{old_name_for_log}' to '{result.get('new_name')}' at '{os.path.dirname(current_relative_path)}'")
        
        # Emit file change events for real-time update
        # Option 1: Simple - tell client to refresh parent directory (or current if it was root)
        parent_dir_of_renamed = os.path.dirname(current_relative_path)
        if parent_dir_of_renamed == ".": parent_dir_of_renamed = ""

        # More specific event for rename might be better for client-side handling
        socketio.emit('file_changed', {
            'action': 'renamed',
            'old_path': current_relative_path,
            'new_path': result.get('new_path'),
            'new_name': result.get('new_name'),
            'parent_path': parent_dir_of_renamed, # directory where rename happened
            'type': item_type
        }, namespace='/updates')
        
        return jsonify(result)
    except PermissionError as e: # Should be caught by FileManager, but as a safeguard
        log_user_activity("access_denied", f"Attempted: Rename Item, Path: {current_relative_path}, New Name: {new_name}, Error: {str(e)}")
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        log_user_activity("operation_error", f"Operation: Rename Item, Path: {current_relative_path}, New Name: {new_name}, Error: {str(e)}")
        return jsonify({"error": "An unexpected server error occurred during rename."}), 500

@app.route('/api/move', methods=['POST'])
@login_required
def move_item_api():
    if not file_manager:
        return jsonify({"error": "FileManager not initialized"}), 500

    data = request.json
    source_path = data.get('source')
    target_path = data.get('target')

    if not source_path or target_path is None:
        return jsonify({"error": "Required parameters: 'source' and 'target'"}), 400

    # Normalize paths - convert "/" to empty string for root (file manager expects this)
    if target_path == '/':
        target_path = ''

    try:
        # Get source item name for the move
        source_name = os.path.basename(source_path)
        
        # The target should be a directory
        target_file_path = os.path.join(target_path, source_name)
        
        # Check if source exists
        source_abs_path = file_manager._get_safe_path(source_path)
        if not os.path.exists(source_abs_path):
            return jsonify({"error": "Source item not found"}), 404
            
        # Check if target directory exists
        target_dir_abs_path = file_manager._get_safe_path(target_path)
        if not os.path.isdir(target_dir_abs_path):
            return jsonify({"error": "Target is not a directory"}), 400
        
        # Check if target already exists
        target_abs_path = file_manager._get_safe_path(target_file_path)
        if os.path.exists(target_abs_path):
            return jsonify({"error": f"Item '{source_name}' already exists in target directory"}), 400
        
        # Perform the move
        import shutil
        shutil.move(source_abs_path, target_abs_path)
        
        # Log the move activity
        log_user_activity("move", f"From: '{source_path}' to '{target_file_path}'")
        
        # Emit file change events for real-time update
        socketio.emit('file_changed', {
            'action': 'moved',
            'old_path': source_path,
            'new_path': target_file_path,
            'source_parent': os.path.dirname(source_path),
            'target_parent': target_path
        }, namespace='/updates')
        
        return jsonify({"success": True, "new_path": target_file_path})
        
    except PermissionError as e:
        log_user_activity("access_denied", f"Attempted: Move Item, Source: {source_path}, Target: {target_path}, Error: {str(e)}")
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        log_user_activity("operation_error", f"Operation: Move Item, Source: {source_path}, Target: {target_path}, Error: {str(e)}")
        return jsonify({"error": "An unexpected server error occurred during move."}), 500

@app.route('/api/archive/contents', methods=['GET'])
@login_required
def get_archive_contents_api():
    if not file_manager:
        return jsonify({"error": "FileManager not initialized"}), 500

    archive_file_path = request.args.get('path')
    if not archive_file_path:
        return jsonify({"error": "Required query parameter: 'path' for the archive file."}), 400

    try:
        result = file_manager.get_archive_contents(archive_file_path)
        if result.get("error"):
            # Handle specific errors from FileManager if needed, e.g., 404 for not found
            if "not found" in result["error"].lower() or "not a valid" in result["error"].lower():
                 return jsonify(result), 404
            return jsonify(result), 400 # Bad request for other errors like bad archive file
        
        # Log activity (optional, could be verbose if just listing contents)
        log_user_activity("preview", f"Archive: {archive_file_path}")
        return jsonify(result)
    except PermissionError as e: # Should be caught by FileManager's _get_safe_path
        log_user_activity("access_denied", f"Attempted: View Archive Contents, File: {archive_file_path}, Error: {str(e)}")
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        log_user_activity("operation_error", f"Operation: Get Archive Contents, File: {archive_file_path}, Error: {str(e)}")
        print(f"Error in get_archive_contents_api for {archive_file_path}: {e}")
        return jsonify({"error": "An unexpected server error occurred while reading archive contents."}), 500

# Keep the old ZIP endpoint for backward compatibility
@app.route('/api/zip/contents', methods=['GET'])
@login_required
def get_zip_contents_api():
    if not file_manager:
        return jsonify({"error": "FileManager not initialized"}), 500

    zip_file_path = request.args.get('path')
    if not zip_file_path:
        return jsonify({"error": "Required query parameter: 'path' for the ZIP file."}), 400

    try:
        result = file_manager.get_archive_contents(zip_file_path)
        if result.get("error"):
            # Handle specific errors from FileManager if needed, e.g., 404 for not found
            if "not found" in result["error"].lower() or "not a valid" in result["error"].lower():
                 return jsonify(result), 404
            return jsonify(result), 400 # Bad request for other errors like bad archive file
        
        # Log activity (optional, could be verbose if just listing contents)
        return jsonify(result)
    except PermissionError as e: # Should be caught by FileManager's _get_safe_path
        log_user_activity("access_denied", f"Attempted: View ZIP Contents, File: {zip_file_path}, Error: {str(e)}")
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        log_user_activity("operation_error", f"Operation: Get ZIP Contents, File: {zip_file_path}, Error: {str(e)}")
        print(f"Error in get_zip_contents_api for {zip_file_path}: {e}")
        return jsonify({"error": "An unexpected server error occurred while reading ZIP contents."}), 500

@app.route('/api/preview/intent', methods=['POST'])
@login_required
def preview_intent_api():
    """
    Endpoint for client to signal intent to preview a file.
    This separates the logging of preview intent from the actual file delivery.
    """
    data = request.json
    file_path = data.get('path')
    
    if not file_path:
        return jsonify({"error": "File path is required."}), 400
    
    try:
        # Check if file exists
        if not file_manager:
            return jsonify({"error": "FileManager not initialized"}), 500
            
        abs_file_path = file_manager._get_safe_path(file_path)
        if not os.path.isfile(abs_file_path):
            return jsonify({"error": "File not found."}), 404
        
        # Log the preview intent
        log_user_activity("preview", f"Path: {file_path}")
        
        # Return success
        return jsonify({"success": True})
    except PermissionError as e:
        log_user_activity("access_denied", f"Attempted: Preview File, Path: {file_path}, Error: {str(e)}")
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        log_user_activity("operation_error", f"Operation: Preview File, Path: {file_path}, Error: {str(e)}")
        return jsonify({"error": "An error occurred."}), 500

# --- SocketIO Event Handlers ---
@socketio.on('connect', namespace='/updates')
@login_required 
def handle_updates_connect():
    # The @login_required decorator already ensures 'username' is in session
    # Add the connection to active_connections
    active_connections['/updates'].add(request.sid)
    
    # Log the connection
    username = session.get('username', 'Unknown')
    print(f"Client {username} (SID: {request.sid}) connected to /updates. Active connections: {len(active_connections['/updates'])}")
    
    # Emit current user count to this newly connected client
    emit('user_count_update', {'count': get_active_users_count()})
    
    # Broadcast updated count to all clients
    socketio.emit('user_count_update', {'count': get_active_users_count()}, room=None, namespace='/updates')

@socketio.on('disconnect', namespace='/updates')
def handle_updates_disconnect(reason=None):
    # Remove the connection from active_connections if it exists
    if request.sid in active_connections['/updates']:
        active_connections['/updates'].remove(request.sid)
        print(f"Client (SID: {request.sid}) disconnected from /updates. Reason: {reason}. Active connections: {len(active_connections['/updates'])}")
        
        # Broadcast updated count to all clients
        socketio.emit('user_count_update', {'count': get_active_users_count()}, room=None, namespace='/updates')

@socketio.on('connect', namespace='/logs')
@login_required
def handle_logs_connect():
    # The @login_required decorator already ensures 'username' is in session        
    # Add the connection to active_connections
    active_connections['/logs'].add(request.sid)
    
    print(f"Client {session.get('username', request.sid)} connected to /logs")
    recent_logs = get_recent_logs(count=50) # Fetch recent logs from auth.py (logs.json)
    emit('initial_logs', {'logs': recent_logs})

@socketio.on('disconnect', namespace='/logs')
def handle_logs_disconnect():
    # Remove the connection from active_connections if it exists
    if request.sid in active_connections['/logs']:
        active_connections['/logs'].remove(request.sid)
        print(f"Client (SID: {request.sid}) disconnected from /logs.")

@app.route('/api/activity_log', methods=['GET'])
@login_required
def get_activity_log_api():
    all_logs = read_logs() # Fetch all logs from auth.py (logs.json)
    return jsonify(all_logs)

@app.route('/api/user/status', methods=['GET'])
@login_required
def user_status_api():
    user_info = get_current_user_info()
    active_users = get_active_users_count()
    
    if user_info:
        return jsonify({
            "logged_in": True,
            "username": user_info['username'],
            "ip_address": user_info['ip_address'],
            "user_count": active_users
        })
    return jsonify({"logged_in": False, "user_count": active_users}), 401

@app.route('/debug/request-info', methods=['GET'])
@login_required
def debug_request_info():
    """Debug route showing comprehensive request information including headers and IP details."""
    
    # Get all request headers
    headers_dict = dict(request.headers)
    
    # Get IP information
    real_ip = get_real_ip()
    remote_addr = request.remote_addr
    
    # Get proxy-related headers specifically
    proxy_headers = {
        'X-Forwarded-For': request.headers.get('X-Forwarded-For'),
        'X-Real-IP': request.headers.get('X-Real-IP'),
        'X-Forwarded-Proto': request.headers.get('X-Forwarded-Proto'),
        'X-Forwarded-Host': request.headers.get('X-Forwarded-Host'),
        'CF-Connecting-IP': request.headers.get('CF-Connecting-IP'),  # CloudFlare
        'True-Client-IP': request.headers.get('True-Client-IP'),      # CloudFlare
        'X-Client-IP': request.headers.get('X-Client-IP'),
        'X-Cluster-Client-IP': request.headers.get('X-Cluster-Client-IP'),
        'Forwarded': request.headers.get('Forwarded'),
    }
    
    # Filter out None values
    proxy_headers = {k: v for k, v in proxy_headers.items() if v is not None}
    
    # Get user and session information
    user_info = get_current_user_info()
    
    # Get browser data
    try:
        browser_data = get_browser_data()
        browser_fingerprint = generate_browser_fingerprint()
    except Exception as e:
        browser_data = {"error": str(e)}
        browser_fingerprint = f"Error: {e}"
    
    # Get environment information
    environ_info = {
        'REQUEST_METHOD': request.method,
        'PATH_INFO': request.path,
        'QUERY_STRING': request.query_string.decode('utf-8'),
        'CONTENT_TYPE': request.content_type,
        'CONTENT_LENGTH': request.content_length,
        'SERVER_NAME': request.host,
        'SERVER_PORT': request.environ.get('SERVER_PORT'),
        'SCRIPT_NAME': request.script_root,
        'REQUEST_URI': request.url,
        'HTTP_HOST': request.environ.get('HTTP_HOST'),
        'REMOTE_ADDR': request.environ.get('REMOTE_ADDR'),
        'REMOTE_HOST': request.environ.get('REMOTE_HOST'),
        'REMOTE_USER': request.environ.get('REMOTE_USER'),
    }
    
    # Get WSGI environ keys related to proxy/IP
    wsgi_ip_keys = {}
    for key, value in request.environ.items():
        if any(term in key.upper() for term in ['IP', 'ADDR', 'FORWARD', 'PROXY', 'CLIENT', 'REAL']):
            wsgi_ip_keys[key] = value
    
    debug_info = {
        "timestamp": datetime.datetime.now().isoformat(),
        "ip_information": {
            "get_real_ip()": real_ip,
            "request.remote_addr": remote_addr,
            "ip_sources_match": real_ip == remote_addr
        },
        "proxy_headers": proxy_headers,
        "all_headers": headers_dict,
        "wsgi_ip_environ": wsgi_ip_keys,
        "request_environ": environ_info,
        "session_info": {
            "session_id": request.cookies.get('session'),
            "username": session.get('username'),
            "session_keys": list(session.keys()) if session else []
        },
        "user_info": user_info,
        "browser_info": {
            "fingerprint": browser_fingerprint,
            "data": browser_data,
            "user_agent": request.headers.get('User-Agent')
        },
        "flask_info": {
            "is_secure": request.is_secure,
            "scheme": request.scheme,
            "endpoint": request.endpoint,
            "view_args": request.view_args,
            "base_url": request.base_url,
            "url_root": request.url_root
        }
    }
    
    return jsonify(debug_info)

@app.route('/rename', methods=['POST'])
@login_required
def rename_redirect():
    # Redirect to the proper API endpoint
    return rename_item_api()

if __name__ == '__main__':
    # Cleanup function 
    def cleanup():
        print("Cleaning up...")
    
    # Register cleanup function
    atexit.register(cleanup)
    
    # Start the Flask-SocketIO server
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"Starting server on {host}:{port}")
    print(f"Debug mode: {debug}")
    
    try:
        socketio.run(app, host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        cleanup()
    except Exception as e:
        print(f"Server error: {e}")
        cleanup()
        raise 