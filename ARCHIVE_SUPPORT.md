# Archive Support Documentation

The File Manager now supports previewing and extracting multiple archive formats with minimal setup required.

## Supported Archive Formats

### Built-in Support (No Additional Installation)
These formats work out of the box with Python's standard library:

- **ZIP** files (`.zip`) - Full support
- **TAR** files (`.tar`, `.tar.gz`, `.tar.bz2`, `.tar.xz`, `.tgz`, `.tbz2`) - Full support
- **Gzip** files (`.gz`) - Full support
- **Bzip2** files (`.bz2`) - Full support
- **XZ** files (`.xz`) - Full support

### Optional Support (Requires Additional Libraries)
These formats require installing additional Python packages:

- **RAR** files (`.rar`) - Requires `rarfile` library + `unrar` utility
- **7Z** files (`.7z`) - Requires `py7zr` library (pure Python)

## Features

### Archive Preview
- **File Listing**: View all files and directories within an archive
- **Size Information**: See original and compressed file sizes
- **Icon Support**: Files display appropriate icons based on their type
- **Multiple Formats**: Works with all supported archive types
- **Error Handling**: Graceful error messages for unsupported or corrupted archives

### Archive Extraction
- **Smart Extraction**: Archives can be extracted to custom directories
- **Format Detection**: Automatically detects archive type from file extension
- **Safe Extraction**: Prevents path traversal attacks
- **Progress Feedback**: Visual feedback during extraction process

## Installation

### Basic Installation (Built-in Formats Only)
No additional installation required. ZIP, TAR, and compressed TAR formats work immediately.

### Extended Format Support

#### Option 1: Automatic Installation
Run the provided installation script:
```bash
python install_archive_support.py
```

#### Option 2: Manual Installation
Install the optional libraries manually:
```bash
pip install -r requirements-archive.txt
```

#### Option 3: Individual Package Installation
Install specific packages as needed:
```bash
# For 7Z support
pip install py7zr>=0.20.0

# For RAR support  
pip install rarfile>=4.0
```

### Platform-Specific Setup for RAR Support

RAR support requires the `unrar` utility to be installed on your system:

#### Windows
1. Download and install WinRAR from https://www.win-rar.com/download.html
2. Add WinRAR installation directory to your PATH environment variable
   (Usually: `C:\Program Files\WinRAR\`)

#### macOS
Using Homebrew:
```bash
brew install unrar
```

Using MacPorts:
```bash
sudo port install unrar
```

#### Linux
Ubuntu/Debian:
```bash
sudo apt-get install unrar
```

CentOS/RHEL/Fedora:
```bash
sudo yum install unrar
# or for newer versions:
sudo dnf install unrar
```

Arch Linux:
```bash
sudo pacman -S unrar
```

## Usage

### Previewing Archives
1. Navigate to any supported archive file in the file manager
2. Click on the archive file to select it
3. Click "Preview" or double-click to open the preview
4. The archive contents will be displayed with file sizes and compression information

### Extracting Archives
1. Right-click on any supported archive file
2. Select "Extract" from the context menu
3. Choose the extraction directory (or leave blank for current directory)
4. Click "Extract" to begin the process

### File Icons
Archive files display with the archive icon (📦) and are clearly distinguishable from regular files.

## Troubleshooting

### "RAR support not available" Error
- Ensure `rarfile` package is installed: `pip install rarfile`
- Verify `unrar` utility is installed and accessible in PATH
- On Windows, restart your terminal/IDE after adding WinRAR to PATH

### "7Z support not available" Error
- Install the `py7zr` package: `pip install py7zr`
- This is a pure Python library and should work on all platforms

### "Unsupported archive format" Error
- Check if the file extension is supported
- Verify the file is not corrupted
- For less common formats, consider converting to ZIP or TAR

### Preview Shows "Error loading archive contents"
- File may be corrupted
- Insufficient permissions to read the file
- Archive may be password-protected (not supported)
- Missing required libraries for that format

## Technical Details

### Archive Detection
The system uses file extensions to determine archive types:
- `.zip` → ZIP format
- `.rar` → RAR format  
- `.7z` → 7Z format
- `.tar`, `.tar.gz`, `.tar.bz2`, `.tar.xz`, `.tgz`, `.tbz2` → TAR formats

### Security Considerations
- **Path Traversal Protection**: Prevents extraction outside the managed directory
- **Safe File Paths**: Validates all file paths within archives
- **Size Limits**: Reasonable limits on archive processing to prevent DoS
- **Permission Checks**: Respects file system permissions

### Performance
- **Lazy Loading**: Archive contents are loaded only when previewed
- **Memory Efficient**: Streams large archives without loading entirely into memory
- **Caching**: Archive metadata is cached for repeated access

### API Endpoints
- `GET /api/archive/contents?path=<path>` - Get archive contents
- `POST /api/unzip` - Extract archive (legacy endpoint, works with all formats)

## Contributing

To add support for additional archive formats:
1. Add format detection logic in `FileManager._get_archive_type()`
2. Implement format-specific handler method
3. Update the JavaScript `isArchive()` function
4. Add appropriate file icons
5. Update documentation

## License

Archive support functionality is part of the File Manager application and follows the same license terms. 