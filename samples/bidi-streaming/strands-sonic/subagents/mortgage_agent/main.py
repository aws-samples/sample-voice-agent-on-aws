"""
Mortgage Sub-Agent (A2A)

A Strands agent deployed as an A2A server on AgentCore Runtime.
Handles mortgage rates, calculations, eligibility, and application status.
"""

from strands import Agent, tool
from strands.multiagent.a2a.executor import StrandsA2AExecutor
from bedrock_agentcore.runtime import serve_a2a
from strands.models import BedrockModel
import json


@tool
def get_mortgage_rates() -> str:
    """Get current mortgage rates and loan products."""
    response = {
        "status": "success",
        "effective_date": "2024-03-04",
        "rates": [
            {"product": "30-Year Fixed", "rate": 6.875, "apr": 7.125, "monthly_payment_per_100k": 658.00},
            {"product": "15-Year Fixed", "rate": 6.125, "apr": 6.375, "monthly_payment_per_100k": 855.00},
            {"product": "5/1 ARM", "rate": 6.250, "apr": 7.450, "monthly_payment_per_100k": 615.00},
            {"product": "FHA 30-Year", "rate": 6.500, "apr": 6.750, "monthly_payment_per_100k": 632.00},
        ],
        "disclaimer": "Rates are subject to change. Actual rate depends on credit score, down payment, and other factors.",
        "message": "Current mortgage rates retrieved successfully",
    }
    return json.dumps(response)


@tool
def calculate_mortgage_payment(loan_amount: float, interest_rate: float, loan_term_years: int, down_payment: float = 0) -> str:
    """Calculate monthly mortgage payment.

    Args:
        loan_amount: Total loan amount
        interest_rate: Annual interest rate (e.g., 6.5 for 6.5%)
        loan_term_years: Loan term in years (e.g., 30)
        down_payment: Down payment amount (default: 0)
    """
    principal = loan_amount - down_payment
    monthly_rate = interest_rate / 100 / 12
    num_payments = loan_term_years * 12

    if monthly_rate > 0:
        monthly_payment = principal * (monthly_rate * (1 + monthly_rate) ** num_payments) / ((1 + monthly_rate) ** num_payments - 1)
    else:
        monthly_payment = principal / num_payments

    total_payment = monthly_payment * num_payments
    total_interest = total_payment - principal

    response = {
        "status": "success",
        "loan_details": {
            "home_price": loan_amount,
            "down_payment": down_payment,
            "loan_amount": principal,
            "interest_rate": interest_rate,
            "loan_term_years": loan_term_years,
        },
        "monthly_payment": round(monthly_payment, 2),
        "total_payments": round(total_payment, 2),
        "total_interest": round(total_interest, 2),
        "message": f"Monthly payment: ${round(monthly_payment, 2):,.2f} (Principal & Interest)",
    }
    return json.dumps(response)


@tool
def check_mortgage_eligibility(customer_id: str, annual_income: float, monthly_debts: float, credit_score: int) -> str:
    """Check mortgage eligibility and pre-qualification amount.

    Args:
        customer_id: Customer's unique identifier
        annual_income: Annual gross income
        monthly_debts: Total monthly debt payments
        credit_score: Credit score (300-850)
    """
    monthly_income = annual_income / 12
    debt_to_income = (monthly_debts / monthly_income * 100) if monthly_income > 0 else 100
    eligible = credit_score >= 620 and debt_to_income <= 43
    max_monthly_payment = monthly_income * 0.28
    max_loan_amount = max_monthly_payment * 12 * 30 / 0.07

    response = {
        "status": "success",
        "eligible": eligible,
        "credit_score": credit_score,
        "debt_to_income_ratio": round(debt_to_income, 2),
        "estimated_max_loan": round(max_loan_amount, 2),
        "estimated_monthly_payment": round(max_monthly_payment, 2),
        "message": f"You are {'pre-qualified' if eligible else 'not currently eligible'} for a mortgage. Estimated max loan: ${round(max_loan_amount, 2):,.2f}",
    }
    return json.dumps(response)


@tool
def get_mortgage_application_status(application_id: str) -> str:
    """Check the status of a mortgage application.

    Args:
        application_id: The mortgage application ID
    """
    response = {
        "status": "success",
        "application_id": application_id,
        "application_status": "Under Review",
        "submitted_date": "2024-02-15",
        "last_updated": "2024-03-01",
        "progress": {
            "application_submitted": {"status": "completed", "date": "2024-02-15"},
            "document_verification": {"status": "completed", "date": "2024-02-20"},
            "credit_check": {"status": "completed", "date": "2024-02-22"},
            "appraisal_ordered": {"status": "in_progress", "date": "2024-03-01"},
            "underwriting": {"status": "pending"},
            "final_approval": {"status": "pending"},
        },
        "estimated_closing_date": "2024-03-20",
        "message": "Your application is under review. Appraisal scheduled for March 5th.",
    }
    return json.dumps(response)


SYSTEM_PROMPT = """You are a mortgage specialist agent for AnyBank. Your role is to:
1. Provide current mortgage rates
2. Calculate monthly payments for different loan scenarios
3. Check mortgage eligibility and pre-qualification
4. Provide application status updates

Be helpful and informative. When calculating payments, explain the breakdown clearly.
For eligibility checks, provide actionable next steps."""

model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[get_mortgage_rates, calculate_mortgage_payment, check_mortgage_eligibility, get_mortgage_application_status],
)

if __name__ == "__main__":
    serve_a2a(StrandsA2AExecutor(agent))
