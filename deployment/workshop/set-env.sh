#!/bin/bash
# =============================================================================
# Workshop Environment Setup
# =============================================================================
# Sets AWS credentials and CloudFront proxy URLs for the EC2 lab environment.
# Source this script (don't execute it) so variables persist in your shell:
#
#   source set-env.sh
#
# After sourcing, these variables are available:
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
#   AWS_DEFAULT_REGION, AWS_REGION, ACCOUNT_ID
#   CLOUDFRONT_BASE_URL  (e.g., https://XXXXX.cloudfront.net)
#   WS_BASE_URL          (e.g., wss://XXXXX.cloudfront.net/proxy/8081/ws)
#   CLIENT_BASE_URL      (e.g., https://XXXXX.cloudfront.net/proxy/3000)
# =============================================================================

echo ""
echo "=============================================="
echo "  Workshop Environment Setup"
echo "=============================================="
echo ""

# --- AWS Region ---
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_REGION="$AWS_DEFAULT_REGION"

# --- AWS Credentials from EC2 Instance Metadata (IMDS) ---
if [ -z "$AWS_ACCESS_KEY_ID" ]; then
    echo "🔑 Fetching AWS credentials from instance metadata..."
    TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
        -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null)

    if [ -n "$TOKEN" ]; then
        ROLE_NAME=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
            http://169.254.169.254/latest/meta-data/iam/security-credentials/ 2>/dev/null)

        if [ -n "$ROLE_NAME" ]; then
            CREDS=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
                "http://169.254.169.254/latest/meta-data/iam/security-credentials/$ROLE_NAME" 2>/dev/null)

            export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | python3 -c "import sys,json; print(json.load(sys.stdin)['AccessKeyId'])" 2>/dev/null)
            export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | python3 -c "import sys,json; print(json.load(sys.stdin)['SecretAccessKey'])" 2>/dev/null)
            export AWS_SESSION_TOKEN=$(echo "$CREDS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Token'])" 2>/dev/null)
            echo "   ✅ Credentials loaded from role: $ROLE_NAME"
        else
            echo "   ⚠️  No IAM role found on instance"
        fi
    else
        echo "   ⚠️  IMDS not available (not running on EC2?)"
    fi
else
    echo "🔑 Using existing AWS credentials from environment"
fi

# --- AWS Account ID ---
if [ -z "$ACCOUNT_ID" ]; then
    echo "📋 Fetching AWS Account ID..."
    export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
    if [ -n "$ACCOUNT_ID" ]; then
        echo "   ✅ Account ID: $ACCOUNT_ID"
    else
        echo "   ⚠️  Could not determine Account ID (aws sts get-caller-identity failed)"
    fi
else
    echo "📋 Account ID: $ACCOUNT_ID"
fi

# --- Workshop Password from CloudFormation Stack ---
echo "🔐 Fetching workshop password from CloudFormation..."
WORKSHOP_PASSWORD=$(aws cloudformation describe-stacks \
    --stack-name "vscode-server-full" \
    --query "Stacks[0].Outputs[?OutputKey=='Password'].OutputValue" \
    --output text 2>/dev/null)

if [ -n "$WORKSHOP_PASSWORD" ] && [ "$WORKSHOP_PASSWORD" != "None" ]; then
    export WORKSHOP_PASSWORD
    echo "   ✅ Workshop password set"
else
    echo "   ⚠️  Could not retrieve password from vscode-server-full stack"
fi

# --- CloudFront Proxy URL ---
VSCODE_PROXY_URI=$(printenv VSCODE_PROXY_URI 2>/dev/null || echo "")

if [ -n "$VSCODE_PROXY_URI" ]; then
    # Extract the base CloudFront URL (remove the {{port}} placeholder)
    export CLOUDFRONT_BASE_URL=$(echo "$VSCODE_PROXY_URI" | sed 's|/proxy/{{port}}.*||')

    # WebSocket URL (port 8081): replace {{port}}, convert https→wss, append /ws
    PROXY_URL="${VSCODE_PROXY_URI//\{\{port\}\}/8081}"
    export WS_BASE_URL="${PROXY_URL/https:/wss:}ws"

    # Client URL (port 3000)
    export CLIENT_BASE_URL="${VSCODE_PROXY_URI//\{\{port\}\}/3000}"

    echo ""
    echo "🌐 CloudFront proxy detected:"
    echo "   Base URL:    $CLOUDFRONT_BASE_URL"
    echo "   WebSocket:   $WS_BASE_URL"
    echo "   Client:      $CLIENT_BASE_URL"
else
    export CLOUDFRONT_BASE_URL=""
    export WS_BASE_URL="ws://localhost:8081/ws"
    export CLIENT_BASE_URL="http://localhost:3000"

    echo ""
    echo "🌐 No CloudFront proxy (local mode):"
    echo "   WebSocket:   $WS_BASE_URL"
    echo "   Client:      $CLIENT_BASE_URL"
fi

echo ""
echo "📍 Region:  $AWS_DEFAULT_REGION"
echo "📋 Account: $ACCOUNT_ID"
echo ""
echo "=============================================="
echo "  ✅ Environment ready"
echo "=============================================="
echo ""
