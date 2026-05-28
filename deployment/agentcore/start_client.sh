#!/bin/bash

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Parse command line arguments
WEBSOCKET_FOLDER=""

usage() {
    echo "Usage: $0 <websocket-folder>"
    echo ""
    echo "Arguments:"
    echo "  websocket-folder    Folder containing the client (strands-sonic, langchain, echo, or sonic)"
    echo ""
    echo "Example:"
    echo "  ./start_client.sh bedrock-sonic"
    echo "  ./start_client.sh strands-sonic"
    echo "  ./start_client.sh langchain-transcribe-polly"
    echo "  ./start_client.sh echo"
    echo ""
    exit 1
}

# Check if folder argument is provided
if [ $# -eq 0 ]; then
    echo -e "${RED}❌ Error: websocket folder argument is required${NC}"
    echo ""
    usage
fi

WEBSOCKET_FOLDER="$1"

# Resolve the base directory (project root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Find the sample folder under samples/
SAMPLE_DIR=""
for search_path in "$BASE_DIR/samples/bidi-streaming/$WEBSOCKET_FOLDER" "$BASE_DIR/samples/cascading/$WEBSOCKET_FOLDER" "$SAMPLE_DIR"; do
    if [ -d "$search_path" ]; then
        SAMPLE_DIR="$search_path"
        break
    fi
done

# Validate folder exists
if [ -z "$SAMPLE_DIR" ]; then
    echo -e "${RED}❌ Error: Sample not found: $WEBSOCKET_FOLDER${NC}"
    echo ""
    echo "Available folders:"
    for dir in strands-sonic bedrock-sonic pipecat-sonic livekit-sonic webrtc-kvs-sonic livekit-transcribe-polly langchain-transcribe-polly; do
        if [ -d "$BASE_DIR/samples/bidi-streaming/$dir" ] || [ -d "$BASE_DIR/samples/cascading/$dir" ]; then
            echo "  - $dir"
        fi
    done
    echo ""
    exit 1
fi

echo -e "${BLUE}🚀 Starting $WEBSOCKET_FOLDER Client${NC}"
echo ""

# Auto-fetch AWS credentials from EC2 instance metadata (IMDS) if not already set
if [ -z "$AWS_ACCESS_KEY_ID" ]; then
    echo -e "${YELLOW}🔑 Fetching AWS credentials from instance metadata...${NC}"
    TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null)
    if [ -n "$TOKEN" ]; then
        ROLE_NAME=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/security-credentials/ 2>/dev/null)
        if [ -n "$ROLE_NAME" ]; then
            CREDS=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" "http://169.254.169.254/latest/meta-data/iam/security-credentials/$ROLE_NAME" 2>/dev/null)
            export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | python3 -c "import sys,json; print(json.load(sys.stdin)['AccessKeyId'])" 2>/dev/null)
            export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | python3 -c "import sys,json; print(json.load(sys.stdin)['SecretAccessKey'])" 2>/dev/null)
            export AWS_SESSION_TOKEN=$(echo "$CREDS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Token'])" 2>/dev/null)
            export AWS_DEFAULT_REGION=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo "us-east-1")
            echo -e "${GREEN}   ✅ Credentials loaded from role: $ROLE_NAME${NC}"
        else
            echo -e "${YELLOW}   ⚠️  No IAM role found. Please set AWS credentials manually.${NC}"
        fi
    else
        echo -e "${YELLOW}   ⚠️  IMDS not available. Please set AWS credentials manually.${NC}"
    fi
else
    echo -e "${GREEN}🔑 Using existing AWS credentials from environment${NC}"
fi
echo ""

# Check for configuration file
CONFIG_FILE="$SAMPLE_DIR/setup_config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ Error: Configuration file not found: $CONFIG_FILE${NC}"
    echo ""
    echo "Please run setup first:"
    echo "  ./setup.sh $WEBSOCKET_FOLDER"
    echo ""
    exit 1
fi

