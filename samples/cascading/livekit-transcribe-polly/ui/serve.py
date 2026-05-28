#!/usr/bin/env python3
"""Simple HTTP server that serves the React build folder.

Handles CloudFront proxy prefix by stripping /proxy/PORT/ from request paths.
"""

import os
import re
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse


class ProxyAwareHandler(SimpleHTTPRequestHandler):
    """HTTP handler that strips CloudFront proxy prefix from paths."""

    def translate_path(self, path):
        # Strip /proxy/PORT/ prefix if present
        path = re.sub(r'^/proxy/\d+/', '/', path)
        return super().translate_path(path)

    def log_message(self, format, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")


def main():
    port = int(os.getenv("PORT", "3000"))
    build_dir = os.path.join(os.path.dirname(__file__), "build")

    if not os.path.exists(build_dir):
        print("❌ Build folder not found. Run 'npm run build' first.")
        sys.exit(1)

    os.chdir(build_dir)

    print("=" * 50)
    print("🌐 LiveKit Nova Sonic UI")
    print("=" * 50)
    print(f"📁 Serving: {build_dir}")
    print(f"🔗 http://localhost:{port}")
    print(f"💡 Press Ctrl+C to stop")
    print("=" * 50)

    import webbrowser
    webbrowser.open(f"http://localhost:{port}")

    httpd = HTTPServer(("", port), ProxyAwareHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")


if __name__ == "__main__":
    main()
