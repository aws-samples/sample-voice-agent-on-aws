"""
Banking Sub-Agent (A2A)

A Strands agent deployed as an A2A server on AgentCore Runtime.
Handles account management, balance inquiries, transactions, and transfers.
"""

from strands import Agent, tool
from strands.multiagent.a2a.executor import StrandsA2AExecutor
from bedrock_agentcore.runtime import serve_a2a
from strands.models import BedrockModel
import json


@tool
def get_account_balance(account_number: str) -> str:
    """Get the current balance for a bank account.

    Args:
        account_number: The account number to check
    """
    response = {
        "status": "success",
        "account_number": account_number,
        "account_type": "Premium Checking",
        "balances": {
            "available": 15234.56,
            "current": 15734.56,
            "pending": 500.00,
        },
        "currency": "USD",
        "last_updated": "2024-03-04T10:30:00Z",
        "message": "Your available balance is $15,234.56",
    }
    return json.dumps(response)


@tool
def get_recent_transactions(account_number: str, limit: int = 5) -> str:
    """Get recent transactions for an account.

    Args:
        account_number: The account number to check
        limit: Number of transactions to return (default: 5)
    """
    response = {
        "status": "success",
        "account_number": account_number,
        "transactions": [
            {"id": "TXN-001", "date": "2024-03-04", "description": "Amazon.com Purchase", "amount": -89.99, "type": "debit", "category": "Shopping"},
            {"id": "TXN-002", "date": "2024-03-03", "description": "Salary Deposit", "amount": 5000.00, "type": "credit", "category": "Income"},
            {"id": "TXN-003", "date": "2024-03-02", "description": "Grocery Store", "amount": -156.78, "type": "debit", "category": "Food & Dining"},
            {"id": "TXN-004", "date": "2024-03-01", "description": "Electric Bill Payment", "amount": -125.00, "type": "debit", "category": "Utilities"},
            {"id": "TXN-005", "date": "2024-02-28", "description": "ATM Withdrawal", "amount": -200.00, "type": "debit", "category": "Cash"},
        ][:limit],
        "message": f"Showing {min(limit, 5)} most recent transactions",
    }
    return json.dumps(response)


@tool
def transfer_funds(from_account: str, to_account: str, amount: float) -> str:
    """Transfer funds between accounts.

    Args:
        from_account: Source account number
        to_account: Destination account number
        amount: Amount to transfer
    """
    response = {
        "status": "success",
        "transfer_id": "TRF-20240304-001",
        "from_account": from_account,
        "to_account": to_account,
        "amount": amount,
        "currency": "USD",
        "timestamp": "2024-03-04T10:35:00Z",
        "new_balance": 15234.56 - amount,
        "message": f"Successfully transferred ${amount:.2f} from account {from_account} to {to_account}",
    }
    return json.dumps(response)


@tool
def get_account_summary(customer_id: str) -> str:
    """Get a summary of all accounts for a customer.

    Args:
        customer_id: The customer's unique identifier
    """
    response = {
        "status": "success",
        "customer_id": customer_id,
        "customer_name": "John Doe",
        "accounts": [
            {"account_number": "1234567890", "account_type": "Premium Checking", "balance": 15234.56, "status": "active"},
            {"account_number": "1234567891", "account_type": "Savings Account", "balance": 45678.90, "status": "active", "interest_rate": 2.5},
            {"account_number": "1234567892", "account_type": "Credit Card", "balance": -2345.67, "credit_limit": 10000.00, "status": "active"},
        ],
        "total_assets": 60913.46,
        "total_liabilities": 2345.67,
        "net_worth": 58567.79,
        "message": "Account summary retrieved successfully",
    }
    return json.dumps(response)


SYSTEM_PROMPT = """You are a banking operations agent for AnyBank. Your role is to:
1. Check account balances
2. Retrieve recent transactions
3. Process fund transfers between accounts
4. Provide account summaries

Use the appropriate tool for each request. Return clear, helpful information about the account status.
Always confirm transfer details before processing."""

model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[get_account_balance, get_recent_transactions, transfer_funds, get_account_summary],
)

if __name__ == "__main__":
    serve_a2a(StrandsA2AExecutor(agent))