# Check for jq
if ! command -v jq &> /dev/null; then
    echo -e "${RED}❌ Error: jq is not installed${NC}"
    echo "Please install jq to parse JSON configuration"
    exit 1
fi

# Load configuration
echo -e "${YELLOW}📋 Loading configuration from $CONFIG_FILE...${NC}"
AGENT_ARN=$(jq -r '.agent_arn' "$CONFIG_FILE")
AWS_REGION=$(jq -r '.aws_region' "$CONFIG_FILE")

if [ -z "$AGENT_ARN" ] || [ "$AGENT_ARN" = "null" ]; then
    echo -e "${RED}❌ Error: Agent ARN not found in configuration${NC}"
    exit 1
fi

if [ -z "$AWS_REGION" ] || [ "$AWS_REGION" = "null" ]; then
    echo -e "${RED}❌ Error: AWS Region not found in configuration${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Configuration loaded${NC}"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "   Folder:       $WEBSOCKET_FOLDER"
echo "   Agent ARN:    $AGENT_ARN"
echo "   AWS Region:   $AWS_REGION"
echo ""

# Export environment variables
export AWS_REGION="$AWS_REGION"

# Check if virtual environment exists (not needed for pipecat-sonic — uses npm)
if [ "$WEBSOCKET_FOLDER" != "pipecat-sonic" ]; then
    if [ ! -d "$BASE_DIR/venv" ]; then
        echo -e "${YELLOW}⚠️  Virtual environment not found${NC}"
        echo "Creating virtual environment..."
        python3 -m venv "$BASE_DIR/venv"
        source "$BASE_DIR/venv/bin/activate"
        pip install -q -r "$SAMPLE_DIR/client/requirements.txt"
        echo -e "${GREEN}✅ Virtual environment created${NC}"
    else
        source "$BASE_DIR/venv/bin/activate"
    fi
fi

# Start the client
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 Starting Client${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Different clients have different interfaces
case "$WEBSOCKET_FOLDER" in
    "echo")
        echo -e "${YELLOW}Starting Echo client...${NC}"
        echo ""
        python "$SAMPLE_DIR/client/client.py" --runtime-arn "$AGENT_ARN"
        ;;
    "pipecat-sonic")
        echo -e "${YELLOW}Starting Pipecat client (signing server + Vite)...${NC}"
        echo ""

        cd "$SAMPLE_DIR/client"
        if [ ! -d "node_modules" ]; then
            echo -e "${YELLOW}Installing npm dependencies...${NC}"
            npm install
        fi

        # Start the signing server in the background (port 8081).
        # The Vite dev server proxies /start to it.
        echo -e "${YELLOW}Starting signing server on port 8081...${NC}"
        python "$SAMPLE_DIR/client/client.py" \
            --runtime-arn "$AGENT_ARN" \
            --region "$AWS_REGION" &
        SIGNING_PID=$!
        sleep 1

        echo -e "${YELLOW}Starting Vite dev server...${NC}"
        echo -e "${YELLOW}Open the URL shown below in your browser${NC}"
        echo ""

        # Run Vite in foreground; kill signing server on exit
        trap "kill $SIGNING_PID 2>/dev/null" EXIT
        npm run dev
        ;;
    "bedrock-sonic"|"strands-sonic"|"langchain-transcribe-polly")
        echo -e "${YELLOW}Starting $WEBSOCKET_FOLDER web client...${NC}"
        echo -e "${YELLOW}The browser will open automatically${NC}"
        echo ""
        python "$SAMPLE_DIR/client/client.py" --runtime-arn "$AGENT_ARN"
        ;;
    "webrtc-kvs-sonic")
        echo -e "${YELLOW}Starting WebRTC KVS client...${NC}"
        echo -e "${YELLOW}The browser will open automatically${NC}"
        echo ""
        python "$SAMPLE_DIR/client/client.py" --runtime-arn "$AGENT_ARN"
        ;;
    *)
        echo -e "${RED}❌ Error: Unknown folder type: $WEBSOCKET_FOLDER${NC}"
        exit 1
        ;;
esac
