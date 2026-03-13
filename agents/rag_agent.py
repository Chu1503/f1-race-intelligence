import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crewai import Agent
from langchain_anthropic import ChatAnthropic
from rag_pipeline.retriever import retrieve_similar_situations, format_context_for_agent
from config import settings

llm = ChatAnthropic(
    model=settings.CLAUDE_MODEL,
    api_key=settings.ANTHROPIC_API_KEY,
    max_tokens=settings.CLAUDE_MAX_TOKENS
)


def get_rag_context(query: str, top_k: int = 5) -> str:
    results = retrieve_similar_situations(query, top_k=top_k)
    return format_context_for_agent(results)


rag_agent = Agent(
    role="F1 Historical Data Analyst",
    goal=(
        "Retrieve and synthesize relevant historical F1 race data to provide "
        "context for current race strategy decisions."
    ),
    backstory=(
        "You are an expert F1 data analyst with access to a database of historical "
        "race data going back decades. You can find patterns in tyre degradation, "
        "pit stop timing, and race strategies across different circuits and conditions. "
        "You provide factual, data-driven context to support strategy decisions."
    ),
    llm=llm,
    verbose=False,
    allow_delegation=False,
)