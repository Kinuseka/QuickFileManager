document.addEventListener('DOMContentLoaded', () => {
    const fileList = document.getElementById('file-list');
    const currentPathDisplay = document.getElementById('current-path-display');
    const goUpButton = document.getElementById('go-up-button');
    const logoutButton = document.getElementById('logout-button');
    const userCountDisplay = document.getElementById('user-count-display');
    const activityLogList = document.getElementById('activity-log-list');
    const toggleDarkModeButton = document.getElementById('toggle-dark-mode');

    const uploadButton = document.getElementById('upload-button');
    const fileUploadInput = document.getElementById('file-upload-input');
    const createFolderButton = document.getElementById('create-folder-button');
    const createFileButton = document.getElementById('create-file-button');
    const deleteSelectedButton = document.getElementById('delete-selected-button');
    const zipSelectedButton = document.getElementById('zip-selected-button');

    const filePreviewArea = document.getElementById('file-preview-area');
    const editingFilenameDisplay = document.getElementById('editing-filename');
    const fileContentEditor = document.getElementById('file-content-editor');
    const saveFileButton = document.getElementById('save-file-button');
    const closePreviewButton = document.getElementById('close-preview-button');

    const imageZoomModal = document.getElementById('image-zoom-modal');
    const zoomedImage = document.getElementById('zoomed-image');
    const modalCaption = document.getElementById('modal-caption');
    const closeModalButton = document.querySelector('.close-modal-button');

    const uploadProgressArea = document.getElementById('upload-progress-area');

    const iframePreviewContainer = document.getElementById('iframe-preview-container');
    const iframePreviewElement = document.getElementById('iframe-preview-element');

    const selectAllButton = document.getElementById('select-all-button');

    const deleteConfirmationModal = document.getElementById('deleteConfirmationModal');
    const deleteModalMessage = document.getElementById('deleteModalMessage');
    const confirmDeleteButton = document.getElementById('confirmDelete');
    const cancelDeleteButton = document.getElementById('cancelDelete');
    const closeDeleteModalButton = document.getElementById('closeDeleteModal');

    const zipModal = document.getElementById('zipModal');
    const zipModalMessage = document.getElementById('zipModalMessage');
    const archiveNameInput = document.getElementById('archiveName');
    const deleteZippedFilesCheckbox = document.getElementById('deleteZippedFiles');
    const confirmZipButton = document.getElementById('confirmZip');
    const cancelZipButton = document.getElementById('cancelZip');
    const closeZipModalButton = document.getElementById('closeZipModal');

    const unzipModal = document.getElementById('unzipModal');
    const unzipModalMessage = document.getElementById('unzipModalMessage');
    const extractPathInput = document.getElementById('extractPath');
    const confirmUnzipButton = document.getElementById('confirmUnzip');
    const cancelUnzipButton = document.getElementById('cancelUnzip');
    const closeUnzipModalButton = document.getElementById('closeUnzipModal');

    let currentDirectory = '';
    let currentlyEditingPath = null;
    let selectedItems = new Set();
    let currentRenameOperation = null; // Global variable to track current rename operation
    let itemToDelete = null;
    let itemsToZip = null;
    let fileToUnzip = null;
    let isCheckboxSelectModeActive = false;
    const toggleSelectModeButton = document.getElementById('toggle-select-mode-button');

    const fileListContainer = document.getElementById('file-list-container');
    const dragOverlay = document.getElementById('drag-overlay');

    // --- Theme Toggle ---
    function applyTheme() {
        if (localStorage.getItem('theme') === 'light-mode') {
            document.body.classList.remove('dark-mode');
            document.body.classList.add('light-mode');
        } else {
            document.body.classList.remove('light-mode');
            document.body.classList.add('dark-mode');
        }
    }
    applyTheme(); // Apply theme on load

    if (toggleDarkModeButton) {
        toggleDarkModeButton.addEventListener('click', () => {
            if (document.body.classList.contains('dark-mode')) {
                localStorage.setItem('theme', 'light-mode');
            } else {
                localStorage.setItem('theme', 'dark-mode');
            }
            applyTheme();
        });
    }

    if (toggleSelectModeButton) {
        toggleSelectModeButton.addEventListener('click', () => {
            isCheckboxSelectModeActive = !isCheckboxSelectModeActive;
            
            if (isCheckboxSelectModeActive) {
                toggleSelectModeButton.classList.add('active');
                toggleSelectModeButton.innerHTML = '<i class="fas fa-mouse-pointer"></i> Click Mode';
            } else {
                toggleSelectModeButton.classList.remove('active');
                toggleSelectModeButton.innerHTML = '<i class="fas fa-tasks"></i> Select Items';
                // Clear all selections when returning to click mode
                clearAllSelections();
            }
            updateButtonVisibility(); // Update button visibility
            loadFiles(currentDirectory); // Reload files to show/hide checkboxes
        });
    }

    // --- API Helper ---
    async function fetchAPI(endpoint, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest' // To help server identify AJAX
            }
        };
        const config = { ...defaultOptions, ...options };
        if (options.body && typeof options.body !== 'string' && !(options.body instanceof FormData)) {
            config.body = JSON.stringify(options.body);
        }

        try {
            const response = await fetch(endpoint, config);
            if (response.status === 401) { // Unauthorized
                alert("Session expired or unauthorized. Redirecting to login.");
                window.location.href = '/login';
                return null;
            }
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: `HTTP error! status: ${response.status}` }));
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }
            return response.json();
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            showToast(`Error: ${error.message}`, 'error');
            return null;
        }
    }

    // --- File & Folder Listing ---
    async function loadFiles(path = '') {
        const data = await fetchAPI(`/api/files/${path}`);
        if (data && data.items) {
            currentDirectory = data.path || '';
            if (currentPathDisplay) currentPathDisplay.textContent = currentDirectory === '' ? '/' : `/${currentDirectory}`;
            if (fileList) fileList.innerHTML = ''; // Clear previous list

            // Sort: folders first, then by name
            data.items.sort((a, b) => {
                if (a.type === b.type) {
                    return a.name.localeCompare(b.name);
                }
                return a.type === 'directory' ? -1 : 1;
            });

            // If not root, create an '..' entry for parent directory
            if (currentDirectory !== '' && currentDirectory !== '/') {
                const parentItem = document.createElement('li');
                parentItem.className = 'folder-item navigation-item'; // Mark as navigation
                parentItem.innerHTML = '<div class="item-details"><i class="fas fa-arrow-left item-icon"></i> <span class="item-name">.. (Parent)</span></div>';
                
                // Make parent directory non-selectable
                parentItem.style.userSelect = 'none';
                parentItem.style.webkitUserSelect = 'none';
                parentItem.style.mozUserSelect = 'none';
                parentItem.style.msUserSelect = 'none';
                
                // Calculate parent path more robustly - use empty string as root (file manager expects this)
                const parentPath = currentDirectory.includes('/') 
                    ? currentDirectory.substring(0, currentDirectory.lastIndexOf('/'))
                    : '';
                    
                parentItem.onclick = () => loadFiles(parentPath);
                
                // Add drag and drop support for parent directory
                parentItem.addEventListener('dragover', handleDragOver);
                parentItem.addEventListener('dragleave', handleDragLeave);
                parentItem.addEventListener('drop', (e) => handleDrop(e, parentPath));
                

                
                if (fileList) fileList.appendChild(parentItem);
            }

            data.items.forEach(item => {
                const itemElement = document.createElement('li');
                itemElement.className = item.type === 'directory' ? 'folder-item' : 'file-item';
                itemElement.dataset.path = item.path;
                itemElement.dataset.name = item.name;
                itemElement.dataset.type = item.type;
                if (selectedItems.has(item.path)) { // Re-apply 'selected' class if item is in selection set
                    itemElement.classList.add('selected');
                }

                const itemDetails = document.createElement('div');
                itemDetails.className = 'item-details';

                // Add checkbox if in select mode
                if (isCheckboxSelectModeActive) {
                    const checkbox = document.createElement('input');
                    checkbox.type = 'checkbox';
                    checkbox.className = 'item-checkbox';
                    checkbox.dataset.path = item.path;
                    checkbox.checked = selectedItems.has(item.path);
                    checkbox.addEventListener('click', (e) => {
                        e.stopPropagation(); // Prevent item click event when clicking checkbox
                        toggleItemSelectionState(itemElement, item.path, checkbox.checked);
                    });
                    itemDetails.appendChild(checkbox);
                }

                const icon = document.createElement('i');
                const iconClass = item.type === 'directory' ? 'fa-folder' : getFileIcon(item.name);
                icon.className = `item-icon fas ${iconClass}`;
                itemDetails.appendChild(icon);

                const nameSpan = document.createElement('span');
                nameSpan.className = 'item-name';
                nameSpan.textContent = item.name;
                itemDetails.appendChild(nameSpan);
                itemElement.appendChild(itemDetails);

                const actionsWrapper = document.createElement('div');
                actionsWrapper.className = 'file-item-actions-wrapper';
                const ellipsisButton = document.createElement('button');
                ellipsisButton.className = 'ellipsis-button';
                ellipsisButton.innerHTML = '<i class="fas fa-ellipsis-v"></i>';
                const actionsDropdown = document.createElement('div');
                actionsDropdown.className = 'actions-dropdown';

                // --- RENAME --- 
                const renameButton = document.createElement('button');
                renameButton.innerHTML = '<i class="fas fa-edit"></i> Rename';
                renameButton.onclick = (e) => { 
                    e.stopPropagation(); 
                    closeAllDropdowns();
                    renameItem(item.path, item.name, item.type, itemElement); 
                };
                actionsDropdown.appendChild(renameButton);

                // --- DOWNLOAD (for files) / OPEN (for folders) --- 
                if (item.type === 'file') {
                    const downloadButton = document.createElement('button');
                    downloadButton.innerHTML = '<i class="fas fa-download"></i> Download';
                    downloadButton.onclick = (e) => {
                        e.stopPropagation();
                        closeAllDropdowns();
                        downloadFile(item.path, true);
                    };
                    actionsDropdown.appendChild(downloadButton);
                } else if (item.type === 'directory') {
                    const openButton = document.createElement('button');
                    openButton.innerHTML = '<i class="fas fa-folder-open"></i> Open';
                    openButton.onclick = (e) => {
                        e.stopPropagation();
                        closeAllDropdowns();
                        loadFiles(item.path);
                    };
                    actionsDropdown.appendChild(openButton);
                }

                // --- DELETE --- 
                const deleteButton = document.createElement('button');
                deleteButton.innerHTML = '<i class="fas fa-trash-alt"></i> Delete';
                deleteButton.onclick = (e) => {
                    e.stopPropagation();
                    closeAllDropdowns();
                    deleteItem(item.path, item.name, item.type);
                };
                actionsDropdown.appendChild(deleteButton);

                // --- EXTRACT (for archive files) ---
                if (item.type === 'file' && isArchive(item.name)) {
                    const extractButton = document.createElement('button');
                    extractButton.innerHTML = '<i class="fas fa-file-archive"></i> Extract';
                    extractButton.onclick = (e) => {
                        e.stopPropagation();
                        closeAllDropdowns();
                        showExtractModal(item.path);
                    };
                    actionsDropdown.appendChild(extractButton);
                }

                if (actionsDropdown.childElementCount > 0) {
                    actionsWrapper.appendChild(ellipsisButton);
                    document.body.appendChild(actionsDropdown); // Append dropdown to body for fixed positioning

                    ellipsisButton.addEventListener('click', (e) => {
                        e.stopPropagation(); 
                        const isActive = actionsDropdown.classList.contains('active');
                        
                        // Always close all dropdowns first. This simplifies state management.
                        closeAllDropdowns(); 
                        
                        if (!isActive) { // If it wasn't active, we are opening it.
                            const buttonRect = ellipsisButton.getBoundingClientRect();
                            // Position dropdown: attempt to position above, then to left, then below.
                            let top = buttonRect.top - actionsDropdown.offsetHeight - 5; // 5px margin
                            let left = buttonRect.left;

                            // Check if it goes off-screen top
                            if (top < 0) {
                                top = buttonRect.bottom + 5;
                            }
                            // Check if it goes off-screen right
                            if (left + actionsDropdown.offsetWidth > window.innerWidth) {
                                left = window.innerWidth - actionsDropdown.offsetWidth - 5; // 5px margin from edge
                            }
                             // Check if it goes off-screen left
                            if (left < 0) {
                                left = 5; // 5px margin from edge
                            }

                            actionsDropdown.style.left = `${left}px`;
                            actionsDropdown.style.top = `${top}px`;
                            
                            ellipsisButton.innerHTML = '<i class="fas fa-times"></i>';
                            actionsDropdown.classList.add('active');
                            actionsDropdown._associatedButton = ellipsisButton; // Store reference
                        }
                        // If it *was* active, closeAllDropdowns already handled it (and reset its icon).
                    });
                    itemElement.appendChild(actionsWrapper);
                } else {
                    itemElement.appendChild(actionsWrapper); 
                }

                // Handle single and double clicks differently
                let clickTimer = null;
                itemElement.addEventListener('click', function(e) {
                    if (e.target.type === 'checkbox' || e.target.closest('.ellipsis-button') || e.target.closest('.actions-dropdown')) {
                        return; 
                    }
                    
                    const isCtrlOrMeta = e.ctrlKey || e.metaKey;
                    
                    if (isCheckboxSelectModeActive || isCtrlOrMeta) {
                        // If using Ctrl/Cmd and not in select mode, enable it
                        if (!isCheckboxSelectModeActive && isCtrlOrMeta) {
                            isCheckboxSelectModeActive = true;
                            toggleSelectModeButton.classList.add('active');
                            toggleSelectModeButton.innerHTML = '<i class="fas fa-mouse-pointer"></i> Click Mode';
                            updateButtonVisibility();
                            // Instead of reloading which loses context, just add checkboxes dynamically
                            document.querySelectorAll('.file-item, .folder-item').forEach(item => {
                                if (!item.querySelector('.item-checkbox')) {
                                    const itemDetails = item.querySelector('.item-details');
                                    if (itemDetails) {
                                        const checkbox = document.createElement('input');
                                        checkbox.type = 'checkbox';
                                        checkbox.className = 'item-checkbox';
                                        checkbox.dataset.path = item.dataset.path;
                                        checkbox.checked = selectedItems.has(item.dataset.path);
                                        checkbox.addEventListener('click', (e) => {
                                            e.stopPropagation();
                                            toggleItemSelectionState(item, item.dataset.path, checkbox.checked);
                                        });
                                        // Insert checkbox as first child of itemDetails
                                        itemDetails.insertBefore(checkbox, itemDetails.firstChild);
                                    }
                                }
                            });
                        }
                        // Toggle selection state of clicked item
                        toggleItemSelectionState(itemElement, item.path, !selectedItems.has(item.path));
                        updateSelectionControls();
                    } else {
                        // Single click without Ctrl/Meta and not in checkbox mode: just select
                        clearAllSelections();
                        toggleItemSelectionState(itemElement, item.path, true);
                        updateSelectionControls();
                    }
                });

                // Handle double-click to open
                itemElement.addEventListener('dblclick', function(e) {
                    if (e.target.type === 'checkbox' || e.target.closest('.ellipsis-button') || e.target.closest('.actions-dropdown')) {
                        return; 
                    }
                    
                    // Clear the single-click timer if it exists
                    if (clickTimer) {
                        clearTimeout(clickTimer);
                        clickTimer = null;
                    }
                    
                    if (item.type === 'directory') {
                        loadFiles(item.path);
                    } else if (item.type === 'file') {
                        // Log the preview intent first
                        fetchAPI('/api/preview/intent', { 
                            method: 'POST', 
                            body: { path: item.path }
                        });
                        openFilePreview(item.path);
                    }
                });
                
                // Drag and Drop specific logic for items
                if (item.type === 'file') {
                    itemElement.setAttribute('draggable', true);
                    itemElement.addEventListener('dragstart', (e) => handleDragStart(e, item.path));
                } else if (item.type === 'directory') {
                    itemElement.setAttribute('draggable', true); 
                    itemElement.addEventListener('dragstart', (e) => handleDragStart(e, item.path));
                    itemElement.addEventListener('dragover', handleDragOver);
                    itemElement.addEventListener('dragleave', handleDragLeave);
                    itemElement.addEventListener('drop', (e) => handleDrop(e, item.path));
                }

                if (fileList) fileList.appendChild(itemElement);
            });
            updateSelectionControls(); // Fixed function name - Initial update after loading
        } else {
            if (currentPathDisplay) currentPathDisplay.textContent = `/${currentDirectory}`;
            if (fileList) fileList.innerHTML = '<p>Could not load files or directory is empty.</p>';
        }
        closeFilePreview(); // Close preview when navigating
    }

    // --- Item Selection ---
    function updateSelectionControls() {
        const hasSelection = selectedItems.size > 0;
        deleteSelectedButton.disabled = !hasSelection;
        zipSelectedButton.disabled = !hasSelection;
    }

    function clearAllSelections() {
        document.querySelectorAll('.file-item.selected, .folder-item.selected:not(.navigation-item)').forEach(el => {
            el.classList.remove('selected');
            const checkbox = el.querySelector('.item-checkbox');
            if (checkbox) checkbox.checked = false;
        });
        selectedItems.clear();
        updateSelectionControls(); // Fixed function name
    }
    
    // --- File Operations ---
    if (goUpButton) {
        goUpButton.addEventListener('click', () => {
            if (currentDirectory) {
                const parentPath = currentDirectory.substring(0, currentDirectory.lastIndexOf('/'));
                loadFiles(parentPath);
            }
        });
    }

    if (uploadButton && fileUploadInput) {
        uploadButton.addEventListener('click', () => fileUploadInput.click());
        fileUploadInput.addEventListener('change', async (event) => {
            const files = event.target.files;
            if (files.length === 0) return;

            if (files.length > 5) {
                showToast('You can upload a maximum of 5 files at a time.', 'error');
                fileUploadInput.value = '';
                return;
            }

            if (uploadProgressArea) uploadProgressArea.innerHTML = ''; // Clear previous progress bars
            let allUploadsSuccessful = true;
            let filesUploadedCount = 0;

            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                const fileId = `upload-${Date.now()}-${i}`;

                // Create progress bar elements for this file
                const progressItem = document.createElement('div');
                progressItem.classList.add('upload-progress-item');
                progressItem.id = fileId;
                
                const fileInfoSpan = document.createElement('span');
                fileInfoSpan.classList.add('file-info');
                fileInfoSpan.textContent = `${file.name} (${formatBytes(file.size)})`;

                const progressBarContainer = document.createElement('div');
                progressBarContainer.classList.add('progress-bar-container');
                const progressBar = document.createElement('div');
                progressBar.classList.add('progress-bar');
                progressBarContainer.appendChild(progressBar);

                const progressTextSpan = document.createElement('span');
                progressTextSpan.classList.add('progress-text');
                progressTextSpan.textContent = '0%';

                const uploadSpeedSpan = document.createElement('span');
                uploadSpeedSpan.classList.add('upload-speed');
                uploadSpeedSpan.textContent = '0 B/s';
                
                // Add close button
                const closeButton = document.createElement('button');
                closeButton.classList.add('upload-progress-close');
                closeButton.innerHTML = '×';
                closeButton.title = 'Close';
                closeButton.onclick = () => {
                    progressItem.style.transition = 'opacity 0.3s ease-out';
                    progressItem.style.opacity = '0';
                    setTimeout(() => {
                        if (progressItem.parentNode) {
                            progressItem.parentNode.removeChild(progressItem);
                        }
                    }, 300);
                };

                progressItem.appendChild(fileInfoSpan);
                progressItem.appendChild(progressBarContainer);
                progressItem.appendChild(progressTextSpan);
                progressItem.appendChild(uploadSpeedSpan);
                progressItem.appendChild(closeButton);
                if (uploadProgressArea) uploadProgressArea.appendChild(progressItem);

                // Upload this file
                const formData = new FormData();
                formData.append('file', file);
                formData.append('path', currentDirectory);
                
                const xhr = new XMLHttpRequest();
                let lastLoaded = 0;
                let lastTime = Date.now();

                xhr.upload.onprogress = function(e) {
                    if (e.lengthComputable) {
                        const percentComplete = Math.round((e.loaded / e.total) * 100);
                        progressBar.style.width = percentComplete + '%';
                        progressTextSpan.textContent = percentComplete + '%';

                        const currentTime = Date.now();
                        const deltaTime = (currentTime - lastTime) / 1000; // in seconds
                        const deltaLoaded = e.loaded - lastLoaded;
                        if (deltaTime > 0) {
                            const speed = deltaLoaded / deltaTime;
                            uploadSpeedSpan.textContent = `${formatBytes(speed)}/s`;
                        }
                        lastLoaded = e.loaded;
                        lastTime = currentTime;
                    }
                };

                xhr.onload = function() {
                    filesUploadedCount++;
                    if (xhr.status === 200) {
                        const response = JSON.parse(xhr.responseText);
                        if (response.success) {
                            progressTextSpan.textContent = 'Done!';
                            progressBar.style.backgroundColor = '#28a745'; // Green for success
                            // Auto-hide individual progress item after 5 seconds
                            setTimeout(() => {
                                progressItem.style.transition = 'opacity 1s ease-out';
                                progressItem.style.opacity = '0';
                                setTimeout(() => {
                                    if (progressItem.parentNode) {
                                        progressItem.parentNode.removeChild(progressItem);
                                    }
                                }, 1000);
                            }, 5000);
                            // showToast(`${file.name} uploaded successfully!`, 'success'); // Can be too noisy
                        } else {
                            allUploadsSuccessful = false;
                            progressTextSpan.textContent = 'Error!';
                            progressBar.style.backgroundColor = '#dc3545'; // Red for error
                            showToast(response.error || `Error uploading ${file.name}`, 'error');
                        }
                    } else {
                        allUploadsSuccessful = false;
                        progressTextSpan.textContent = 'Failed!';
                        progressBar.style.backgroundColor = '#dc3545'; // Red for server error
                        showToast(`Upload failed for ${file.name}: ${xhr.statusText}`, 'error');
                    }

                    if (filesUploadedCount === files.length) { // All files processed
                        // File list will be updated via socket events
                        if (allUploadsSuccessful) {
                            showToast(`${files.length} file(s) processed.`, 'success');
                        } else {
                            showToast('Some files failed to upload.', 'warning');
                        }
                        // Auto-hide upload progress after 10 seconds with fade effect
                        setTimeout(() => {
                            if (uploadProgressArea && uploadProgressArea.children.length > 0) {
                                // Add fade-out class to all progress items
                                Array.from(uploadProgressArea.children).forEach(progressItem => {
                                    progressItem.style.transition = 'opacity 1s ease-out';
                                    progressItem.style.opacity = '0';
                                });
                                
                                // Remove elements after fade animation completes
                                setTimeout(() => {
                                    if (uploadProgressArea) uploadProgressArea.innerHTML = '';
                                }, 1000); // Wait for 1s fade out to complete
                            }
                        }, 10000); // 10 second delay
                    }
                };

                xhr.onerror = function() {
                    filesUploadedCount++;
                    allUploadsSuccessful = false;
                    progressTextSpan.textContent = 'Network Error!';
                    progressBar.style.backgroundColor = '#dc3545';
                    showToast(`Network error during upload of ${file.name}.`, 'error');
                    
                    // Auto-hide individual progress item after 5 seconds for errors too
                    setTimeout(() => {
                        progressItem.style.transition = 'opacity 1s ease-out';
                        progressItem.style.opacity = '0';
                        setTimeout(() => {
                            if (progressItem.parentNode) {
                                progressItem.parentNode.removeChild(progressItem);
                            }
                        }, 1000);
                    }, 5000);
                    
                    if (filesUploadedCount === files.length) {
                        // File list will be updated via socket events
                        showToast('Some files failed due to network issues.', 'warning');
                        // Auto-hide upload progress after 10 seconds with fade effect
                        setTimeout(() => {
                            if (uploadProgressArea && uploadProgressArea.children.length > 0) {
                                // Add fade-out class to all progress items
                                Array.from(uploadProgressArea.children).forEach(progressItem => {
                                    progressItem.style.transition = 'opacity 1s ease-out';
                                    progressItem.style.opacity = '0';
                                });
                                
                                // Remove elements after fade animation completes
                                setTimeout(() => {
                                    if (uploadProgressArea) uploadProgressArea.innerHTML = '';
                                }, 1000); // Wait for 1s fade out to complete
                            }
                        }, 10000); // 10 second delay
                    }
                };

                xhr.open('POST', '/api/upload', true);
                // xhr.setRequestHeader('X-CSRFToken', csrfToken); // If using CSRF tokens
                xhr.send(formData);
            } // end for loop

            fileUploadInput.value = ''; // Reset input after initiating uploads
        });
    }

    if (createFolderButton) {
        createFolderButton.addEventListener('click', async () => {
            const folderName = prompt("Enter new folder name:");
            if (folderName) {
                const path = currentDirectory ? `${currentDirectory}/${folderName}` : folderName;
                const result = await fetchAPI('/api/create/folder', { method: 'POST', body: { path } });
                if (result && result.success) {
                    showToast(result.message, 'success');
                    // File list will be updated via socket events
                }
            }
        });
    }

    if (createFileButton) {
        createFileButton.addEventListener('click', async () => {
            const fileName = prompt("Enter new file name (e.g., text.txt):");
            if (fileName) {
                const path = currentDirectory ? `${currentDirectory}/${fileName}` : fileName;
                // Open in editor immediately (will save as new file)
                openFilePreview(path, true);
            }
        });
    }
    
    // --- File Preview Logic ---
    const textEditorContainer = document.getElementById('text-editor-container');
    const imagePreviewContainer = document.getElementById('image-preview-container');
    const imagePreviewElement = document.getElementById('image-preview-element');
    const videoPreviewContainer = document.getElementById('video-preview-container');
    const videoPreviewElement = document.getElementById('video-preview-element');
    const zipPreviewContainer = document.getElementById('zip-preview-container');
    const zipContentsList = document.getElementById('zip-contents-list');
    const genericPreviewMessage = document.getElementById('generic-preview-message');

    function getFileIconClass(filename) {
        const extension = filename.split('.').pop().toLowerCase();
        switch (extension) {
            case 'txt': return 'fa-file-alt';
            case 'doc': case 'docx': return 'fa-file-word';
            case 'xls': case 'xlsx': return 'fa-file-excel';
            case 'ppt': case 'pptx': return 'fa-file-powerpoint';
            case 'pdf': return 'fa-file-pdf';
            case 'zip': case 'rar': case '7z': case 'tar': case 'gz': case 'bz2': case 'xz': case 'tgz': case 'tbz2': return 'fa-file-archive';
            case 'jpg': case 'jpeg': case 'png': case 'gif': case 'bmp': case 'svg': return 'fa-file-image';
            case 'mp4': case 'mov': case 'avi': case 'wmv': case 'mkv': return 'fa-file-video';
            case 'mp3': case 'wav': case 'ogg': return 'fa-file-audio';
            case 'js': case 'html': case 'css': case 'py': case 'java': case 'c': case 'cpp': return 'fa-file-code';
            default: return 'fa-file'; // Generic file icon
        }
    }

    function isArchive(filename) {
        const ext = filename.toLowerCase();
        const archiveExtensions = ['.zip', '.rar', '.7z', '.tar', '.tar.gz', '.tar.bz2', '.tar.xz', '.tgz', '.tbz2', '.gz', '.bz2', '.xz'];
        return archiveExtensions.some(archiveExt => ext.endsWith(archiveExt));
    }

    function isPreviewable(filename) {
        const ext = filename.toLowerCase().split('.').pop();
        const textExtensions = ['txt', 'md', 'json', 'js', 'css', 'html', 'xml', 'csv', 'log', 'py', 'java', 'cpp', 'c', 'h', 'php', 'rb', 'go', 'rs', 'yml', 'yaml', 'ini', 'cfg', 'conf'];
        const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'];
        const videoExtensions = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv'];
        const officeExtensions = ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'];
        
        return textExtensions.includes(ext) || 
               imageExtensions.includes(ext) || 
               videoExtensions.includes(ext) || 
               officeExtensions.includes(ext) ||
               ext === 'pdf' ||
               isArchive(filename); // Add archive preview support
    }

    async function openFilePreview(filePath, isNewFile = false) {
        currentlyEditingPath = filePath;
        const fileName = filePath.split('/').pop();
        if(editingFilenameDisplay) editingFilenameDisplay.textContent = fileName;
        
        // Hide all preview containers first
        if(textEditorContainer) textEditorContainer.style.display = 'none';
        if(imagePreviewContainer) imagePreviewContainer.style.display = 'none';
        if(videoPreviewContainer) videoPreviewContainer.style.display = 'none';
        if(zipPreviewContainer) zipPreviewContainer.style.display = 'none';
        if(iframePreviewContainer) iframePreviewContainer.style.display = 'none'; // Hide new container
        if(genericPreviewMessage) genericPreviewMessage.style.display = 'none';
        if(filePreviewArea) filePreviewArea.style.display = 'block';

        const extension = fileName.split('.').pop().toLowerCase();
        const directFileUrl = `/download/${encodeURIComponent(filePath)}?context=preview&v=${Date.now()}`; // Add cache buster

        if (isNewFile && (['txt', 'md', 'json', 'js', 'css', 'html', 'xml', 'log', 'py', 'yml'].includes(extension) || !extension )) {
            if(textEditorContainer) textEditorContainer.style.display = 'block';
            if(fileContentEditor) fileContentEditor.value = ''; 
        } else if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'].includes(extension)) {
            if(imagePreviewContainer) imagePreviewContainer.style.display = 'block';
            if(imagePreviewElement) {
                imagePreviewElement.src = directFileUrl;
                imagePreviewElement.style.cursor = 'zoom-in';
                imagePreviewElement.onclick = () => {
                    if (imageZoomModal && zoomedImage && modalCaption) {
                        imageZoomModal.style.display = 'block';
                        zoomedImage.src = imagePreviewElement.src;
                        modalCaption.textContent = fileName;
                    }
                };
                imagePreviewElement.onerror = () => {
                    imagePreviewContainer.style.display = 'none';
                    genericPreviewMessage.style.display = 'block';
                    genericPreviewMessage.textContent = `Could not load image preview for ${fileName}. The file might be corrupted or not a valid image.`;
                };
            }
        } else if (['mp4', 'webm', 'ogg', 'mov', 'mkv'].includes(extension)) { 
            if(videoPreviewContainer) videoPreviewContainer.style.display = 'block';
            if(videoPreviewElement) {
                videoPreviewElement.src = directFileUrl; 
                videoPreviewElement.load();
                videoPreviewElement.onerror = () => {
                    videoPreviewContainer.style.display = 'none';
                    genericPreviewMessage.style.display = 'block';
                    genericPreviewMessage.textContent = `Could not load video preview for ${fileName}. The file might be corrupted or not a valid video format.`;
                };
            }
        } else if (isArchive(fileName)) {
            if(zipPreviewContainer) zipPreviewContainer.style.display = 'block';
            await loadArchiveContents(filePath);
        } else if (extension === 'pdf') {
            if(iframePreviewContainer && iframePreviewElement) {
                iframePreviewContainer.style.display = 'block';
                iframePreviewElement.src = directFileUrl;
            } else {
                 if(genericPreviewMessage) {
                    genericPreviewMessage.style.display = 'block';
                    genericPreviewMessage.textContent = `Preview component for PDF not found.`;
                }
            }
        } else if (['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'].includes(extension)) {
            if(iframePreviewContainer && iframePreviewElement) {
                iframePreviewContainer.style.display = 'block';
                const absoluteFileUrl = new URL(directFileUrl, window.location.origin).href;
                // Using Google Docs Viewer as an example
                const viewerUrl = `https://docs.google.com/gview?url=${encodeURIComponent(absoluteFileUrl)}&embedded=true`;
                iframePreviewElement.src = viewerUrl;
            } else {
                 if(genericPreviewMessage) {
                    genericPreviewMessage.style.display = 'block';
                    genericPreviewMessage.textContent = `Preview component for Office documents not found.`;
                }
            }
        } else if (['txt', 'md', 'json', 'js', 'css', 'html', 'xml', 'csv', 'log', 'py', 'java', 'cpp', 'c', 'h', 'php', 'rb', 'go', 'rs', 'yml', 'yaml', 'ini', 'cfg', 'conf'].includes(extension)) {
            if(textEditorContainer) textEditorContainer.style.display = 'block';
            const data = await fetchAPI(`/api/file/content?path=${encodeURIComponent(filePath)}`);
            if (fileContentEditor) {
                if (data && typeof data.content === 'string') {
                    fileContentEditor.value = data.content;
                } else {
                    fileContentEditor.value = 'Error loading file content or file is binary/too large for text editor.';
                    if(data && data.error) showToast(data.error, 'error');
                }
            }
        } else {
            if(genericPreviewMessage) {
                genericPreviewMessage.style.display = 'block';
                genericPreviewMessage.textContent = `Preview not available for this file type (${extension || 'unknown'}).`;
            }
        }
    }

    if (saveFileButton) {
        saveFileButton.addEventListener('click', async () => {
            if (currentlyEditingPath) {
                const content = fileContentEditor.value;
                const result = await fetchAPI('/api/file/content', {
                    method: 'POST',
                    body: { path: currentlyEditingPath, content }
                });
                if (result && result.success) {
                    showToast(result.message, 'success');
                    // Refresh will be handled by socket event
                    // Keep preview open if user wants to continue editing
                }
            }
        });
    }

    if (closePreviewButton) {
        closePreviewButton.addEventListener('click', closeFilePreview);
    }

    function closeFilePreview() {
        filePreviewArea.style.display = 'none';
        fileContentEditor.value = '';
        editingFilenameDisplay.textContent = '';
        currentlyEditingPath = null;
    }
    
    async function deleteSingleItem(itemPath) {
        if (confirm(`Are you sure you want to delete '${itemPath}'?`)) {
            const result = await fetchAPI('/api/delete', { method: 'POST', body: { path: itemPath } });
            if (result && result.success) {
                showToast(result.message, 'success');
                // Refresh will be handled by socket event
                selectedItems.delete(itemPath); // Remove from selection if it was there
                updateSelectionControls();
            }
        }
    }

    function showDeleteModal(path, name, type, isBatch = false) {
        itemToDelete = { path, name, type, isBatch }; // Store context
        if (deleteModalMessage) {
            if (isBatch) {
                deleteModalMessage.textContent = `Are you sure you want to delete ${selectedItems.size} selected item(s)?`;
            } else {
                deleteModalMessage.textContent = `Are you sure you want to delete ${type} "${name}"?`;
            }
        }
        if(deleteConfirmationModal) deleteConfirmationModal.style.display = 'flex'; // Use flex for centering modal content
    }

    function closeDeleteModal() {
        if(deleteConfirmationModal) deleteConfirmationModal.style.display = 'none';
        itemToDelete = null;
    }

    if (confirmDeleteButton) {
        confirmDeleteButton.addEventListener('click', async () => {
            if (itemToDelete) {
                if (itemToDelete.isBatch) {
                    // Perform batch delete
                    const pathsToDelete = Array.from(selectedItems);
                    const result = await fetchAPI('/api/batch-delete', { method: 'POST', body: { paths: pathsToDelete } });
                    if (result && result.success) {
                        showToast('Selected items deleted.', 'success');
                    } else if (result && result.results) {
                        const errors = result.results.filter(r => r.status === 'error').map(r => `${r.path}: ${r.message}`).join('\n');
                        if (errors) showToast(`Some items failed to delete:\n${errors}`, 'error');
                        else showToast('Selected items deleted (with some warnings).', 'warning');
                    }
                    // loadFiles(currentDirectory); // Will be handled by socket event
                    clearAllSelections();
                } else {
                    // Perform single item delete
                    const result = await fetchAPI('/api/delete', {
                        method: 'POST',
                        body: { path: itemToDelete.path }
                    });
                    if (result && result.success) {
                        showToast(`${itemToDelete.type} deleted successfully.`, 'success');
                        // loadFiles(currentDirectory); // Will be handled by socket event
                        // If the deleted item was selected, remove it from selections
                        if (selectedItems.has(itemToDelete.path)) {
                            selectedItems.delete(itemToDelete.path);
                            updateSelectionControls();
                        }
                    } else {
                        showToast(result.error || `Failed to delete ${itemToDelete.type}.`, 'error');
                    }
                }
            }
            closeDeleteModal();
        });
    }

    if (cancelDeleteButton) cancelDeleteButton.addEventListener('click', closeDeleteModal);
    if (closeDeleteModalButton) closeDeleteModalButton.addEventListener('click', closeDeleteModal);

    // Update deleteItem function to use the modal
    function deleteItem(itemPath, itemName, itemType) {
        showDeleteModal(itemPath, itemName, itemType);
    }

    // Update batch delete button event listener
    if (deleteSelectedButton) {
        deleteSelectedButton.addEventListener('click', () => {
            if (selectedItems.size === 0) return;
            showDeleteModal(null, null, null, true); // Pass true for isBatch
        });
    }

    function downloadFile(filePath, forceDownload = false) {
        // Use hidden iframe to avoid disrupting socket connections
        let downloadUrl = `/download/${encodeURIComponent(filePath)}`;
        if (forceDownload) {
            downloadUrl += '?force_download=true';
        }
        
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        iframe.src = downloadUrl;
        document.body.appendChild(iframe);
        
        // Clean up iframe after download starts
        setTimeout(() => {
            if (iframe.parentNode) {
                document.body.removeChild(iframe);
            }
        }, 5000);
    }
    
    if (zipSelectedButton) {
        zipSelectedButton.addEventListener('click', () => {
            if (selectedItems.size === 0) return;
            showZipModal();
        });
    }

    function showZipModal() {
        itemsToZip = Array.from(selectedItems);
        if (zipModalMessage) zipModalMessage.textContent = `Create archive from ${itemsToZip.length} selected item(s)`;
        if (archiveNameInput) archiveNameInput.value = 'archive.zip';
        if (deleteZippedFilesCheckbox) deleteZippedFilesCheckbox.checked = false; // Default to off
        if (zipModal) zipModal.style.display = 'flex';
    }

    function closeZipModal() {
        if (zipModal) zipModal.style.display = 'none';
        itemsToZip = null;
    }

    function showExtractModal(archiveFilePath) {
        fileToUnzip = archiveFilePath;
        const fileName = archiveFilePath.split('/').pop();
        if (unzipModalMessage) unzipModalMessage.textContent = `Extract contents of "${fileName}"`;
        
        // Generate extraction folder name based on archive name
        const archiveName = fileName.split('.')[0]; // Get name without extension
        if (extractPathInput) extractPathInput.value = `${archiveName}_extracted`;
        if (unzipModal) unzipModal.style.display = 'flex';
    }

    // Keep old function for backward compatibility
    function showUnzipModal(zipFilePath) {
        return showExtractModal(zipFilePath);
    }

    function closeUnzipModal() {
        if (unzipModal) unzipModal.style.display = 'none';
        fileToUnzip = null;
    }

    // Zip modal event handlers
    if (confirmZipButton) {
        confirmZipButton.addEventListener('click', async () => {
            if (itemsToZip && archiveNameInput && archiveNameInput.value.trim()) {
                const archiveName = archiveNameInput.value.trim();
                const deleteAfterZip = deleteZippedFilesCheckbox ? deleteZippedFilesCheckbox.checked : false;
                
                const result = await fetchAPI('/api/zip', {
                    method: 'POST',
                    body: { 
                        items: itemsToZip, 
                        archive_name: archiveName, 
                        output_path: currentDirectory,
                        delete_after_zip: deleteAfterZip
                    }
                });

                if (result && result.success) {
                    showToast(result.message, 'success');
                    clearAllSelections();
                }
            }
            closeZipModal();
        });
    }

    if (cancelZipButton) cancelZipButton.addEventListener('click', closeZipModal);
    if (closeZipModalButton) closeZipModalButton.addEventListener('click', closeZipModal);

    // Unzip modal event handlers
    if (confirmUnzipButton) {
        confirmUnzipButton.addEventListener('click', async () => {
            if (fileToUnzip) {
                const extractFolderName = extractPathInput ? extractPathInput.value.trim() : '';
                let extractPath = currentDirectory;
                if (extractFolderName !== '') {
                    extractPath = currentDirectory ? `${currentDirectory}/${extractFolderName}` : extractFolderName;
                }

                const result = await fetchAPI('/api/unzip', {
                    method: 'POST',
                    body: { zip_path: fileToUnzip, extract_path: extractPath }
                });
                if (result && result.success) {
                    showToast(result.message, 'success');
                }
            }
            closeUnzipModal();
        });
    }

    if (cancelUnzipButton) cancelUnzipButton.addEventListener('click', closeUnzipModal);
    if (closeUnzipModalButton) closeUnzipModalButton.addEventListener('click', closeUnzipModal);

    // Update the unzipFile function to use the modal
    async function unzipFile(zipFilePath) {
        showUnzipModal(zipFilePath);
    }

    // --- Logout ---
    if (logoutButton) {
        logoutButton.addEventListener('click', () => {
            window.location.href = '/logout';
        });
    }

    // --- Toast Notifications ---
    function showToast(message, type = 'info') {
        // Simple toast, can be replaced with a library
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);

        // Trigger the animation
        setTimeout(() => {
            toast.classList.add('show');
        }, 10); // Small delay to allow the element to be added to DOM first

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                toast.remove();
            }, 300); // Wait for fade out transition to complete
        }, 3000); // Duration toast is visible
    }

    // --- SocketIO Setup with Auto-reconnection ---
    const updatesSocket = io('/updates', {
        autoConnect: true,
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 5,
        timeout: 20000
    });
    
    const logsSocket = io('/logs', {
        autoConnect: true,
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 5,
        timeout: 20000
    });

    // Updates socket event handlers
    updatesSocket.on('connect', () => {
        console.log('Connected to /updates namespace');
    });

    updatesSocket.on('disconnect', (reason) => {
        console.log('Disconnected from /updates:', reason);
        showToast('Connection lost. Attempting to reconnect...', 'warning');
        if (reason === 'io server disconnect') {
            // Server initiated disconnect - manual reconnection needed
            updatesSocket.connect();
        }
    });

    updatesSocket.on('reconnect', () => {
        console.log('Reconnected to /updates namespace');
        showToast('Connection restored!', 'success');
        // Refresh current directory to sync any missed changes
        if (currentDirectory !== undefined) {
            loadFiles(currentDirectory);
        }
    });

    updatesSocket.on('reconnect_error', (error) => {
        console.log('Failed to reconnect to /updates:', error);
    });

    // Logs socket event handlers
    logsSocket.on('connect', () => {
        console.log('Connected to /logs namespace');
    });

    logsSocket.on('disconnect', (reason) => {
        console.log('Disconnected from /logs:', reason);
        if (reason === 'io server disconnect') {
            // Server initiated disconnect - manual reconnection needed
            logsSocket.connect();
        }
    });

    logsSocket.on('reconnect', () => {
        console.log('Reconnected to /logs namespace');
        // Request fresh log data on reconnection
        if (activityLogList) {
            // The server will send initial_logs again upon reconnection
        }
    });

    logsSocket.on('reconnect_error', (error) => {
        console.log('Failed to reconnect to /logs:', error);
    });

    updatesSocket.on('user_count_update', (data) => {
        if (userCountDisplay) userCountDisplay.textContent = `Connected Users: ${data.count}`;
    });

    updatesSocket.on('file_changed', function(data) {
        console.log('File change event received:', data);
        
        if (data.external) {
            // Show notification for external changes
            showToast(`External change detected: ${data.action} - ${data.path || 'file'}`, 'info');
        }
        
        // Refresh the current directory if it's affected
        let shouldRefresh = false;
        const currentPath = currentDirectory || '';
        
        if (data.action === 'renamed' && data.old_path && data.new_path) {
            // Check if the renamed item affects current view
            const oldParent = data.old_path.includes('/') ? data.old_path.substring(0, data.old_path.lastIndexOf('/')) : '';
            const newParent = data.new_path.includes('/') ? data.new_path.substring(0, data.new_path.lastIndexOf('/')) : '';
            
            if (oldParent === currentPath || newParent === currentPath) {
                shouldRefresh = true;
            }
        } else {
            // For other actions, check if the path affects current view
            const itemParent = data.path && data.path.includes('/') ? 
                data.path.substring(0, data.path.lastIndexOf('/')) : '';
            
            if (itemParent === currentPath || data.path === currentPath) {
                shouldRefresh = true;
            }
        }
        
        if (shouldRefresh) {
            console.log('Refreshing directory due to file change');
            loadFiles(currentDirectory);
        }
    });

    logsSocket.on('initial_logs', (data) => {
        if (activityLogList) {
            activityLogList.innerHTML = ''; // Clear existing if any
            // Logs come from server in newest-first order, so we append each one in order
            // This maintains the newest-first ordering (newest at top, oldest at bottom)
            data.logs.forEach(log => addLogEntry(log, false));
        }
    });

    logsSocket.on('new_activity', (log) => {
        addLogEntry(log, true);
    });

    function addLogEntry(log, prepend = false) {
        if (!activityLogList) return;
        const li = document.createElement('li');
        const timestamp = new Date(log.timestamp).toLocaleString();
        let displayAction = log.action; // Default to concise action
        let actionClass = 'log-action-default';

        // Map concise actions to display text and CSS classes
        switch (log.action) {
            case 'login': 
                displayAction = 'User Logged In'; 
                actionClass = 'log-action-login'; 
                break;
            case 'login_fail': 
                displayAction = 'Login Attempt Failed'; 
                actionClass = 'log-action-error'; 
                break;
            case 'logout': 
                displayAction = 'User Logged Out'; 
                actionClass = 'log-action-logout'; 
                break;
            case 'list_dir': 
                displayAction = 'Viewed Directory'; 
                actionClass = 'log-action-preview'; 
                break;
            case 'preview': 
                displayAction = 'Previewed File'; 
                actionClass = 'log-action-preview'; 
                break;
            case 'download': 
                displayAction = 'Downloaded File'; 
                actionClass = 'log-action-download'; 
                break;
            case 'save_file': 
                displayAction = 'Saved/Updated File'; 
                actionClass = 'log-action-modify'; 
                break;
            case 'create_folder': 
                displayAction = 'Created Folder'; 
                actionClass = 'log-action-add'; 
                break;
            case 'create_file': // Assuming you might add this concise action
                displayAction = 'Created File'; 
                actionClass = 'log-action-add'; 
                break;
            case 'delete': 
                displayAction = 'Deleted Item'; 
                actionClass = 'log-action-delete'; 
                break;
            case 'batch_delete': 
                displayAction = 'Batch Deleted Items'; 
                actionClass = 'log-action-delete'; 
                break;
            case 'rename': 
                displayAction = 'Renamed Item'; 
                actionClass = 'log-action-modify'; 
                break;
            case 'zip': 
                displayAction = 'Zipped Item(s)'; 
                actionClass = 'log-action-archive'; 
                break;
            case 'unzip': 
                displayAction = 'Unzipped File'; 
                actionClass = 'log-action-archive'; 
                break;
            case 'upload': 
                displayAction = 'Uploaded File'; 
                actionClass = 'log-action-add'; 
                break;
            case 'access_denied':
                displayAction = 'Access Denied';
                actionClass = 'log-action-error';
                break;
            case 'operation_error':
                displayAction = 'Operation Error';
                actionClass = 'log-action-error';
                break;
            case 'external_file_change':
                displayAction = 'External File Change';
                actionClass = 'log-action-system'; // A new class for system events
                break;
            // Add more cases as new concise actions are defined
        }

        li.innerHTML = `<span class="log-timestamp">[${timestamp}]</span> <span class="log-user">${log.username} (${log.ip_address})</span>: <span class="log-action ${actionClass}">${displayAction}</span> <small class="log-details">${log.details || ''}</small>`;
        
        if (prepend) {
            activityLogList.insertBefore(li, activityLogList.firstChild);
        } else {
            activityLogList.appendChild(li);
        }
        // Optional: limit number of log entries displayed
        const maxLogEntries = 100;
        while (activityLogList.children.length > maxLogEntries) {
            activityLogList.removeChild(activityLogList.lastChild);
        }
    }
    
    // --- Initial Load ---
    async function initializeApp() {
        // Check login status first, useful if landing directly on index.html when already logged in.
        applyTheme();
        updateButtonVisibility(); // Set initial button visibility
        
        const status = await fetchAPI('/api/user/status');
        if (status && status.logged_in) {
            if(document.getElementById('username-display')) document.getElementById('username-display').textContent = status.username;
            if(userCountDisplay) userCountDisplay.textContent = `Connected Users: ${status.user_count}`;
            loadFiles(''); // Load root directory
        } else if (window.location.pathname !== '/login') {
            // If not on login page and not logged in, redirect.
            // This handles cases where user might try to access index directly without session
            window.location.href = '/login';
        }
        // If on login page, the login form submission will handle redirection.
    }

    // Only run app initialization logic if we are on the main page (index.html)
    // The login page has its own minimal script.
    if (fileList) { // Check if a main page element exists
        initializeApp();
    }

    // Add this new function somewhere in script.js
    function renameItem(itemPath, currentName, itemType, itemElement) {
        if (currentRenameOperation) { // If another rename is in progress, cancel it
            currentRenameOperation.cancel();
        }

        const itemNameSpan = itemElement.querySelector('.item-name');
        const itemActionsDiv = itemElement.querySelector('.file-item-actions'); // Assuming this is the container for action buttons

        if (!itemNameSpan) {
            console.error('Could not find item name span for rename:', itemElement);
            return;
        }

        // Hide original name and actions
        itemNameSpan.style.display = 'none';
        if (itemActionsDiv) itemActionsDiv.style.display = 'none';

        // Create input field
        const input = document.createElement('input');
        input.type = 'text';
        input.value = currentName;
        input.className = 'rename-input'; // For styling

        // Create confirm button (tick)
        const confirmBtn = document.createElement('button');
        confirmBtn.innerHTML = '<i class="fas fa-check"></i>';
        confirmBtn.className = 'rename-confirm-btn';

        // Create cancel button (cross)
        const cancelBtn = document.createElement('button');
        cancelBtn.innerHTML = '<i class="fas fa-times"></i>';
        cancelBtn.className = 'rename-cancel-btn';

        // Container for input and buttons
        const renameControls = document.createElement('div');
        renameControls.className = 'rename-controls';
        renameControls.appendChild(input);
        renameControls.appendChild(confirmBtn);
        renameControls.appendChild(cancelBtn);

        // Insert controls after the icon
        const itemDetailsDiv = itemElement.querySelector('.item-details');
        if (itemDetailsDiv && itemDetailsDiv.firstChild) { // insert after icon
            itemDetailsDiv.insertBefore(renameControls, itemNameSpan);
        } else {
            itemNameSpan.parentNode.insertBefore(renameControls, itemNameSpan); // fallback
        }
        input.focus();
        input.select();

        const performRename = () => {
            const newName = input.value.trim();
            if (newName && newName !== currentName) {
                fetch('/api/rename', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type: itemType, current_path: itemPath, new_name: newName })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // showToast(data.message || `${itemType} renamed successfully.`, 'success');
                        // The list will be refreshed by SocketIO, which will remove the input
                    } else {
                        showToast(data.error || `Failed to rename ${itemType}.`, 'error');
                        cleanup(); // Restore UI on failure
                    }
                })
                .catch(error => {
                    console.error('Error renaming:', error);
                    showToast(`Error renaming ${itemType}.`, 'error');
                    cleanup(); // Restore UI on error
                });
            } else if (newName === currentName) {
                cleanup(); // No change, just clean up
            } else {
                showToast('New name cannot be empty.', 'error');
                input.focus(); // Keep focus if name is empty
            }
        };

        const cleanup = () => {
            renameControls.remove();
            itemNameSpan.style.display = ''; // Restore display
            if (itemActionsDiv) itemActionsDiv.style.display = ''; // Restore display
            currentRenameOperation = null;
        };

        confirmBtn.onclick = performRename;
        input.onkeydown = (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                performRename();
            } else if (event.key === 'Escape') {
                event.preventDefault();
                cleanup();
            }
        };
        cancelBtn.onclick = cleanup;

        currentRenameOperation = { cancel: cleanup }; // Store cleanup function
    }

    async function loadArchiveContents(archiveFilePath) {
        const archiveContentsListElement = document.getElementById('zip-contents-list');
        const archiveContentsTitle = document.getElementById('archive-contents-title');
        if (!archiveContentsListElement) return;
        
        archiveContentsListElement.innerHTML = '<li><i class="fas fa-spinner fa-spin"></i> Loading contents...</li>';

        const data = await fetchAPI(`/api/archive/contents?path=${encodeURIComponent(archiveFilePath)}`);

        if (data && data.success && data.contents) {
            // Update title with archive type
            const archiveType = data.archive_type ? data.archive_type.toUpperCase() : 'Archive';
            if (archiveContentsTitle) archiveContentsTitle.textContent = `${archiveType} Contents:`;
            
            archiveContentsListElement.innerHTML = ''; // Clear loading/previous
            if (data.contents.length === 0) {
                const li = document.createElement('li');
                li.textContent = `This ${archiveType} archive is empty.`;
                archiveContentsListElement.appendChild(li);
                return;
            }
            
            data.contents.forEach(item => {
                const li = document.createElement('li');
                const icon = document.createElement('i');
                icon.classList.add('fas');
                icon.classList.add(item.is_dir ? 'fa-folder' : getFileIconClass(item.name));
                icon.style.marginRight = '8px';
                
                const sizeInfo = item.size !== undefined ? ` (${formatBytes(item.size)})` : '';
                const compressionInfo = item.compressed_size !== undefined && item.compressed_size !== item.size 
                    ? ` [Compressed: ${formatBytes(item.compressed_size)}]` 
                    : '';
                
                li.appendChild(icon);
                li.appendChild(document.createTextNode(`${item.name}${sizeInfo}${compressionInfo}`));
                archiveContentsListElement.appendChild(li);
            });
        } else {
            archiveContentsListElement.innerHTML = '<li>Error loading archive contents.</li>';
            if (data && data.error) {
                showToast(`Error previewing archive: ${data.error}`, 'error');
            }
        }
    }

    // Keep the old function for backward compatibility
    async function loadZipContents(zipFilePath) {
        return loadArchiveContents(zipFilePath);
    }
    
    // Helper function to format bytes (optional, but nice for zip contents)
    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    if (closeModalButton) {
        closeModalButton.onclick = function() {
            if (imageZoomModal) imageZoomModal.style.display = "none";
        }
    }
    // Close modal if user clicks outside the image
    if (imageZoomModal) {
        imageZoomModal.onclick = function(event) {
            if (event.target === imageZoomModal) { // Check if click is on the modal background itself
                imageZoomModal.style.display = "none";
            }
        }
    }

    function closeAllDropdowns() {
        document.querySelectorAll('.actions-dropdown.active').forEach(dropdown => {
            dropdown.classList.remove('active');
            if (dropdown._associatedButton) {
                dropdown._associatedButton.innerHTML = '<i class="fas fa-ellipsis-v"></i>';
                delete dropdown._associatedButton; // Clean up reference
            }
        });
        // Fallback: Ensure any buttons that somehow got stuck as 'X' are reset.
        // This typically shouldn't be needed if the above logic is sound.
        document.querySelectorAll('.ellipsis-button').forEach(button => {
            // If it doesn't have an active dropdown it thinks it's associated with, reset it.
            // This is a bit indirect. The primary mechanism is the _associatedButton.
            let associatedDropdownIsOpen = false;
            document.querySelectorAll('.actions-dropdown.active').forEach(dd => {
                if (dd._associatedButton === button) associatedDropdownIsOpen = true;
            });
            if (!associatedDropdownIsOpen && button.innerHTML.includes('fa-times')) {
                 button.innerHTML = '<i class="fas fa-ellipsis-v"></i>';
            }
        });
    }

    // Add a global click listener to close dropdowns when clicking outside
    document.addEventListener('click', function(event) {
        // If the click is not on an ellipsis button and not inside a dropdown, close all dropdowns
        if (!event.target.closest('.ellipsis-button') && !event.target.closest('.actions-dropdown')) {
            closeAllDropdowns();
        }
    });

    // Add an escape key handler to close dropdowns
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeAllDropdowns();
        }
    });

    // Socket.IO event listeners for connection status should be added after 'socket' is initialized.
    // Assuming 'socket' is the variable name for the Socket.IO client instance.

    if (typeof socket !== 'undefined') {
        socket.on('disconnect', (reason) => {
            showToast('Disconnected from server: ' + reason + '. Attempting to reconnect...', 'error');
            // Socket.IO client will attempt to reconnect automatically by default.
            // You could add UI changes here, e.g., disable certain features.
        });

        socket.on('connect_error', (error) => {
            showToast('Connection error: ' + error.message, 'error');
        });

        socket.on('connect', () => {
            // This event is useful if you want to do something special upon successful (re)connection.
            // For example, re-enable UI elements or refresh data.
            // showToast('Connected to server.', 'success'); // Optional: notify on successful connection
            // If there was a visible "disconnected" state, clear it here.
        });
    } else {
        console.warn('Socket.IO client (socket) not found. Disconnection handlers not attached.');
    }

    // --- Helper Functions ---
    function getFileIcon(filename) {
        return getFileIconClass(filename); // Use existing function
    }

    function toggleItemSelectionState(itemElement, path, shouldBeSelected) {
        const checkbox = itemElement.querySelector('.item-checkbox');
        if (shouldBeSelected) {
            selectedItems.add(path);
            itemElement.classList.add('selected');
            if (checkbox) checkbox.checked = true;
        } else {
            selectedItems.delete(path);
            itemElement.classList.remove('selected');
            if (checkbox) checkbox.checked = false;
        }
        updateSelectionControls(); // Fixed function name
    }

    if (selectAllButton) {
        selectAllButton.addEventListener('click', () => {
            // Automatically switch to select mode if not already in it
            if (!isCheckboxSelectModeActive) {
                isCheckboxSelectModeActive = true;
                toggleSelectModeButton.classList.add('active');
                toggleSelectModeButton.innerHTML = '<i class="fas fa-mouse-pointer"></i> Click Mode';
                loadFiles(currentDirectory); // Reload to show checkboxes
                return; // Exit early, let the reload handle selection
            }
            
            const allItemElements = fileList.querySelectorAll('.file-item, .folder-item:not(.navigation-item)');
            const allCurrentlySelectedOnPage = Array.from(allItemElements).every(el => selectedItems.has(el.dataset.path));

            if (allCurrentlySelectedOnPage && selectedItems.size >= allItemElements.length) {
                // If all visible items are selected, deselect all *visible* items
                allItemElements.forEach(itemEl => {
                    if(selectedItems.has(itemEl.dataset.path)) {
                        toggleItemSelectionState(itemEl, itemEl.dataset.path, false);
                    }
                });
            } else {
                // Otherwise, select all visible items
                allItemElements.forEach(itemEl => {
                    if(!selectedItems.has(itemEl.dataset.path)) {
                         toggleItemSelectionState(itemEl, itemEl.dataset.path, true);
                    }
                });
            }
        });
    }

    // Function to update button visibility based on mode
    function updateButtonVisibility() {
        const selectAllButton = document.getElementById('select-all-button');
        if (selectAllButton) {
            selectAllButton.style.display = isCheckboxSelectModeActive ? 'inline-block' : 'none';
        }
    }

    function createUploadProgressItem(fileName, fileSize = null) {
        const fileId = `upload-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        
        // Create progress bar elements for this file
        const progressItem = document.createElement('div');
        progressItem.classList.add('upload-progress-item');
        progressItem.id = fileId;
        
        const fileInfoSpan = document.createElement('span');
        fileInfoSpan.classList.add('file-info');
        fileInfoSpan.textContent = fileSize ? `${fileName} (${formatBytes(fileSize)})` : fileName;

        const progressBarContainer = document.createElement('div');
        progressBarContainer.classList.add('progress-bar-container');
        const progressBar = document.createElement('div');
        progressBar.classList.add('progress-bar');
        progressBarContainer.appendChild(progressBar);

        const progressTextSpan = document.createElement('span');
        progressTextSpan.classList.add('progress-text');
        progressTextSpan.textContent = '0%';

        const uploadSpeedSpan = document.createElement('span');
        uploadSpeedSpan.classList.add('upload-speed');
        uploadSpeedSpan.textContent = '0 B/s';
        
        // Add close button
        const closeButton = document.createElement('button');
        closeButton.classList.add('upload-progress-close');
        closeButton.innerHTML = '×';
        closeButton.title = 'Close';
        closeButton.onclick = () => {
            progressItem.style.transition = 'opacity 0.3s ease-out';
            progressItem.style.opacity = '0';
            setTimeout(() => {
                if (progressItem.parentNode) {
                    progressItem.parentNode.removeChild(progressItem);
                }
            }, 300);
        };

        progressItem.appendChild(fileInfoSpan);
        progressItem.appendChild(progressBarContainer);
        progressItem.appendChild(progressTextSpan);
        progressItem.appendChild(uploadSpeedSpan);
        progressItem.appendChild(closeButton);
        
        if (uploadProgressArea) uploadProgressArea.appendChild(progressItem);
        
        return progressItem;
    }

    // Call updateButtonVisibility on page load
    updateButtonVisibility();

    // Drag and Drop Setup
    if (fileListContainer) {
        setupDragAndDrop();
    }

    function setupDragAndDrop() {
        setupDropZone();
    }

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight(e) {
        const dragOverlay = document.getElementById('drag-overlay');
        const fileListContainer = document.getElementById('file-list-container');
        if (dragOverlay) dragOverlay.classList.add('active');
        if (fileListContainer) fileListContainer.classList.add('drag-active');
    }

    function unhighlight(e) {
        const dragOverlay = document.getElementById('drag-overlay');
        const fileListContainer = document.getElementById('file-list-container');
        if (dragOverlay) dragOverlay.classList.remove('active');
        if (fileListContainer) fileListContainer.classList.remove('drag-active');
    }

    function setupDropZone() {
        const fileListContainer = document.getElementById('file-list-container');
        if (!fileListContainer) return;

        // Prevent default drag behaviors on the entire document
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            document.addEventListener(eventName, preventDefaults, false);
            fileListContainer.addEventListener(eventName, preventDefaults, false);
        });

        // Handle highlight for external files being dragged over
        ['dragenter', 'dragover'].forEach(eventName => {
            fileListContainer.addEventListener(eventName, (e) => {
                // Only highlight for external files (not internal drag operations)
                if (e.dataTransfer.types.includes('Files')) {
                    highlight(e);
                }
            }, false);
        });

        // Handle unhighlight when leaving or dropping
        ['dragleave', 'drop'].forEach(eventName => {
            fileListContainer.addEventListener(eventName, (e) => {
                // Only unhighlight for external files
                if (e.dataTransfer.types.includes('Files')) {
                    unhighlight(e);
                }
            }, false);
        });

        // Handle the actual file drop
        fileListContainer.addEventListener('drop', (e) => {
            // Check if this is an external file drop (not internal drag)
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handleFiles(e);
            }
        }, false);
    }

    function handleFiles(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFileUploads(files);
    }

    // Add missing drag and drop handlers for file/directory items
    function handleDragStart(e, path) {
        e.dataTransfer.setData('text/plain', path);
        e.dataTransfer.effectAllowed = 'move';
    }

    function handleDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        e.currentTarget.classList.add('drag-over');
    }

    function handleDragLeave(e) {
        e.currentTarget.classList.remove('drag-over');
    }

    function handleDrop(e, targetPath) {
        e.preventDefault();
        e.currentTarget.classList.remove('drag-over');
        
        const sourcePath = e.dataTransfer.getData('text/plain');

        
        if (sourcePath && sourcePath !== targetPath && targetPath !== undefined && targetPath !== null) {
            // Move file/folder to target directory
            moveItem(sourcePath, targetPath);
        } else {
            if (!sourcePath) {
                showToast('Error: No source file detected', 'error');
            } else if (targetPath === undefined || targetPath === null) {
                showToast('Error: Invalid target directory', 'error');
            } else if (sourcePath === targetPath) {
                showToast('Cannot move item to itself', 'warning');
            }
        }
    }

    async function moveItem(sourcePath, targetPath) {
        console.log('moveItem debug:', {
            sourcePath,
            targetPath,
            sourcePathType: typeof sourcePath,
            targetPathType: typeof targetPath,
            sourcePathEmpty: !sourcePath,
            targetPathUndefined: targetPath === undefined,
            targetPathNull: targetPath === null,
            targetPathEmpty: targetPath === ''
        });
        
        // Validate parameters (empty string and "/" are valid for root directory)
        if (!sourcePath || targetPath === undefined || targetPath === null) {
            showToast(`Invalid move operation: source='${sourcePath}', target='${targetPath}'`, 'error');
            return;
        }
        
        try {
            const requestBody = {
                source: sourcePath,
                target: targetPath
            };
            console.log('Sending move request:', requestBody);
            
            const response = await fetchAPI('/api/move', {
                method: 'POST',
                body: requestBody
            });
            
            if (response.success) {
                showToast('Item moved successfully', 'success');
                loadFiles(currentDirectory); // Refresh the current view
            } else {
                showToast(response.error || 'Failed to move item', 'error');
            }
        } catch (error) {
            showToast('Error moving item: ' + error.message, 'error');
        }
    }

    async function handleFileUploads(files) {
        for (const file of files) {
            await uploadSingleFile(file);
        }
    }

    async function uploadSingleFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('path', currentDirectory);

        // Create progress indicator
        const progressItem = createUploadProgressItem(file.name, file.size);
        const progressBar = progressItem.querySelector('.progress-bar');
        const progressText = progressItem.querySelector('.progress-text');
        const uploadSpeed = progressItem.querySelector('.upload-speed');

        try {
            const xhr = new XMLHttpRequest();
            
            // Track upload progress
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    progressBar.style.width = percentComplete + '%';
                    progressText.textContent = `${Math.round(percentComplete)}%`;
                    
                    // Calculate upload speed
                    const uploadSpeedValue = (e.loaded / 1024 / 1024).toFixed(2); // MB
                    uploadSpeed.textContent = `${uploadSpeedValue} MB uploaded`;
                }
            });

            // Handle upload completion
            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    if (response.success) {
                        progressText.textContent = 'Upload complete!';
                        progressBar.style.backgroundColor = 'var(--success-color)';
                        showToast(`File "${file.name}" uploaded successfully.`, 'success');
                        
                        // Refresh file list to show the new file
                        loadFiles(currentDirectory);
                        
                        // Auto-hide after 5 seconds
                        setTimeout(() => {
                            progressItem.style.transition = 'opacity 1s ease';
                            progressItem.style.opacity = '0';
                            setTimeout(() => {
                                if (progressItem.parentNode) {
                                    progressItem.parentNode.removeChild(progressItem);
                                }
                            }, 1000);
                        }, 5000);
                    } else {
                        throw new Error(response.error || 'Upload failed');
                    }
                } else {
                    throw new Error('Upload failed');
                }
            });

            // Handle upload errors
            xhr.addEventListener('error', () => {
                progressText.textContent = 'Upload failed!';
                progressBar.style.backgroundColor = 'var(--error-color)';
                showToast(`Failed to upload "${file.name}".`, 'error');
                
                // Auto-hide after 5 seconds
                setTimeout(() => {
                    progressItem.style.transition = 'opacity 1s ease';
                    progressItem.style.opacity = '0';
                    setTimeout(() => {
                        if (progressItem.parentNode) {
                            progressItem.parentNode.removeChild(progressItem);
                        }
                    }, 1000);
                }, 5000);
            });

            // Send the request
            xhr.open('POST', '/api/upload');
            xhr.send(formData);
            
        } catch (error) {
            progressText.textContent = 'Upload failed!';
            progressBar.style.backgroundColor = 'var(--error-color)';
            showToast(`Failed to upload "${file.name}": ${error.message}`, 'error');
        }
    }
}); 