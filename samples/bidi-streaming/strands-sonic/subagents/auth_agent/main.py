"""
Authentication Sub-Agent (A2A)

A Strands agent deployed as an A2A server on AgentCore Runtime.
Handles user authentication and identity verification.
"""

from strands import Agent, tool
from strands.multiagent.a2a.executor import StrandsA2AExecutor
from bedrock_agentcore.runtime import serve_a2a
from strands.models import BedrockModel
import json


@tool
def authenticate_user(username: str, account_number: str) -> str:
    """Authenticate a user with their username and account number.

    Args:
        username: The customer's username
        account_number: The customer's account number
    """
    response = {
        "status": "success",
        "authenticated": True,
        "user": {
            "username": username,
            "account_number": account_number,
            "full_name": "John Doe",
            "customer_id": "CUST-001",
            "member_since": "2020-01-15",
            "account_type": "Premium Checking",
        },
        "session_token": "tok_demo_abc123xyz789",
        "message": f"Welcome back, {username}! Authentication successful.",
    }
    return json.dumps(response)


@tool
def verify_identity(customer_id: str, last_four_ssn: str) -> str:
    """Verify customer identity using customer ID and last 4 digits of SSN.

    Args:
        customer_id: The customer's unique identifier
        last_four_ssn: Last 4 digits of Social Security Number
    """
    response = {
        "status": "success",
        "verified": True,
        "customer_id": customer_id,
        "verification_level": "high",
        "verification_methods": ["SSN", "Account History", "Device Recognition"],
        "message": "Identity verified successfully. You may proceed with sensitive operations.",
    }
    return json.dumps(response)


SYSTEM_PROMPT = """You are an authentication agent for AnyBank. Your role is to:
1. Authenticate users by verifying their username and account number
2. Perform additional identity verification when needed using customer ID and SSN

Always use the authenticate_user tool when a user provides credentials.
Use verify_identity for additional verification when requested.
Return clear, structured results about the authentication status."""

model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[authenticate_user, verify_identity],
)

if __name__ == "__main__":
    serve_a2a(StrandsA2AExecutor(agent))
