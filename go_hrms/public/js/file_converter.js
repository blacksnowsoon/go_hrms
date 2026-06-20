document.addEventListener('DOMContentLoaded', function() {
	const dropzone = document.getElementById('dropzone');
	const fileInput = document.getElementById('file-input');
	const processingState = document.getElementById('processing-state');
	const successState = document.getElementById('success-state');
	const errorState = document.getElementById('error-state');

	const processingFilename = document.getElementById('processing-filename');
	const successFilename = document.getElementById('success-filename');
	const successFilesize = document.getElementById('success-filesize');
	const errorMessage = document.getElementById('error-message');

	const downloadBtn = document.getElementById('download-btn');
	const resetBtn = document.getElementById('reset-btn');
	const errorResetBtn = document.getElementById('error-reset-btn');

	let currentBlob = null;
	let currentDownloadName = 'converted.xlsx';

	// Click to open file dialog
	dropzone.addEventListener('click', () => {
		fileInput.click();
	});

	// Handle file dialog selection
	fileInput.addEventListener('change', (e) => {
		if (e.target.files.length > 0) {
			handleFile(e.target.files[0]);
		}
	});

	// Drag & Drop event handlers
	['dragenter', 'dragover'].forEach(eventName => {
		dropzone.addEventListener(eventName, (e) => {
			e.preventDefault();
			e.stopPropagation();
			dropzone.classList.add('dragover');
		}, false);
	});

	['dragleave', 'drop'].forEach(eventName => {
		dropzone.addEventListener(eventName, (e) => {
			e.preventDefault();
			e.stopPropagation();
			dropzone.classList.remove('dragover');
		}, false);
	});

	dropzone.addEventListener('drop', (e) => {
		const dt = e.dataTransfer;
		const files = dt.files;
		if (files.length > 0) {
			handleFile(files[0]);
		}
	});

	// Main file handling logic
	function handleFile(file) {
		// Reset file input value so same file can be selected again
		fileInput.value = '';

		// 1. Client-side validations
		if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
			showError('Only PDF files are supported. Please select a valid PDF file.');
			return;
		}

		const maxLimit = 10 * 1024 * 1024; // 10MB
		if (file.size > maxLimit) {
			showError('File is too large. Maximum supported file size is 10MB.');
			return;
		}

		// Update processing UI state
		showProcessing(file.name);

		// Prepare payload
		const formData = new FormData();
		formData.append('file', file);

		// Get CSRF Token
		const csrfToken = window.csrf_token || (window.frappe && frappe.csrf_token);

		const headers = {};
		if (csrfToken) {
			headers['X-Frappe-CSRF-Token'] = csrfToken;
		}

		// Perform API POST request
		fetch('/api/method/go_hrms.utils.file_converter.convert_pdf_to_excel', {
			method: 'POST',
			headers: headers,
			body: formData
		})
		.then(async response => {
			const contentType = response.headers.get('content-type');
			if (response.ok) {
				// Success binary response
				const blob = await response.blob();
				const contentDisposition = response.headers.get('content-disposition');
				let downloadName = file.name.substring(0, file.name.lastIndexOf('.')) + '.xlsx';

				if (contentDisposition) {
					const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
					if (filenameMatch && filenameMatch[1]) {
						downloadName = filenameMatch[1];
					}
				}

				currentBlob = blob;
				currentDownloadName = downloadName;
				showSuccess(downloadName, blob.size);
			} else {
				// Error JSON response
				let errText = 'An error occurred during file parsing.';
				if (contentType && contentType.includes('application/json')) {
					try {
						const errData = await response.json();
						errText = errData.error || errData.message || errText;
					} catch (e) {
						// Fallback if parsing fails
					}
				} else {
					try {
						const text = await response.text();
						if (text) errText = text;
					} catch (e) {}
				}
				showError(errText);
			}
		})
		.catch(error => {
			showError('Connection error. Please check your network and try again.');
			console.error('File conversion error:', error);
		});
	}

	// Trigger download on client side
	downloadBtn.addEventListener('click', () => {
		if (currentBlob) {
			const url = window.URL.createObjectURL(currentBlob);
			const a = document.createElement('a');
			a.style.display = 'none';
			a.href = url;
			a.download = currentDownloadName;
			document.body.appendChild(a);
			a.click();

			// Clean up
			setTimeout(() => {
				document.body.removeChild(a);
				window.URL.revokeObjectURL(url);
			}, 100);
		}
	});

	// Reset buttons
	resetBtn.addEventListener('click', resetState);
	errorResetBtn.addEventListener('click', resetState);

	// UI state switcher functions
	function showProcessing(filename) {
		dropzone.classList.add('hidden');
		successState.classList.add('hidden');
		errorState.classList.add('hidden');
		processingState.classList.remove('hidden');
		processingFilename.textContent = filename;
	}

	function showSuccess(filename, size) {
		processingState.classList.add('hidden');
		dropzone.classList.add('hidden');
		errorState.classList.add('hidden');
		successState.classList.remove('hidden');

		successFilename.textContent = filename;

		// Format file size
		let sizeStr = '';
		if (size < 1024) {
			sizeStr = size + ' B';
		} else if (size < 1024 * 1024) {
			sizeStr = (size / 1024).toFixed(1) + ' KB';
		} else {
			sizeStr = (size / (1024 * 1024)).toFixed(1) + ' MB';
		}
		successFilesize.textContent = sizeStr;
	}

	function showError(msg) {
		processingState.classList.add('hidden');
		dropzone.classList.add('hidden');
		successState.classList.add('hidden');
		errorState.classList.remove('hidden');
		errorMessage.textContent = msg;
	}

	function resetState() {
		currentBlob = null;
		successState.classList.add('hidden');
		errorState.classList.add('hidden');
		processingState.classList.add('hidden');
		dropzone.classList.remove('hidden');
	}
});
