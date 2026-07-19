import os
import sys
import shutil
import tempfile
import subprocess
from pathlib import Path
from flask import Flask, request, render_template, send_file, jsonify

app = Flask(__name__)

# Configure maximum upload size (e.g. 16MB)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Standard locations of Chromium-based browsers
DEFAULT_WINDOWS_BROWSER_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%USERPROFILE%\AppData\Local\Google\Chrome\Application\chrome.exe"),
]

def find_browser():
    """Finds available Chromium browser executable path cross-platform."""
    # 1. On Windows, check standard installation paths
    if os.name == 'nt':
        for path in DEFAULT_WINDOWS_BROWSER_PATHS:
            if os.path.exists(path):
                return path
                
    # 2. Check system PATH for common binary names (Linux/macOS/Windows)
    binaries = ['google-chrome', 'chrome', 'chromium', 'chromium-browser', 'msedge', 'microsoft-edge']
    for binary in binaries:
        path = shutil.which(binary)
        if path:
            return path
            
    return None

@app.route('/')
def index():
    """Renders the main converter interface."""
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    """Handles HTML file upload and returns the printed PDF."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file.'}), 400
        
    if not file.filename.lower().endswith('.html'):
        return jsonify({'error': 'Invalid file type. Only .html files are supported.'}), 400

    browser_path = find_browser()
    if not browser_path:
        return jsonify({
            'error': 'Chromium browser (Edge or Chrome) not found on server. Please ensure Chrome or Edge is installed.'
        }), 500

    # Create a temporary directory to process the conversion securely
    temp_dir = tempfile.mkdtemp(prefix='html_to_pdf_')
    try:
        # Save uploaded HTML file
        safe_filename = "document.html"
        html_path = os.path.join(temp_dir, safe_filename)
        file.save(html_path)
        
        # Output PDF path
        pdf_filename = Path(file.filename).with_suffix('.pdf').name
        pdf_path = os.path.join(temp_dir, pdf_filename)
        
        # Convert HTML path to file URI
        file_url = Path(html_path).as_uri()
        
        # Headless Chromium printing command
        cmd = [
            browser_path,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--user-data-dir={os.path.join(temp_dir, 'chrome-profile')}",
            "--disable-dev-shm-usage",
            "--single-process",
            "--no-first-run",
            "--no-default-browser-check",
            "--print-to-pdf-no-header",
            f"--print-to-pdf={pdf_path}",
            file_url
        ]
        
        # Run conversion process
        print(f"Running subprocess command: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
        print(f"Subprocess finished with return code: {result.returncode}")
        if result.stdout:
            print(f"Subprocess stdout: {result.stdout}")
        if result.stderr:
            print(f"Subprocess stderr: {result.stderr}")
        
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            # Send file and make sure to clean up the temp directory afterward.
            # We read file into memory or send it directly, then clean up.
            response = send_file(
                pdf_path,
                as_attachment=True,
                download_name=pdf_filename,
                mimetype='application/pdf'
            )
            return response
        else:
            stderr_msg = result.stderr if result.stderr else "Unknown error during rendering."
            return jsonify({'error': f'Rendering failed: {stderr_msg}'}), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'The conversion process timed out.'}), 504
    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500
    finally:
        # Schedule cleanup after request is handled
        # Flask's after_this_request can do this, or we do a simple cleanup thread.
        # But a robust way is to delete temp_dir when sending file completes.
        # To avoid file lock issues, we can clean up at the end of the view or use a background cleaner,
        # or delete it immediately since send_file reads the file or handles it.
        # Wait, if we use a helper thread or standard try/finally, if send_file is synchronous, it returns
        # the response but doesn't close the file till sent.
        # To be safe, we can read the file bytes, delete the temp dir immediately, and return a BytesIO:
        pass

# A safer file sender that reads file bytes, cleans up, and returns response
@app.route('/convert-safe', methods=['POST'])
def convert_safe():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected.'}), 400
        
    if not file.filename.lower().endswith('.html'):
        return jsonify({'error': 'Invalid file type. Only .html is supported.'}), 400

    browser_path = find_browser()
    if not browser_path:
        return jsonify({'error': 'No suitable browser found on server.'}), 500

    temp_dir = tempfile.mkdtemp(prefix='html_to_pdf_')
    try:
        html_path = os.path.join(temp_dir, "doc.html")
        file.save(html_path)
        
        pdf_path = os.path.join(temp_dir, "doc.pdf")
        file_url = Path(html_path).as_uri()
        
        cmd = [
            browser_path,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--user-data-dir={os.path.join(temp_dir, 'chrome-profile')}",
            "--disable-dev-shm-usage",
            "--single-process",
            "--no-first-run",
            "--no-default-browser-check",
            "--print-to-pdf-no-header",
            f"--print-to-pdf={pdf_path}",
            file_url
        ]
        
        print(f"Running subprocess command: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
        print(f"Subprocess finished with return code: {result.returncode}")
        if result.stdout:
            print(f"Subprocess stdout: {result.stdout}")
        if result.stderr:
            print(f"Subprocess stderr: {result.stderr}")
        
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            # Read bytes to memory
            with open(pdf_path, 'rb') as f:
                pdf_data = f.read()
                
            pdf_filename = Path(file.filename).with_suffix('.pdf').name
            
            import io
            return send_file(
                io.BytesIO(pdf_data),
                as_attachment=True,
                download_name=pdf_filename,
                mimetype='application/pdf'
            )
        else:
            return jsonify({'error': f'Rendering failed: {result.stderr}'}), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Rendering timed out.'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        # Safely clean up the temp directory
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            app.logger.error(f"Error cleaning up temp dir: {e}")

if __name__ == '__main__':
    # Default to port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
