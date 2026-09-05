from langgraph.graph import END, StateGraph

from app.graph.nodes.catalog_agent import catalog_agent_node
from app.graph.nodes.checkout_agent import create_order_node
from app.graph.nodes.policy_agent import (
    policy_agent_checkout_node,
    policy_agent_retry_node,
)
from app.graph.nodes.shopping_agent import shopping_agent_node
from app.graph.state import AgentState


def build_browse_graph():
    """catalog -> shopping -> END

    Produces up to 3 tiered options (most affordable / best value /
    premium pick) for the user to choose from — nothing is added to the
    cart yet, so there's no policy gate in this graph. The gate happens
    once the user actually picks one, in policy_agent_add_to_cart_node
    (called directly from the /select-option endpoint, the same pattern
    used for upsell acceptance) — money-relevant state never changes
    without going through that gate, regardless of which path leads to it.
    """
    graph = StateGraph(AgentState)
    graph.add_node("catalog_agent", catalog_agent_node)
    graph.add_node("shopping_agent", shopping_agent_node)

    graph.set_entry_point("catalog_agent")
    graph.add_edge("catalog_agent", "shopping_agent")
    graph.add_edge("shopping_agent", END)
    return graph.compile()


def _checkout_route(state: dict) -> str:
    return "approved" if state.get("status") == "checkout_approved" else "denied"


def build_checkout_graph():
    """policy(checkout) -> [approved] -> create_order -> END
                         -> [denied]   -> END
    Invoked on initial checkout AND on each retry (a fresh order per retry).
    """
    graph = StateGraph(AgentState)
    graph.add_node("policy_agent_checkout", policy_agent_checkout_node)
    graph.add_node("create_order", create_order_node)

    graph.set_entry_point("policy_agent_checkout")
    graph.add_conditional_edges(
        "policy_agent_checkout",
        _checkout_route,
        {"approved": "create_order", "denied": END},
    )
    graph.add_edge("create_order", END)
    return graph.compile()


def _retry_route(state: dict) -> str:
    return "approved" if state.get("status") == "retry_approved" else "denied"


def build_retry_graph():
    """policy(retry) -> [approved] -> create_order (new order) -> END
                      -> [denied]   -> END (max retries exceeded, graceful stop)
    """
    graph = StateGraph(AgentState)
    graph.add_node("policy_agent_retry", policy_agent_retry_node)
    graph.add_node("create_order", create_order_node)

    graph.set_entry_point("policy_agent_retry")
    graph.add_conditional_edges(
        "policy_agent_retry",
        _retry_route,
        {"approved": "create_order", "denied": END},
    )
    graph.add_edge("create_order", END)
    return graph.compile()


browse_graph = build_browse_graph()
checkout_graph = build_checkout_graph()
retry_graph = build_retry_graph()
