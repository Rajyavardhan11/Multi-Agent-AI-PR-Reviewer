from typing import Any, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.refactor_agent import RefactorAgent
from agents.security_agent import SecurityAgent
from agents.summary_agent import SummaryAgent


class ReviewState(TypedDict):
    diff: str
    security_output: NotRequired[dict[str, Any]]
    refactor_output: NotRequired[dict[str, Any]]
    final_review: NotRequired[dict[str, Any]]


async def security_node(state: ReviewState) -> dict[str, Any]:
    return {"security_output": await SecurityAgent().review_diff(state["diff"])}


async def refactor_node(state: ReviewState) -> dict[str, Any]:
    return {"refactor_output": await RefactorAgent().review_diff(state["diff"])}


async def summary_node(state: ReviewState) -> dict[str, Any]:
    summary = await SummaryAgent().summarize_reviews(
        state.get("security_output"),
        state.get("refactor_output"),
    )
    return {"final_review": summary}


graph = StateGraph(ReviewState)
graph.add_node("security_node", security_node)
graph.add_node("refactor_node", refactor_node)
graph.add_node("summary_node", summary_node)

graph.add_edge(START, "security_node")
graph.add_edge(START, "refactor_node")
graph.add_edge(["security_node", "refactor_node"], "summary_node")
graph.add_edge("summary_node", END)

review_graph = graph.compile()
