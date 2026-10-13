"""Local preview server for the dashboard. Serves a COPY in /tmp, because macOS privacy (TCC)
stops python started by a launcher from even calling os.getcwd() inside Desktop or Documents.

    python3 serve_preview.py <folder-with-dashboard.html> [port]

Copies the folder to /tmp/seo-llm-dashboard-preview and serves it. Re-run after every inject.
"""
import http.server, os, shutil, socketserver, sys

src, port = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 4661
dst = "/tmp/seo-llm-dashboard-preview"
shutil.copytree(src, dst, dirs_exist_ok=True)
os.chdir(dst)
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", port), http.server.SimpleHTTPRequestHandler) as s:
    print(f"http://localhost:{port}/dashboard.html")
    s.serve_forever()
