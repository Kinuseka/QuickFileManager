import os
import shutil
import zipfile
try:
    import rarfile
    RARFILE_AVAILABLE = True
except ImportError:
    RARFILE_AVAILABLE = False

try:
    import py7zr
    PY7ZR_AVAILABLE = True
except ImportError:
    PY7ZR_AVAILABLE = False

try:
    import tarfile
    TARFILE_AVAILABLE = True
except ImportError:
    TARFILE_AVAILABLE = False

from werkzeug.utils import secure_filename
from config import get_config
import tempfile
import time
import threading
import uuid

class FileManager:
    def __init__(self):
        self.config = get_config()
        self.managed_dir = self._get_managed_dir()  # Cache the managed directory path
        if not self.managed_dir:
            raise Exception("Could not initialize managed directory")
        
        # Initialize chunked upload storage
        self.chunk_uploads = {}  # Store information about ongoing chunked uploads
        self.upload_lock = threading.Lock()  # Thread safety for chunked uploads
        self._setup_cleanup_timer()  # Start cleanup timer for abandoned uploads

    def _get_managed_dir(self):
        """Get and validate the managed directory path."""
        managed_dir = self.config.get('managed_directory', './managed_files')
        abs_managed_dir = os.path.abspath(managed_dir)
        
        if not os.path.exists(abs_managed_dir):
            try:
                os.makedirs(abs_managed_dir)
                print(f"Created managed directory at {abs_managed_dir}")
            except Exception as e:
                print(f"Error creating managed directory: {e}")
                return None
        elif not os.path.isdir(abs_managed_dir):
            print(f"Managed path exists but is not a directory: {abs_managed_dir}")
            return None
        
        # Don't print the info message on every call
        return abs_managed_dir

    def _get_safe_path(self, relative_path):
        """Convert a relative path to a safe absolute path within managed directory."""
        if not self.managed_dir:
            raise Exception("Managed directory not initialized")
            
        # Clean the relative path
        cleaned_path = os.path.normpath(relative_path.lstrip('/'))
        if cleaned_path == '.' or not cleaned_path:
            return self.managed_dir
            
        # Construct and validate the absolute path
        abs_path = os.path.abspath(os.path.join(self.managed_dir, cleaned_path))
        if not abs_path.startswith(self.managed_dir):
            raise PermissionError(f"Access denied: Path '{relative_path}' attempts to escape managed directory.")
            
        return abs_path
    
    def _get_archive_type(self, file_path):
        """Determine archive type from file extension."""
        file_path_lower = file_path.lower()
        if file_path_lower.endswith('.zip'):
            return 'zip'
        elif file_path_lower.endswith('.rar'):
            return 'rar'
        elif file_path_lower.endswith('.7z'):
            return '7z'
        elif file_path_lower.endswith(('.tar', '.tar.gz', '.tar.bz2', '.tar.xz', '.tgz', '.tbz2')):
            return 'tar'
        return None

    def get_archive_contents(self, archive_file_relative_path):
        """Lists the contents of various archive formats."""
        try:
            abs_archive_path = self._get_safe_path(archive_file_relative_path)
        except PermissionError as e:
            return {"error": str(e)}

        if not os.path.isfile(abs_archive_path):
            return {"error": "Archive file not found."}
        
        archive_type = self._get_archive_type(archive_file_relative_path)
        if not archive_type:
            return {"error": "Unsupported archive format."}

        try:
            if archive_type == 'zip':
                return self._get_zip_contents(abs_archive_path, archive_file_relative_path)
            elif archive_type == 'rar':
                return self._get_rar_contents(abs_archive_path, archive_file_relative_path)
            elif archive_type == '7z':
                return self._get_7z_contents(abs_archive_path, archive_file_relative_path)
            elif archive_type == 'tar':
                return self._get_tar_contents(abs_archive_path, archive_file_relative_path)
            else:
                return {"error": f"Archive type '{archive_type}' not supported."}
        except Exception as e:
            print(f"ERROR: Unexpected error reading archive contents for '{abs_archive_path}': {e}")
            return {"error": f"Could not read archive file contents: {str(e)}"}

    def _get_zip_contents(self, abs_path, relative_path):
        """Get ZIP file contents."""
        if not zipfile.is_zipfile(abs_path):
            return {"error": "The specified file is not a valid ZIP archive."}

        with zipfile.ZipFile(abs_path, 'r') as zf:
            contents = []
            for member_info in zf.infolist():
                contents.append({
                    "name": member_info.filename,
                    "is_dir": member_info.is_dir(),
                    "size": member_info.file_size,
                    "compressed_size": member_info.compress_size,
                    "date_time": member_info.date_time
                })
            contents.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        return {"success": True, "contents": contents, "archive_type": "zip", "archive_path": relative_path}

    def _get_rar_contents(self, abs_path, relative_path):
        """Get RAR file contents."""
        if not RARFILE_AVAILABLE:
            return {"error": "RAR support not available. Install 'rarfile' library."}

        try:
            with rarfile.RarFile(abs_path, 'r') as rf:
                contents = []
                for member_info in rf.infolist():
                    contents.append({
                        "name": member_info.filename,
                        "is_dir": member_info.is_dir(),
                        "size": member_info.file_size,
                        "compressed_size": member_info.compress_size,
                        "date_time": member_info.date_time if hasattr(member_info, 'date_time') else None
                    })
                contents.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
            return {"success": True, "contents": contents, "archive_type": "rar", "archive_path": relative_path}
        except rarfile.RarCannotExec:
            return {"error": "RAR extraction tool not found. Please install unrar."}
        except Exception as e:
            return {"error": f"Could not read RAR file: {str(e)}"}

    def _get_7z_contents(self, abs_path, relative_path):
        """Get 7Z file contents."""
        if not PY7ZR_AVAILABLE:
            return {"error": "7Z support not available. Install 'py7zr' library."}

        try:
            with py7zr.SevenZipFile(abs_path, 'r') as szf:
                contents = []
                for member_info in szf.list():
                    contents.append({
                        "name": member_info.filename,
                        "is_dir": member_info.is_directory,
                        "size": member_info.uncompressed if hasattr(member_info, 'uncompressed') else 0,
                        "compressed_size": member_info.compressed if hasattr(member_info, 'compressed') else 0,
                        "date_time": member_info.creationtime if hasattr(member_info, 'creationtime') else None
                    })
                contents.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
            return {"success": True, "contents": contents, "archive_type": "7z", "archive_path": relative_path}
        except Exception as e:
            return {"error": f"Could not read 7Z file: {str(e)}"}

    def _get_tar_contents(self, abs_path, relative_path):
        """Get TAR file contents."""
        if not TARFILE_AVAILABLE:
            return {"error": "TAR support not available."}

        try:
            with tarfile.open(abs_path, 'r:*') as tf:
                contents = []
                for member_info in tf.getmembers():
                    contents.append({
                        "name": member_info.name,
                        "is_dir": member_info.isdir(),
                        "size": member_info.size,
                        "compressed_size": member_info.size,  # TAR doesn't compress individual files
                        "date_time": member_info.mtime if hasattr(member_info, 'mtime') else None
                    })
                contents.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
            return {"success": True, "contents": contents, "archive_type": "tar", "archive_path": relative_path}
        except Exception as e:
            return {"error": f"Could not read TAR file: {str(e)}"}

    # Keep the original get_zip_contents method for backward compatibility
    def get_zip_contents(self, zip_file_relative_path):
        """Lists the contents (filenames and directories) of a ZIP archive."""
        return self.get_archive_contents(zip_file_relative_path)

    def list_directory(self, sub_path=""):
        """Lists contents of a directory within the managed scope."""
        try:
            current_path = self._get_safe_path(sub_path)
        except PermissionError as e:
             # This error is specific from _get_safe_path
            return {"error": str(e)} # Will be caught by app.py for a 403

        if not os.path.exists(current_path):
            return {"error": f"Path does not exist: {current_path}"} 
        if not os.path.isdir(current_path):
            return {"error": f"Path is not a directory: {current_path}"} 

        items = []
        try:
            for item_name in os.listdir(current_path):
                item_path = os.path.join(current_path, item_name)
                item_type = "directory" if os.path.isdir(item_path) else "file"
                items.append({
                    "name": item_name,
                    "type": item_type,
                    "path": os.path.join(sub_path, item_name).replace('\\', '/') # Relative path for client
                })
        except OSError as e:
            print(f"ERROR: OSError when listing directory '{current_path}': {e}")
            return {"error": f"Cannot access directory contents: {e.strerror}"} 
        
        # Sort: directories first, then by name
        items.sort(key=lambda x: (x['type'] != 'directory', x['name'].lower()))
        return {"path": sub_path.replace('\\', '/'), "items": items}

    def get_file_content(self, file_path):
        """Reads content of a file within the managed scope."""
        abs_file_path = self._get_safe_path(file_path)
        if not os.path.isfile(abs_file_path):
            return {"error": "File not found."}
        try:
            with open(abs_file_path, 'r', encoding='utf-8') as f:
                return {"content": f.read()}
        except Exception as e:
            return {"error": f"Could not read file: {str(e)}"}

    def save_file_content(self, file_path, content):
        """Saves content to a file within the managed scope."""
        abs_file_path = self._get_safe_path(file_path)
        try:
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(abs_file_path), exist_ok=True)
            with open(abs_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "message": "File saved."}
        except PermissionError as e:
             raise e # Re-raise to be caught by app route
        except Exception as e:
            return {"error": f"Could not save file: {str(e)}"}

    def create_folder(self, folder_path):
        """Creates a new folder within the managed scope."""
        abs_folder_path = self._get_safe_path(folder_path)
        if os.path.exists(abs_folder_path):
            return {"error": "Folder or file already exists."}
        try:
            os.makedirs(abs_folder_path)
            return {"success": True, "message": "Folder created."}
        except Exception as e:
            return {"error": f"Could not create folder: {str(e)}"}

    def delete_item(self, item_path):
        """Deletes a file or folder within the managed scope."""
        abs_item_path = self._get_safe_path(item_path)
        if not os.path.exists(abs_item_path):
            return {"error": "Item not found."}
        try:
            if os.path.isfile(abs_item_path):
                os.remove(abs_item_path)
            elif os.path.isdir(abs_item_path):
                shutil.rmtree(abs_item_path) # Danger: Recursive delete
            return {"success": True, "message": "Item deleted."}
        except PermissionError as e:
             raise e # Re-raise
        except Exception as e:
            return {"error": f"Could not delete item: {str(e)}"}
            
    def batch_delete_items(self, item_paths):
        """Deletes multiple files or folders within the managed scope."""
        results = []
        all_successful = True
        for item_path in item_paths:
            try:
                abs_item_path = self._get_safe_path(item_path) # Validate each path
                if not os.path.exists(abs_item_path):
                    results.append({"path": item_path, "status": "error", "message": "Item not found."})
                    all_successful = False
                    continue
                if os.path.isfile(abs_item_path):
                    os.remove(abs_item_path)
                elif os.path.isdir(abs_item_path):
                    shutil.rmtree(abs_item_path)
                results.append({"path": item_path, "status": "success", "message": "Item deleted."})
            except PermissionError:
                results.append({"path": item_path, "status": "error", "message": "Permission denied."})
                all_successful = False
            except Exception as e:
                results.append({"path": item_path, "status": "error", "message": str(e)})
                all_successful = False
        
        return {"success": all_successful, "results": results}


    def upload_file(self, file_storage, upload_sub_path=""):
        """Saves an uploaded file to the specified sub_path within the managed directory."""
        if not file_storage:
            return {"error": "No file provided."}
        
        filename = secure_filename(file_storage.filename)
        if not filename: # Empty filename after secure_filename (e.g. just "..")
             return {"error": "Invalid filename."}

        target_folder = self._get_safe_path(upload_sub_path)
        if not os.path.isdir(target_folder): # Ensure target_folder is a directory and exists
            try:
                os.makedirs(target_folder, exist_ok=True)
            except Exception as e:
                 return {"error": f"Could not create upload directory: {str(e)}"}

        abs_file_path = os.path.join(target_folder, filename)

        # Security: Check again to ensure the final path is still within managed_dir
        # This is somewhat redundant if _get_safe_path and secure_filename are robust,
        # but good for defense in depth.
        if not os.path.normpath(abs_file_path).startswith(self.managed_dir):
            return {"error": "Upload path is outside managed directory."}

        try:
            file_storage.save(abs_file_path)
            return {"success": True, "message": f"File '{filename}' uploaded to '{upload_sub_path}'.", "filename": filename, "path": os.path.join(upload_sub_path, filename).replace('\\','/')}
        except Exception as e:
            return {"error": f"Could not save uploaded file: {str(e)}"}

    def _setup_cleanup_timer(self):
        """Setup periodic cleanup of abandoned chunked uploads."""
        def cleanup_abandoned_uploads():
            while True:
                time.sleep(300)  # Run every 5 minutes
                self._cleanup_abandoned_uploads()
        
        cleanup_thread = threading.Thread(target=cleanup_abandoned_uploads, daemon=True)
        cleanup_thread.start()

    def _cleanup_abandoned_uploads(self):
        """Clean up abandoned chunked uploads older than timeout."""
        config = get_config()
        timeout = config.get('upload', {}).get('chunk_timeout', 300)
        current_time = time.time()
        
        with self.upload_lock:
            abandoned_uploads = []
            for upload_id, upload_info in self.chunk_uploads.items():
                if current_time - upload_info['last_activity'] > timeout:
                    abandoned_uploads.append(upload_id)
            
            for upload_id in abandoned_uploads:
                self._cleanup_upload_chunks(upload_id)

    def _cleanup_upload_chunks(self, upload_id):
        """Clean up temporary files for a specific upload."""
        if upload_id not in self.chunk_uploads:
            return
        
        upload_info = self.chunk_uploads[upload_id]
        temp_dir = upload_info.get('temp_dir')
        
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"Warning: Could not clean up temp directory {temp_dir}: {e}")
        
        del self.chunk_uploads[upload_id]

    def upload_chunk(self, chunk_data, upload_id, chunk_index, total_chunks, filename, upload_path=""):
        """Handle individual chunk uploads for large files."""
        with self.upload_lock:
            # Initialize upload info if this is the first chunk
            if upload_id not in self.chunk_uploads:
                # Check file size limit for chunked uploads
                config = get_config()
                upload_config = config.get('upload', {})
                max_file_size_gb = upload_config.get('max_file_size_gb', 8)
                chunk_size_mb = upload_config.get('chunk_size_mb', 10)
                
                # Estimate total file size from chunk count and chunk size
                estimated_file_size_bytes = total_chunks * chunk_size_mb * 1024 * 1024
                max_file_size_bytes = max_file_size_gb * 1024 * 1024 * 1024
                
                if estimated_file_size_bytes > max_file_size_bytes:
                    return {"error": f"Estimated file size ({estimated_file_size_bytes / (1024*1024*1024):.2f}GB) exceeds maximum allowed size of {max_file_size_gb}GB."}
                
                temp_dir = tempfile.mkdtemp(prefix=f"chunk_upload_{upload_id}_")
                self.chunk_uploads[upload_id] = {
                    'temp_dir': temp_dir,
                    'filename': filename,
                    'upload_path': upload_path,
                    'total_chunks': total_chunks,
                    'chunks_received': set(),
                    'last_activity': time.time()
                }
            
            upload_info = self.chunk_uploads[upload_id]
            upload_info['last_activity'] = time.time()
            
            # Save chunk to temporary file
            chunk_filename = f"chunk_{chunk_index:06d}"
            chunk_path = os.path.join(upload_info['temp_dir'], chunk_filename)
            
            try:
                chunk_data.save(chunk_path)
                upload_info['chunks_received'].add(chunk_index)
            except Exception as e:
                return {"error": f"Failed to save chunk {chunk_index}: {str(e)}"}
            
            # Check if all chunks have been received
            if len(upload_info['chunks_received']) == total_chunks:
                # Assemble the final file
                result = self._assemble_chunks(upload_id)
                if result.get('success'):
                    self._cleanup_upload_chunks(upload_id)
                    return {
                        "success": True, 
                        "completed": True, 
                        "message": f"File '{filename}' uploaded successfully.",
                        "filename": filename,
                        "path": result.get('path')
                    }
                else:
                    self._cleanup_upload_chunks(upload_id)
                    return result
            else:
                # Return progress info
                progress = (len(upload_info['chunks_received']) / total_chunks) * 100
                return {
                    "success": True, 
                    "completed": False, 
                    "progress": progress,
                    "chunks_received": len(upload_info['chunks_received']),
                    "total_chunks": total_chunks
                }

    def _assemble_chunks(self, upload_id):
        """Assemble all chunks into the final file."""
        if upload_id not in self.chunk_uploads:
            return {"error": "Upload information not found"}
        
        upload_info = self.chunk_uploads[upload_id]
        temp_dir = upload_info['temp_dir']
        filename = secure_filename(upload_info['filename'])
        upload_path = upload_info['upload_path']
        total_chunks = upload_info['total_chunks']
        
        if not filename:
            return {"error": "Invalid filename"}
        
        # Prepare target directory
        target_folder = self._get_safe_path(upload_path)
        if not os.path.isdir(target_folder):
            try:
                os.makedirs(target_folder, exist_ok=True)
            except Exception as e:
                return {"error": f"Could not create upload directory: {str(e)}"}
        
        abs_file_path = os.path.join(target_folder, filename)
        
        # Security check
        if not os.path.normpath(abs_file_path).startswith(self.managed_dir):
            return {"error": "Upload path is outside managed directory"}
        
        try:
            # Assemble chunks in order
            with open(abs_file_path, 'wb') as output_file:
                for chunk_index in range(total_chunks):
                    chunk_filename = f"chunk_{chunk_index:06d}"
                    chunk_path = os.path.join(temp_dir, chunk_filename)
                    
                    if not os.path.exists(chunk_path):
                        return {"error": f"Missing chunk {chunk_index}"}
                    
                    with open(chunk_path, 'rb') as chunk_file:
                        shutil.copyfileobj(chunk_file, output_file)
            
            final_path = os.path.join(upload_path, filename).replace('\\', '/')
            return {
                "success": True, 
                "message": f"File '{filename}' assembled successfully.",
                "filename": filename,
                "path": final_path
            }
        except Exception as e:
            return {"error": f"Failed to assemble file: {str(e)}"}

    def cancel_chunked_upload(self, upload_id):
        """Cancel a chunked upload and clean up temporary files."""
        with self.upload_lock:
            if upload_id in self.chunk_uploads:
                self._cleanup_upload_chunks(upload_id)
                return {"success": True, "message": "Upload cancelled and cleaned up"}
            else:
                return {"success": True, "message": "Upload not found or already completed"}

    def zip_items(self, items_to_zip, archive_name, output_sub_path=""):
        """
        Zips specified files and folders into an archive.
        items_to_zip: list of relative paths (to managed_dir) of items to zip.
        archive_name: name of the zip file (e.g., 'backup.zip').
        output_sub_path: relative path within managed_dir where the zip file will be saved.
        """
        if not archive_name.lower().endswith('.zip'):
            archive_name += '.zip'
        
        abs_output_dir = self._get_safe_path(output_sub_path)
        if not os.path.isdir(abs_output_dir):
            try:
                os.makedirs(abs_output_dir, exist_ok=True)
            except Exception as e:
                return {"error": f"Could not create output directory for zip: {str(e)}"}

        abs_archive_path = os.path.join(abs_output_dir, secure_filename(archive_name))

        # Check if archive path is safe
        if not os.path.normpath(abs_archive_path).startswith(self.managed_dir):
            return {"error": "Archive path is outside managed directory."}

        try:
            with zipfile.ZipFile(abs_archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for item_rel_path in items_to_zip:
                    abs_item_path = self._get_safe_path(item_rel_path)
                    if not os.path.exists(abs_item_path):
                        # Log or report missing item
                        continue 
                    
                    if os.path.isfile(abs_item_path):
                        # Add file with its relative path within the zip
                        zf.write(abs_item_path, arcname=os.path.basename(item_rel_path))
                    elif os.path.isdir(abs_item_path):
                        # Add folder and its contents
                        for root, _, files in os.walk(abs_item_path):
                            for file in files:
                                file_abs_path = os.path.join(root, file)
                                # arcname should be relative to the item_rel_path base
                                arcname = os.path.join(os.path.basename(item_rel_path), os.path.relpath(file_abs_path, abs_item_path))
                                zf.write(file_abs_path, arcname=arcname)
            return {"success": True, "message": f"Archive '{archive_name}' created.", "archive_path": os.path.join(output_sub_path, archive_name).replace('\\','/')}
        except PermissionError as e:
            raise e
        except Exception as e:
            return {"error": f"Could not create zip archive: {str(e)}"}

    def unzip_file(self, zip_file_path, extract_to_sub_path=""):
        """Unzips a file into the specified sub_path within the managed directory."""
        abs_zip_file_path = self._get_safe_path(zip_file_path)

        if not os.path.isfile(abs_zip_file_path) or not zipfile.is_zipfile(abs_zip_file_path):
            return {"error": "Invalid or not a zip file."}

        # Determine extraction path: if extract_to_sub_path is empty, extract in same dir as zip
        if extract_to_sub_path:
            abs_extract_path = self._get_safe_path(extract_to_sub_path)
        else:
            abs_extract_path = os.path.dirname(abs_zip_file_path) 

        if not os.path.isdir(abs_extract_path):
            try:
                os.makedirs(abs_extract_path, exist_ok=True)
            except Exception as e:
                 return {"error": f"Could not create extraction directory: {str(e)}"}
        
        # Security: Ensure extraction path is safe
        if not os.path.normpath(abs_extract_path).startswith(self.managed_dir):
            return {"error": "Extraction path is outside managed directory."}
            
        try:
            with zipfile.ZipFile(abs_zip_file_path, 'r') as zf:
                # Security: Check for malicious file paths in zip (e.g., '..', absolute paths)
                for member in zf.namelist():
                    member_path = os.path.normpath(member)
                    if member_path.startswith("..") or os.path.isabs(member_path):
                        return {"error": f"Zip file contains potentially unsafe path: {member}"}
                
                zf.extractall(abs_extract_path)
            return {"success": True, "message": f"File '{os.path.basename(zip_file_path)}' unzipped to '{os.path.relpath(abs_extract_path, self.managed_dir)}'."}
        except zipfile.BadZipFile:
            return {"error": "Bad zip file."}
        except PermissionError as e:
            raise e
        except Exception as e:
            return {"error": f"Could not unzip file: {str(e)}"}

    def rename_item(self, current_relative_path, new_name_unsafe):
        """Renames a file or folder within the managed scope."""
        if not new_name_unsafe or not new_name_unsafe.strip():
            return {"error": "New name cannot be empty."}

        # Custom filename validation that allows spaces but ensures security
        new_name_stripped = new_name_unsafe.strip()
        # Remove dangerous characters but keep spaces and common filename characters
        import re
        new_name_safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', new_name_stripped)
        # Prevent names that are just dots or empty after cleaning
        if not new_name_safe or new_name_safe in ('.', '..'):
             return {"error": f"Invalid new name after sanitization: '{new_name_unsafe}'."}

        try:
            abs_current_path = self._get_safe_path(current_relative_path)
        except PermissionError as e:
            return {"error": str(e)}
        
        if not os.path.exists(abs_current_path):
            return {"error": f"Item to rename not found: '{current_relative_path}'"}

        current_dir = os.path.dirname(abs_current_path)
        abs_new_path = os.path.join(current_dir, new_name_safe)

        # Double check the new path is still safe (should be, as current_dir is from a safe path)
        if not os.path.normpath(abs_new_path).startswith(self.managed_dir):
            # This should theoretically not be hit if _get_safe_path and secure_filename are robust
            print(f"SECURITY ALERT: Rename attempt resulted in path '{abs_new_path}' outside managed directory.")
            return {"error": "Rename results in an invalid path."}

        if os.path.exists(abs_new_path):
            return {"error": f"An item named '{new_name_safe}' already exists in this location."}

        try:
            os.rename(abs_current_path, abs_new_path)
            new_relative_path = os.path.join(os.path.dirname(current_relative_path), new_name_safe).replace('\\', '/')
            return {"success": True, "message": f"Item renamed to '{new_name_safe}'.", "new_path": new_relative_path, "new_name": new_name_safe}
        except OSError as e:
            print(f"ERROR: OSError during rename from '{abs_current_path}' to '{abs_new_path}': {e}")
            return {"error": f"Could not rename item: {e.strerror}"}
        except Exception as e:
            print(f"ERROR: Unexpected exception during rename: {e}")
            return {"error": "An unexpected error occurred during rename."}

# Example usage (for testing)
if __name__ == '__main__':
    fm = FileManager()
    # Ensure managed_files directory exists for testing
    if not os.path.exists(fm.managed_dir):
        os.makedirs(fm.managed_dir)

    # Test listing
    print("Listing root:", fm.list_directory())
    
    # Test folder creation
    print("Creating folder 'test_folder':", fm.create_folder("test_folder"))
    print("Listing root after folder create:", fm.list_directory())
    print("Listing 'test_folder':", fm.list_directory("test_folder"))

    # Test file save
    print("Saving file 'test_folder/test.txt':", fm.save_file_content("test_folder/test.txt", "Hello World!"))
    print("Getting content of 'test_folder/test.txt':", fm.get_file_content("test_folder/test.txt"))

    # Test zip
    # Create some files to zip
    fm.save_file_content("file1.txt", "content1")
    fm.save_file_content("test_folder/file2.txt", "content2")
    print("Zipping ['file1.txt', 'test_folder'] to 'archive.zip':", fm.zip_items(['file1.txt', 'test_folder'], 'archive.zip', ''))
    
    # Test unzip
    if os.path.exists(os.path.join(fm.managed_dir, 'archive.zip')):
        print("Unzipping 'archive.zip' to 'unzipped_stuff':", fm.unzip_file('archive.zip', 'unzipped_stuff'))
        print("Listing 'unzipped_stuff':", fm.list_directory('unzipped_stuff'))


    # Test delete
    # print("Deleting 'test_folder/test.txt':", fm.delete_item("test_folder/test.txt"))
    # print("Deleting 'test_folder':", fm.delete_item("test_folder"))
    # print("Deleting 'file1.txt':", fm.delete_item("file1.txt"))
    # print("Deleting 'archive.zip':", fm.delete_item("archive.zip"))
    # print("Deleting 'unzipped_stuff':", fm.delete_item("unzipped_stuff"))
    # print("Listing root after cleanup:", fm.list_directory())

    # Test path traversal attempt (should fail or be contained)
    try:
        print("Attempting path traversal with '../test.txt':")
        # This should use _get_safe_path and thus be contained or raise error
        # For example, saving:
        # result = fm.save_file_content("../outside_file.txt", "Attempting path traversal")
        # print(result)
        # For example, listing:
        # result = fm.list_directory("../../") # This should be caught by _get_safe_path
        # print(result)
        
        # More direct test of _get_safe_path
        print("Safe path for 'some/path':", fm._get_safe_path("some/path"))
        print("Safe path for '/some/path':", fm._get_safe_path("/some/path")) # Should strip leading /
        print("Safe path for '../above':") # This should raise PermissionError
        # print(fm._get_safe_path("../above"))
    except PermissionError as e:
        print(f"Caught expected error: {e}")
    except Exception as e:
        print(f"Caught unexpected error: {e}") 