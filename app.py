import os
import sys
import shutil
import tempfile
import subprocess
import urllib.request
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


def run_browser_command(cmd, timeout=90):
    """Runs the chromium command in a new process group (on Unix) to ensure all descendant processes are killed on timeout."""
    import signal
    kwargs = {}
    if os.name != 'nt':
        kwargs['preexec_fn'] = os.setsid
        
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return process.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        # Kill the process group to reap all grandchild processes on Unix
        if os.name != 'nt':
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except Exception as kill_err:
                print(f"Failed to kill process group: {kill_err}")
        else:
            process.kill()
            
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout, output=stdout, stderr=stderr)

def download_static_assets():
    """Downloads necessary static assets on startup if they don't exist."""
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    os.makedirs(static_dir, exist_ok=True)
    
    tailwind_path = os.path.join(static_dir, "tailwind.min.css")
    if not os.path.exists(tailwind_path):
        print("Downloading static Tailwind CSS for offline rendering...")
        url = "https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css"
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                with open(tailwind_path, 'wb') as out_file:
                    out_file.write(response.read())
            print("Successfully downloaded tailwind.min.css")
        except Exception as e:
            print(f"Warning: Could not download tailwind.min.css on startup: {e}")

def optimize_html(html_path):
    """Optimizes uploaded HTML to render faster in headless Chromium by replacing CDN JIT with local static CSS."""
    try:
        if not os.path.exists(html_path):
            return
            
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        local_tailwind = os.path.join(os.path.dirname(__file__), "static", "tailwind.min.css")
        if os.path.exists(local_tailwind):
            local_tailwind_url = Path(local_tailwind).as_uri()
            # If the HTML uses cdn.tailwindcss.com, replace it
            if "cdn.tailwindcss.com" in content:
                print("Optimizing: Replacing cdn.tailwindcss.com JIT with local static tailwind.min.css")
                # Disable the CDN script tag
                content = content.replace(
                    '<script src="https://cdn.tailwindcss.com"></script>',
                    '<!-- Disabled Tailwind JIT CDN -->'
                )
                content = content.replace(
                    'src="https://cdn.tailwindcss.com"',
                    'src="" data-disabled-cdn="true"'
                )
                # Inject the local static stylesheet in head
                if "</head>" in content:
                    content = content.replace(
                        "</head>",
                        f'<link rel="stylesheet" href="{local_tailwind_url}"></head>'
                    )
                else:
                    content = f'<link rel="stylesheet" href="{local_tailwind_url}">' + content
                    
                # Write back the optimized HTML
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(content)
    except Exception as e:
        print(f"Warning: HTML optimization failed: {e}")

# Download static assets on startup
download_static_assets()

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
        
        # Optimize HTML to use local Tailwind static files and avoid JIT performance timeouts
        optimize_html(html_path)
        
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
            "--disable-software-rasterizer",
            "--disable-extensions",
            "--disable-background-networking",
            "--renderer-process-limit=2",
            "--enable-low-end-device-mode",
            "--disable-component-update",
            "--disable-sync",
            "--disable-default-apps",
            "--host-resolver-rules=MAP * ~NOTFOUND",
            "--safebrowsing-disable-auto-update",
            "--use-mock-keychain",
            "--password-store=basic",
            "--no-first-run",
            "--no-default-browser-check",
            "--print-to-pdf-no-header",
            f"--print-to-pdf={pdf_path}",
            file_url
        ]
        
        # Run conversion process
        print(f"Running subprocess command: {' '.join(cmd)}")
        returncode, stdout, stderr = run_browser_command(cmd, timeout=90)
        print(f"Subprocess finished with return code: {returncode}")
        if stdout:
            print(f"Subprocess stdout: {stdout}")
        if stderr:
            print(f"Subprocess stderr: {stderr}")
        
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
            stderr_msg = stderr if stderr else "Unknown error during rendering."
            return jsonify({'error': f'Rendering failed: {stderr_msg}'}), 500
            
    except subprocess.TimeoutExpired as e:
        print(f"Subprocess timeout expired!")
        if e.output:
            print(f"Subprocess stdout (partial): {e.output}")
        if e.stderr:
            print(f"Subprocess stderr (partial): {e.stderr}")
        stderr_msg = e.stderr if e.stderr else ""
        return jsonify({'error': f'The conversion process timed out. Subprocess stderr: {stderr_msg}'}), 504
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
        
        # Optimize HTML to use local Tailwind static files and avoid JIT performance timeouts
        optimize_html(html_path)
        
        pdf_path = os.path.join(temp_dir, "doc.pdf")
        file_url = Path(html_path).as_uri()
        
        cmd = [
            browser_path,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--user-data-dir={os.path.join(temp_dir, 'chrome-profile')}",
            "--disable-dev-shm-usage",
            "--disable-software-rasterizer",
            "--disable-extensions",
            "--disable-background-networking",
            "--renderer-process-limit=2",
            "--enable-low-end-device-mode",
            "--disable-component-update",
            "--disable-sync",
            "--disable-default-apps",
            "--host-resolver-rules=MAP * ~NOTFOUND",
            "--safebrowsing-disable-auto-update",
            "--use-mock-keychain",
            "--password-store=basic",
            "--no-first-run",
            "--no-default-browser-check",
            "--print-to-pdf-no-header",
            f"--print-to-pdf={pdf_path}",
            file_url
        ]
        
        print(f"Running subprocess command: {' '.join(cmd)}")
        returncode, stdout, stderr = run_browser_command(cmd, timeout=90)
        print(f"Subprocess finished with return code: {returncode}")
        if stdout:
            print(f"Subprocess stdout: {stdout}")
        if stderr:
            print(f"Subprocess stderr: {stderr}")
        
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
            stderr_msg = stderr if stderr else "Unknown error during rendering."
            return jsonify({'error': f'Rendering failed: {stderr_msg}'}), 500
            
    except subprocess.TimeoutExpired as e:
        print(f"Subprocess timeout expired!")
        if e.output:
            print(f"Subprocess stdout (partial): {e.output}")
        if e.stderr:
            print(f"Subprocess stderr (partial): {e.stderr}")
        stderr_msg = e.stderr if e.stderr else ""
        return jsonify({'error': f'Rendering timed out. Subprocess stderr: {stderr_msg}'}), 504
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
