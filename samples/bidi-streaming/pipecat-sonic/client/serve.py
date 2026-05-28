#!/usr/bin/env python3
"""Simple HTTP server that serves the Vite build output (dist/).

Handles CloudFront proxy prefix by stripping /proxy/PORT/ from request paths.
Proxies /start POST requests to the pipecat server on port 8081.

Usage:
    npm run build   # Build the Vite app first
    python3 serve.py
"""

import os
import re
import sys
import json
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError


PIPECAT_SERVER = os.getenv("PIPECAT_SERVER", "http://localhost:8081")


class ProxyAwareHandler(SimpleHTTPRequestHandler):
    """HTTP handler that strips CloudFront proxy prefix and proxies /start."""

    def do_POST(self):
        # Strip proxy prefix
        path = re.sub(r'^/proxy/\d+/', '/', self.path)

        if path == "/start":
            self._proxy_start()
        else:
            self.send_error(404, "Not found")

    def do_GET(self):
        # Strip proxy prefix before serving static files
        self.path = re.sub(r'^/proxy/\d+/', '/', self.path)
        return super().do_GET()

    def _proxy_start(self):
        """Forward /start to the pipecat server and return the response."""
        try:
            # Read request body if any
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None

            # Forward to pipecat server
            req = Request(
                f"{PIPECAT_SERVER}/start",
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )

            # Pass through forwarded headers so server can detect proxy
            if "Host" in self.headers:
                req.add_header("X-Forwarded-Host", self.headers["Host"])
            req.add_header("X-Forwarded-Proto", "https")

            with urlopen(req, timeout=10) as resp:
                response_data = resp.read()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(response_data))
            self.end_headers()
            self.wfile.write(response_data)

        except URLError as e:
            error_msg = json.dumps({"error": f"Cannot reach pipecat server: {e}"})
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(error_msg))
            self.end_headers()
            self.wfile.write(error_msg.encode())

    def translate_path(self, path):
        # Strip /proxy/PORT/ prefix if present
        path = re.sub(r'^/proxy/\d+/', '/', path)
        return super().translate_path(path)

    def log_message(self, format, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")


def main():
    port = int(os.getenv("PORT", "3000"))
    dist_dir = os.path.join(os.path.dirname(__file__), "dist")

    if not os.path.exists(dist_dir):
        print("❌ dist/ folder not found. Run 'npm run build' first.")
        sys.exit(1)

    os.chdir(dist_dir)

    print("=" * 50)
    print("🎙️  Pipecat Nova Sonic UI")
    print("=" * 50)
    print(f"📁 Serving: {dist_dir}")
    print(f"🔗 http://localhost:{port}")
    print(f"🔌 Pipecat server: {PIPECAT_SERVER}")
    print(f"💡 Press Ctrl+C to stop")
    print("=" * 50)

    webbrowser.open(f"http://localhost:{port}")

    httpd = HTTPServer(("", port), ProxyAwareHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")


if __name__ == "__main__":
    main()
