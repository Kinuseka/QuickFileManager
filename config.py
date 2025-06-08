import yaml
import os

CONFIG_FILE = "config.yml"
DEFAULT_CONFIG = {
    "app_password": "change_me_please",
    "managed_directory": "./managed_files",
    "users": {},
    "upload": {
        "enable_chunked_upload": True,
        "chunk_size_mb": 10,  # Size of each chunk in MB
        "max_concurrent_chunks": 3,  # Maximum concurrent chunks per file
        "chunk_timeout": 300,  # Timeout for chunk upload in seconds
        "max_file_size_gb": 8  # Maximum file size limit in GB
    }
}

def get_config():
    """Loads configuration from YAML file, ensuring defaults and directory status."""
    if not os.path.exists(CONFIG_FILE):
        print(f"INFO: '{CONFIG_FILE}' not found. Creating a default one.")
        save_config(DEFAULT_CONFIG) 
        # Also ensure the default managed directory is created here for the very first run
        try:
            default_dir_to_check = DEFAULT_CONFIG["managed_directory"]
            if not os.path.isabs(default_dir_to_check):
                 path_for_creation_check = os.path.join(os.getcwd(), default_dir_to_check)
            else:
                 path_for_creation_check = default_dir_to_check
            path_for_creation_check = os.path.normpath(path_for_creation_check)

            if not os.path.exists(path_for_creation_check):
                os.makedirs(path_for_creation_check)
                print(f"INFO: Default managed directory '{path_for_creation_check}' created.")
            elif not os.path.isdir(path_for_creation_check):
                 print(f"WARNING: Default managed directory path '{path_for_creation_check}' exists but is not a directory.")
        except OSError as e:
            print(f"ERROR: Could not create default managed directory '{path_for_creation_check}': {e}")
        config = DEFAULT_CONFIG.copy() # Use a copy of defaults
    else:
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config is None: # Handle empty or invalid YAML file
                    print(f"WARNING: '{CONFIG_FILE}' is empty or invalid. Loading default configuration.")
                    config = {}
        except yaml.YAMLError as e:
            print(f"ERROR: Error parsing '{CONFIG_FILE}': {e}. Loading default configuration.")
            config = DEFAULT_CONFIG.copy()
        except Exception as e:
            print(f"ERROR: An unexpected error occurred while loading '{CONFIG_FILE}': {e}. Loading default configuration.")
            config = DEFAULT_CONFIG.copy()

    # Merge with defaults to ensure all keys are present
    final_config = DEFAULT_CONFIG.copy()
    if isinstance(config, dict):
        final_config.update(config)
    else: # If config wasn't a dict for some reason
        print(f"WARNING: Configuration loaded from '{CONFIG_FILE}' was not a dictionary. Using defaults.")
        config = final_config # Ensure config is a dict for below checks

    # Validate and ensure managed_directory logic
    managed_dir_path_from_config = final_config.get("managed_directory")

    if not managed_dir_path_from_config or not isinstance(managed_dir_path_from_config, str) or not managed_dir_path_from_config.strip():
        print(f"WARNING: 'managed_directory' in '{CONFIG_FILE}' is missing, empty, or not a string. Using default: '{DEFAULT_CONFIG['managed_directory']}'")
        final_config["managed_directory"] = DEFAULT_CONFIG["managed_directory"]
        managed_dir_path_to_check = DEFAULT_CONFIG["managed_directory"]
    else:
        managed_dir_path_to_check = managed_dir_path_from_config.strip()
        final_config["managed_directory"] = managed_dir_path_to_check # Store the stripped version

    if not os.path.isabs(managed_dir_path_to_check):
        path_for_creation_check = os.path.join(os.getcwd(), managed_dir_path_to_check)
    else:
        path_for_creation_check = managed_dir_path_to_check
    path_for_creation_check = os.path.normpath(path_for_creation_check)

    # This check is for informational purposes during get_config, FileManager will do its own robust check & creation
    if not os.path.exists(path_for_creation_check):
        print(f"INFO: Managed directory for '{CONFIG_FILE}' (resolved to '{path_for_creation_check}' from value '{managed_dir_path_to_check}') does not exist yet. FileManager will attempt to create it.")
    elif not os.path.isdir(path_for_creation_check):
        print(f"ERROR: Path for managed_directory in '{CONFIG_FILE}' ('{path_for_creation_check}' from value '{managed_dir_path_to_check}') exists but is NOT a directory.")
    else:
        print(f"INFO: Managed directory for '{CONFIG_FILE}' ('{path_for_creation_check}' from value '{managed_dir_path_to_check}') found and is a directory.")
            
    return final_config

def save_config(config_data):
    """Saves configuration to YAML file."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False)
    except Exception as e:
        print(f"ERROR: Error saving config file '{CONFIG_FILE}': {e}")

if __name__ == '__main__':
    print("Running config.py directly for testing.")
    cfg = get_config()
    print("Current Configuration Loaded:", cfg)
    # Example of modifying and saving (be careful with this in a live app)
    # cfg["app_password"] = "new_password_test"
    # save_config(cfg)
    # print("Updated Configuration after save:", get_config()) 