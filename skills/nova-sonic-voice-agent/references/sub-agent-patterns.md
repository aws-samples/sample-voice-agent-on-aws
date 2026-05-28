# Sub-Agent Patterns

Design patterns and examples for using Strands Agent instances as tools within the BidiAgent voice agent.

## Concept

A sub-agent is a full Strands `Agent` instance (text-based, using a reasoning model) that gets passed as a tool to the BidiAgent. Nova Sonic invokes it mid-stream like any other tool — the sub-agent processes the request, returns text, and Nova Sonic speaks it back to the user.

## Default Configuration

- **Reasoning model**: `us.amazon.nova-2-lite-v1:0` (fast, cost-effective)
- **Use Nova Pro** (`us.amazon.nova-2-pro-v1:0`) only when stronger reasoning is needed
- **Keep responses concise** — output is spoken aloud

## Basic Pattern

```python
from strands import Agent, tool
from strands.models.bedrock import BedrockModel


@tool
def lookup_order(order_id: str) -> str:
    """Look up an order by ID.

    Args:
        order_id: The order ID to look up.
    """
    # Replace with real API call
    return f"Order {order_id}: shipped on May 20, arriving May 23."


def create_order_agent(region: str = "us-east-1"):
    """Create an order tracking sub-agent."""
    model = BedrockModel(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name=region,
    )

    return Agent(
        model=model,
        tools=[lookup_order],
        system_prompt="You are an order tracking specialist. Look up orders and provide brief status updates.",
        name="order_tracker",
        description="Tracks and provides status updates for customer orders. Call this when the user asks about an order, shipment, or delivery.",
    )
```

## Factory Pattern (Reusable)

```python
def create_subagent_tool(
    name: str,
    description: str,
    system_prompt: str,
    tools: list = None,
    model_id: str = "us.amazon.nova-2-lite-v1:0",
    region: str = "us-east-1",
):
    """Create a Strands Agent configured as a tool for the BidiAgent.

    Args:
        name: Tool name exposed to BidiAgent (e.g., "finance_agent").
        description: What this sub-agent does — Nova Sonic uses this to decide when to call it.
        system_prompt: Instructions for the sub-agent.
        tools: Optional list of @tool functions the sub-agent can use.
        model_id: Bedrock model ID for reasoning.
        region: AWS region.

    Returns:
        Agent instance (pass directly to BidiAgent tools list).
    """
    model = BedrockModel(model_id=model_id, region_name=region)

    return Agent(
        model=model,
        tools=tools or [],
        system_prompt=system_prompt,
        name=name,
        description=description,
    )
```

## Multiple Sub-Agents Example

```python
# subagents.py
from strands import Agent, tool
from strands.models.bedrock import BedrockModel


@tool
def check_balance(account_id: str) -> str:
    """Check account balance."""
    return f"Account {account_id} balance: $4,250.00"


@tool
def get_transactions(account_id: str, limit: int = 5) -> str:
    """Get recent transactions."""
    return f"Last {limit} transactions for {account_id}: grocery $45, gas $38, coffee $6"


@tool
def lookup_faq(question: str) -> str:
    """Search the FAQ knowledge base."""
    return f"FAQ answer for '{question}': Our business hours are 9am-5pm Monday through Friday."


def create_finance_agent(region: str = "us-east-1"):
    model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0", region_name=region)
    return Agent(
        model=model,
        tools=[check_balance, get_transactions],
        system_prompt="You are a finance assistant. Be precise with numbers. Keep responses to one sentence.",
        name="finance_agent",
        description="Handles financial queries: account balances, transactions, transfers. Call for any banking topic.",
    )


def create_support_agent(region: str = "us-east-1"):
    model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0", region_name=region)
    return Agent(
        model=model,
        tools=[lookup_faq],
        system_prompt="You are a customer support agent. Answer questions using the FAQ. Be brief and helpful.",
        name="support_agent",
        description="Answers general questions about policies, hours, and services using the FAQ knowledge base.",
    )
```

## Wiring Sub-Agents into BidiAgent

```python
# agent.py
from subagents import create_finance_agent, create_support_agent

def _create_agent() -> BidiAgent:
    model = BidiNovaSonicModel(
        region=REGION,
        model_id=MODEL_ID,
        provider_config={"audio": {"input_rate": INPUT_RATE, "output_rate": OUTPUT_RATE, "voice": VOICE}},
    )

    finance = create_finance_agent(region=REGION)
    support = create_support_agent(region=REGION)

    return BidiAgent(
        model=model,
        tools=[finance, support],
        system_prompt=SYSTEM_PROMPT,
    )
```

## How It Works at Runtime

1. User speaks → Nova Sonic transcribes and processes
2. Nova Sonic decides a sub-agent's expertise is needed (based on `description`)
3. Nova Sonic emits a `toolUse` event with the sub-agent's `name`
4. BidiAgent invokes the sub-agent synchronously (text-based reasoning with Nova Lite)
5. Sub-agent uses its own tools, returns a text response
6. Response is sent back to Nova Sonic as a tool result
7. Nova Sonic speaks the response to the user
8. Audio streaming continues uninterrupted

## Design Guidelines

| Guideline | Reason |
|-----------|--------|
| Write clear `description` fields | Nova Sonic uses this to decide when to route to the sub-agent |
| Use Nova Lite by default | Fast and cost-effective for text reasoning |
| Give sub-agents their own tools | They can call APIs, query databases independently |
| Keep sub-agent responses concise | Output is spoken aloud — long text = awkward pauses |
| Add "be brief" to sub-agent prompts | Reinforces conciseness in the system prompt |
| Use specific tool names | `order_tracker` is better than `agent_1` |

## File Structure

```
websocket/
├── server.py
├── agent.py            # Imports and wires sub-agents
├── subagents.py        # Sub-agent definitions
├── tools.py            # Simple @tool functions (optional, separate from sub-agents)
└── requirements.txt
```

## Mixing Tools and Sub-Agents

You can pass both simple `@tool` functions and sub-agents in the same tools list:

```python
from tools import get_weather, get_time
from subagents import create_finance_agent

def _create_agent() -> BidiAgent:
    model = BidiNovaSonicModel(...)
    finance = create_finance_agent()

    return BidiAgent(
        model=model,
        tools=[get_weather, get_time, finance],  # Mix simple tools + sub-agents
        system_prompt=SYSTEM_PROMPT,
    )
```

Nova Sonic treats them identically — each appears as a tool with a name and description.
