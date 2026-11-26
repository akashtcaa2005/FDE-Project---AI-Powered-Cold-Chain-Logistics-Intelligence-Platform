"""LangGraph FDE orchestrator with enforced system prompt and safe multi-provider factory."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.agent_tools import (  # noqa: E402
    fetch_corridor_conditions,
    query_telemetry_db,
    search_compliance_sop,
)

load_dotenv(project_root / ".env")

fde_tools = [query_telemetry_db, fetch_corridor_conditions, search_compliance_sop]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """Load the enterprise dispatcher system prompt from src/prompts/system_prompt.txt."""
    prompt_path = project_root / "src" / "prompts" / "system_prompt.txt"
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return (
            "You are FDE AI Dispatcher, a cold-chain logistics operations copilot. "
            "Use query_telemetry_db, fetch_corridor_conditions, and search_compliance_sop "
            "and never fabricate records, weather observations, or SOP citations."
        )


def create_llm(provider: str | None = None, model_name: str | None = None):
    """Instantiate the configured LangChain chat model for tool calling."""
    fallback_provider = "GROQ" if os.getenv("GROQ_API_KEY") else "OLLAMA"
    active_provider = (provider or os.getenv("Agent_llm", fallback_provider)).strip().upper()

    if active_provider == "OPENAI":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name or os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0,
            timeout=45,
            max_retries=2,
        )

    if active_provider == "DEEPSEEK":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            temperature=0,
            openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
            max_tokens=2048,
            timeout=45,
            max_retries=2,
        )

    if active_provider == "GROQ":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=0,
            openai_api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
            max_tokens=2048,
            timeout=45,
            max_retries=2,
        )

    if active_provider == "GEMINI":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name or os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            temperature=0,
            openai_api_key=os.getenv("GEMINI_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            max_tokens=2048,
            timeout=45,
            max_retries=2,
        )

    try:
        from langchain_community.chat_models import ChatOllama
    except ImportError:
        from langchain_ollama import ChatOllama  # type: ignore[no-redef]

    return ChatOllama(
        model=model_name or os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        temperature=0,
        num_predict=1024,
    )


def build_fde_agent(provider: str | None = None, model_name: str | None = None):
    """Compile a LangGraph tool-calling agent with isolated MemorySaver checkpointer."""
    llm = create_llm(provider=provider, model_name=model_name)
    llm_with_tools = llm.bind_tools(fde_tools)
    system_text = load_system_prompt()

    def reasoning_node(state: AgentState):
        msgs = list(state["messages"])
        # Ensure the business system prompt is ALWAYS applied (Streamlit UI + CLI)
        if not msgs or not isinstance(msgs[0], SystemMessage):
            msgs = [SystemMessage(content=system_text), *msgs]
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("reasoner", reasoning_node)
    graph_builder.add_node("tools", ToolNode(fde_tools, handle_tool_errors=True))

    graph_builder.add_edge(START, "reasoner")
    graph_builder.add_conditional_edges("reasoner", tools_condition)
    graph_builder.add_edge("tools", "reasoner")

    return graph_builder.compile(checkpointer=MemorySaver())


# Default module-level compiled agent (preserves existing imports across codebase)
AGENT_LLM_SETTING = os.getenv("Agent_llm", "GROQ" if os.getenv("GROQ_API_KEY") else "OLLAMA").strip().upper()
try:
    fde_agent = build_fde_agent()
except Exception:
    # Deferred build — the AI Dispatcher page will call build_fde_agent() on demand
    fde_agent = None  # type: ignore[assignment]


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("🚀 FDE Supply Chain Orchestrator State Machine Online")
    print(f"   Configured Execution: [LLM: {AGENT_LLM_SETTING}] -> [Embeddings: {os.getenv('Embeddings_model', 'LOCAL')}]")
    print("=" * 55 + "\n")

    thread_config = {"configurable": {"thread_id": "production_test_1"}}
    while True:
        user_input = input("\nDispatcher > ")
        if user_input.lower() in ["exit", "quit"]:
            break

        events = fde_agent.stream(
            {"messages": [("user", user_input)]},
            config=thread_config,
            stream_mode="updates",
        )
        for event in events:
            for node_name, node_state in event.items():
                if node_name == "tools":
                    print("   [System] 🔄 Retrieving external data elements via ToolNode...")
                elif node_name == "reasoner":
                    latest_msg = node_state["messages"][-1]
                    if latest_msg.content:
                        print(f"\n🤖 FDE Agent:\n{latest_msg.content}")
