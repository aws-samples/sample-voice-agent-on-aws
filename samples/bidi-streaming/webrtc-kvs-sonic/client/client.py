#!/usr/bin/env python3
"""
HTTP server for the WebRTC KVS voice client.

Serves the HTML client and proxies /invocations to either:
- A local agent (http://localhost:8080) for development
- An AgentCore Runtime via SigV4 signed requests

Usage:
  # Local mode (agent running on localhost:8080)
  python client.py --local

  # AgentCore mode (agent deployed to AgentCore Runtime)
  python client.py --runtime-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/RUNTIMEID
"""

import argparse
import json
import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

import boto3
import requests


class WebRTCClientHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves the WebRTC client and proxies agent calls."""

    # Class variables
    agent_url = None  # Local agent URL (e.g. http://localhost:8080)
    runtime_arn = None  # AgentCore Runtime ARN
    region = None

    def log_message(self, format, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/" or parsed_path.path == "/index.html":
            self._serve_client_page()
        elif parsed_path.path == "/ping":
            self._json_response({"status": "ok"})
        else:
            self.send_error(404, "File not found")

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/invocations":
            self._proxy_invocations()
        else:
            self.send_error(404, "Endpoint not found")

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _serve_client_page(self):
        """Serve the HTML client."""
        try:
            html_path = os.path.join(os.path.dirname(__file__), "webrtc-client.html")
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            # Inject agent URL or runtime ARN into the page
            if self.agent_url:
                html_content = html_content.replace(
                    'const AGENT_URL = ""',
                    f'const AGENT_URL = "{self.agent_url}"',
                )
                html_content = html_content.replace(
                    'const MODE = "proxy"',
                    'const MODE = "local"',
                )
            else:
                html_content = html_content.replace(
                    'const AGENT_URL = ""',
                    f'const AGENT_URL = ""',
                )
                html_content = html_content.replace(
                    'const MODE = "proxy"',
                    'const MODE = "proxy"',
                )

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", len(html_content.encode()))
            self.end_headers()
            self.wfile.write(html_content.encode())
        except FileNotFoundError:
            self.send_error(404, "webrtc-client.html not found")
        except Exception as e:
            self.send_error(500, f"Internal server error: {str(e)}")

    def _proxy_invocations(self):
        """Proxy /invocations to the agent (local or AgentCore)."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"
        payload = json.loads(body)

        try:
            if self.runtime_arn:
                result = self._invoke_agentcore(payload)
            elif self.agent_url:
                result = self._invoke_local(payload)
            else:
                result = {"error": "No agent configured"}

            self._json_response(result)
        except Exception as e:
            self._json_response({"error": str(e)}, status=500)

    def _invoke_local(self, payload):
        """Forward request to local agent."""
        resp = requests.post(
            f"{self.agent_url}/invocations",
            json=payload,
            timeout=30,
        )
        return resp.json()

    def _invoke_agentcore(self, payload):
        """Invoke agent via AgentCore Runtime API."""
        client = boto3.client("bedrock-agentcore", region_name=self.region)
        response = client.invoke_agent_runtime(
            agentRuntimeArn=self.runtime_arn,
            runtimeSessionId="webrtc-session",
            contentType="application/json",
            accept="application/json",
            payload=json.dumps(payload).encode(),
        )
        result_bytes = response["response"].read()
        return json.loads(result_bytes)

    def _json_response(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(
        description="WebRTC KVS Voice Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local agent (running on localhost:8080)
  python client.py --local

  # AgentCore Runtime
  python client.py --runtime-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/RUNTIMEID

  # Custom local agent URL
  python client.py --agent-url http://localhost:9090
""",
    )

    parser.add_argument(
        "--runtime-arn",
        help="AgentCore Runtime ARN",
    )
    parser.add_argument(
        "--agent-url",
        help="Local agent URL (default: http://localhost:8080)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local agent at http://localhost:8080",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION", "us-east-1"),
        help="AWS region (default: us-east-1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Web server port (default: 7860)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open browser",
    )

    args = parser.parse_args()

    # Determine mode
    if args.runtime_arn:
        WebRTCClientHandler.runtime_arn = args.runtime_arn
        WebRTCClientHandler.region = args.region
        # Extract region from ARN if present
        arn_parts = args.runtime_arn.split(":")
        if len(arn_parts) >= 4 and arn_parts[3]:
            WebRTCClientHandler.region = arn_parts[3]
        mode = "AgentCore Runtime"
    elif args.agent_url:
        WebRTCClientHandler.agent_url = args.agent_url
        mode = f"Local agent ({args.agent_url})"
    elif args.local:
        WebRTCClientHandler.agent_url = "http://localhost:8080"
        mode = "Local agent (http://localhost:8080)"
    else:
        parser.error("Specify --local, --agent-url, or --runtime-arn")

    print("=" * 60)
    print("🎙️ WebRTC KVS Voice Client")
    print("=" * 60)
    print(f"  Mode:    {mode}")
    print(f"  Port:    {args.port}")
    print(f"  Region:  {args.region}")
    print()

    server_address = ("", args.port)
    httpd = HTTPServer(server_address, WebRTCClientHandler)

    server_url = f"http://localhost:{args.port}"
    print(f"  URL:     {server_url}")
    print()
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    if not args.no_browser:
        webbrowser.open(server_url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped.")


if __name__ == "__main__":
    main()
