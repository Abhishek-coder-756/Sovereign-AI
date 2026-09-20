from langgraph.graph import StateGraph, START, END

from .state import AgentState
from .agent import (
    intent_node,
    vision_node,
    calculator_node,
    file_node,
    spreadsheet_node,
    general_node,
    pdf_node,
    check_result,
    generate_answer,
)


def route_intent(state: AgentState) -> str:
    """
    Route the request based on the intent detected by intent_node().
    """

    intent = state.get("intent", "general")

    if intent == "vision":
        return "vision"

    if intent == "spreadsheet":
        return "spreadsheet"

    if intent == "calculator":
        return "calculator"
    
    if intent == "pdf":
        return "pdf"


    if intent == "document":
        return "file"

    return "general"


def build_agent():
    """
    Build and compile the Sovereign AI LangGraph workflow.

    Flow:

        START
          ↓
        intent
          ↓
        route
          ↓
        ┌───────────────┬──────────────┬──────────────┐
        │               │              │              │
      vision       spreadsheet    calculator       file
        │               │              │              │
        └───────────────┴──────────────┴──────────────┘
                        ↓
                       check
                        ↓
                      answer
                        ↓
                       END
    """

    graph = StateGraph(AgentState)

    # --------------------------------------------------------
    # Nodes
    # --------------------------------------------------------

    graph.add_node("intent", intent_node)

    graph.add_node("vision", vision_node)
    graph.add_node("spreadsheet", spreadsheet_node)
    graph.add_node("calculator", calculator_node)
    graph.add_node("file", file_node)
    graph.add_node("pdf", pdf_node)
    graph.add_node("general", general_node)

    graph.add_node("check", check_result)
    graph.add_node("answer", generate_answer)

    # --------------------------------------------------------
    # Start
    # --------------------------------------------------------

    graph.add_edge(
        START,
        "intent"
    )

    # --------------------------------------------------------
    # Intent routing
    # --------------------------------------------------------

    graph.add_conditional_edges(
        "intent",
        route_intent,
        {
            "vision": "vision",
            "spreadsheet": "spreadsheet",
            "calculator": "calculator",
            "pdf": "pdf",
            "file": "file",
            "general": "general",
        }
    )

    # --------------------------------------------------------
    # Every execution node goes to check
    # --------------------------------------------------------

    for node_name in [
        "vision",
        "spreadsheet",
        "calculator",
        "file",
        "pdf",
        "general",
    ]:

        graph.add_edge(
            node_name,
            "check"
        )

    # --------------------------------------------------------
    # Check → Answer → END
    # --------------------------------------------------------

    graph.add_edge(
        "check",
        "answer"
    )

    graph.add_edge(
        "answer",
        END
    )

    return graph.compile()