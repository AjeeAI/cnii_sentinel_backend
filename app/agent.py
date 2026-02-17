from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from app.tools import all_tools

SYSTEM_PROMPT = """You are the CNII Sentinel AI, a specialized assistant for monitoring fiber optic infrastructure risks in Nigeria.

Your capabilities:
1. **Patrol Sweep:** You can scan critical zones for risks using the `perform_patrol_sweep` tool.
2. **Risk Analysis:** You can explain specific threats found in the reports.

Guidelines:
- When asked to "run a patrol" or "scan for risks", ALWAYS use the `perform_patrol_sweep` tool.
- Be professional, concise, and focused on infrastructure safety.
"""

def create_sentinel_agent():
    """Create the LangGraph agent."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    agent = create_react_agent(
        model=llm,
        tools=all_tools,
        prompt=SYSTEM_PROMPT
    )
    return agent

# Singleton instance
agent = create_sentinel_agent()