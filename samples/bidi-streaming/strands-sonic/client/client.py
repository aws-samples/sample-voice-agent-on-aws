#!/usr/bin/env python3
import argparse
import os
import sys
import webbrowser
import json
import secrets
import string
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Import from deployment folder websocket_helpers (only needed for --runtime-arn mode)
def _import_presigned_url():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../deployment/agentcore"))
    try:
        from websocket_helpers import create_presigned_url
        return create_presigned_url
    except ImportError:
        return None

create_presigned_url = _import_presigned_url()


class StrandsClientHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves the Strands client"""

    # Class variables to store connection details
    websocket_url = None
    session_id = None
    is_presigned = False
    default_profile = None

    # Store config for regenerating URLs
    runtime_arn = None
    region = None
    service = None
    expires = None
    qualifier = None

    def log_message(self, format, *args):
        """Override to provide cleaner logging"""
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        # Strip CloudFront proxy prefix (e.g., /proxy/3000/) if present
        path = parsed_path.path
        import re
        path = re.sub(r'^/proxy/\d+/', '/', path)

        if path == "/" or path == "/index.html":
            self.serve_client_page()
        elif path == "/api/connection":
            self.serve_connection_info()
        elif path == "/api/profiles":
            self.serve_profiles()
        else:
            self.send_error(404, "File not found")

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        # Strip CloudFront proxy prefix (e.g., /proxy/3000/) if present
        import re
        path = re.sub(r'^/proxy/\d+/', '/', parsed_path.path)

        if path == "/api/regenerate":
            self.regenerate_url()
        else:
            self.send_error(404, "Endpoint not found")

    def serve_client_page(self):
        """Serve the HTML client with pre-configured connection"""
        try:
            # Read the HTML template
            html_path = os.path.join(os.path.dirname(__file__), "strands-client.html")
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            # Inject the WebSocket URL if provided
            if self.websocket_url:
                html_content = html_content.replace(
                    'id="presignedUrl" placeholder="wss://endpoint/runtimes/arn/ws?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...&X-Amz-Signature=..."',
                    f'id="presignedUrl" placeholder="wss://endpoint/runtimes/arn/ws?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...&X-Amz-Signature=..." value="{self.websocket_url}"',
                )

            # Inject default profile if specified via --profile flag
            if self.default_profile:
                # Add a script that sets the default profile after page load
                profile_script = f'''<script>
                window._defaultProfile = "{self.default_profile}";
                </script>'''
                html_content = html_content.replace('</head>', f'{profile_script}\n</head>')

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", len(html_content.encode()))
            self.end_headers()
            self.wfile.write(html_content.encode())

        except FileNotFoundError:
            self.send_error(404, "strands-client.html not found")
        except Exception as e:
            self.send_error(500, f"Internal server error: {str(e)}")

    def serve_connection_info(self):
        """Serve the connection information as JSON"""
        response = {
            "websocket_url": self.websocket_url or "",
            "session_id": self.session_id,
            "is_presigned": self.is_presigned,
            "can_regenerate": self.runtime_arn is not None,
            "status": "ok" if self.websocket_url else "no_connection",
        }

        response_json = json.dumps(response, indent=2)

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", len(response_json.encode()))
        self.end_headers()
        self.wfile.write(response_json.encode())

    def serve_profiles(self):
        """Serve the profiles.json file"""
        try:
            profiles_path = os.path.join(os.path.dirname(__file__), "profiles.json")
            with open(profiles_path, "r", encoding="utf-8") as f:
                profiles_content = f.read()

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(profiles_content.encode()))
            self.end_headers()
            self.wfile.write(profiles_content.encode())

        except FileNotFoundError:
            self.send_response(200)
            empty = "[]"
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(empty.encode()))
            self.end_headers()
            self.wfile.write(empty.encode())
        except Exception as e:
            self.send_error(500, f"Internal server error: {str(e)}")

    def regenerate_url(self):
        """Regenerate the presigned URL"""
        try:
            if not self.runtime_arn:
                error_response = {
                    "status": "error",
                    "message": "Cannot regenerate URL - not using presigned URL mode",
                }
                response_json = json.dumps(error_response)
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.send_header("Content-Length", len(response_json.encode()))
                self.end_headers()
                self.wfile.write(response_json.encode())
                return

            # Generate new presigned URL
            base_url = f"wss://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{self.runtime_arn}/ws?qualifier={self.qualifier}"

            new_url = create_presigned_url(
                base_url, region=self.region, service=self.service, expires=self.expires
            )

            # Update the class variable
            StrandsClientHandler.websocket_url = new_url

            response = {
                "status": "ok",
                "websocket_url": new_url,
                "expires_in": self.expires,
                "message": "URL regenerated successfully",
            }

            response_json = json.dumps(response, indent=2)

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(response_json.encode()))
            self.end_headers()
            self.wfile.write(response_json.encode())

            print(f"✅ Regenerated presigned URL (expires in {self.expires} seconds)")

        except Exception as e:
            error_response = {"status": "error", "message": str(e)}
            response_json = json.dumps(error_response)
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(response_json.encode()))
            self.end_headers()
            self.wfile.write(response_json.encode())


def main():
    parser = argparse.ArgumentParser(
        description="Start web service for Strands WebSocket client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local WebSocket server (no authentication)
  python client.py --ws-url ws://localhost:8080/ws
  
  # AWS Bedrock with presigned URL
  python client.py --runtime-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/RUNTIMEID
  
  # Specify custom port
  python client.py --runtime-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/RUNTIMEID --port 8080
  
  # Custom region
  python client.py --runtime-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/RUNTIMEID \\
    --region us-east-1
""",
    )

    parser.add_argument(
        "--runtime-arn",
        help="Runtime ARN for AWS Bedrock connection (e.g., arn:aws:bedrock-agentcore:region:account:runtime/id)",
    )

    parser.add_argument(
        "--ws-url",
        help="WebSocket server URL for local connections (e.g., ws://localhost:8080/ws)",
    )

    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION", "us-east-1"),
        help="AWS region (default: us-east-1, from AWS_REGION env var)",
    )

    parser.add_argument(
        "--service",
        default="bedrock-agentcore",
        help="AWS service name (default: bedrock-agentcore)",
    )

    parser.add_argument(
        "--expires",
        type=int,
        default=3600,
        help="URL expiration time in seconds for presigned URLs (default: 3600 = 1 hour)",
    )

    parser.add_argument(
        "--qualifier", default="DEFAULT", help="Runtime qualifier (default: DEFAULT)"
    )



    parser.add_argument(
        "--port", type=int, default=3000, help="Web server port (default: 3000)"
    )

    parser.add_argument(
        "--no-browser", action="store_true", help="Do not automatically open browser"
    )

    parser.add_argument(
        "--profile",
        default=None,
        help="Default profile name to pre-select (e.g., 'Finance Agent', 'General Assistant')"
    )

    args = parser.parse_args()

    # Auto-detect runtime ARN from .bedrock_agentcore.yaml if neither flag provided
    if not args.runtime_arn and not args.ws_url:
        yaml_paths = [
            os.path.join(os.path.dirname(__file__), "../websocket/.bedrock_agentcore.yaml"),
            os.path.join(os.path.dirname(__file__), "../../strands-sonic/websocket/.bedrock_agentcore.yaml"),
        ]
        for yaml_path in yaml_paths:
            if os.path.exists(yaml_path):
                try:
                    import yaml
                    with open(yaml_path, 'r') as f:
                        config = yaml.safe_load(f)
                    # Find agent_arn in the config
                    if config and 'agents' in config:
                        for agent_name, agent_config in config['agents'].items():
                            bc = agent_config.get('bedrock_agentcore', {})
                            if bc and bc.get('agent_arn'):
                                args.runtime_arn = bc['agent_arn']
                                print(f"✅ Auto-detected runtime ARN from {yaml_path}")
                                print(f"   ARN: {args.runtime_arn}")
                                break
                    if args.runtime_arn:
                        break
                except Exception as e:
                    pass

    if not args.runtime_arn and not args.ws_url:
        parser.error("Either --runtime-arn or --ws-url must be specified (or deploy the agent first so .bedrock_agentcore.yaml exists)")

    if args.runtime_arn and args.ws_url:
        parser.error("Cannot specify both --runtime-arn and --ws-url")

    # Extract region from runtime ARN if provided
    if args.runtime_arn:
        arn_parts = args.runtime_arn.split(":")
        if len(arn_parts) >= 4:
            arn_region = arn_parts[3]
            if arn_region and arn_region != args.region:
                args.region = arn_region

    print("=" * 70)
    print("🎙️ Strands Client Web Service")
    print("=" * 70)

    websocket_url = None
    session_id = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(50))
    is_presigned = False

    try:
        # Generate presigned URL for AWS Bedrock
        if args.runtime_arn:
            base_url = f"wss://bedrock-agentcore.{args.region}.amazonaws.com/runtimes/{args.runtime_arn}/ws?qualifier={args.qualifier}"

            print(f"📡 Base URL: {base_url}")
            print(f"🔑 Runtime ARN: {args.runtime_arn}")
            print(f"🌍 Region: {args.region}")
            print(f"🆔 Session ID: {session_id}")
            print(
                f"⏰ URL expires in: {args.expires} seconds ({args.expires / 60:.1f} minutes)"
            )
            print()
            print("🔐 Generating pre-signed URL...")

            if create_presigned_url is None:
                print("❌ Error: websocket_helpers module not found.", file=sys.stderr)
                print("   Install it or use --ws-url for local connections.", file=sys.stderr)
                return 1

            websocket_url = create_presigned_url(
                base_url, region=args.region, service=args.service, expires=args.expires
            )
            is_presigned = True
            print("✅ Pre-signed URL generated successfully!")

        # Use provided WebSocket URL for local connections
        else:
            websocket_url = args.ws_url
            print(f"🔗 WebSocket URL: {websocket_url}")
            print("💡 Using local WebSocket connection (no authentication)")

        print(f"🌐 Web Server Port: {args.port}")
        print()

        # Set connection details in the handler class
        StrandsClientHandler.websocket_url = websocket_url
        StrandsClientHandler.session_id = session_id
        StrandsClientHandler.is_presigned = is_presigned
        StrandsClientHandler.default_profile = args.profile

        # Store config for regenerating URLs
        if args.runtime_arn:
            StrandsClientHandler.runtime_arn = args.runtime_arn
            StrandsClientHandler.region = args.region
            StrandsClientHandler.service = args.service
            StrandsClientHandler.expires = args.expires
            StrandsClientHandler.qualifier = args.qualifier

        # Start web server (allow port reuse to avoid "Address already in use" on restart)
        import socket
        server_address = ("", args.port)

        class ReusableHTTPServer(HTTPServer):
            allow_reuse_address = True

        httpd = ReusableHTTPServer(server_address, StrandsClientHandler)

        server_url = f"http://localhost:{args.port}"

        print("=" * 70)
        print("🌐 Web Server Started")
        print("=" * 70)
        print(f"📍 Server URL: {server_url}")
        print(f"🔗 Client Page: {server_url}/")
        print(f"📊 API Endpoint: {server_url}/api/connection")
        print()
        if is_presigned:
            print("💡 The pre-signed WebSocket URL is pre-populated in the client")
        else:
            print("💡 The WebSocket URL is pre-populated in the client")
        print("💡 Press Ctrl+C to stop the server")
        print("=" * 70)
        print()

        # Open browser automatically
        if not args.no_browser:
            print("🌐 Opening browser...")
            webbrowser.open(server_url)
            print()

        # Start serving
        httpd.serve_forever()

    except KeyboardInterrupt:
        print("\n\n👋 Shutting down server...")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
