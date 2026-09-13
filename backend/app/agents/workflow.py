from langgraph.graph import StateGraph, START, END

from .state import AgentState
from .agent import (
    create_plan,
    vision_node,
    rag_node,
    multimodal_node,
    calculator_node,
    file_node,
    spreadsheet_node,
    code_node,
    general_node,
    execute_tool,
    check_result,
    generate_answer,
    global_rag_node,
)


def route_intent(state: AgentState) -> str:
    """
    Route from planner to the appropriate capability node based on intent and knowledge mode.
    """
    mode = state.get("knowledge_mode", "private")
    intent = state.get("intent", "general_local_chat")

    if mode == "global":
        if intent == "calculator":
            return "calculator"
        elif intent in ("file_read", "file_write"):
            return "file"
        elif intent == "code_execution":
            return "code"
        elif intent == "image_only":
            return "vision"
        else:
            return "global_rag"

    if intent == "image_only":
        return "vision"
    elif intent == "document_rag":
        return "rag"
    elif intent == "multimodal_rag":
        return "multimodal"
    elif intent == "calculator":
        return "calculator"
    elif intent in ("file_read", "file_write"):
        return "file"
    elif intent == "spreadsheet":
        return "spreadsheet"
    elif intent == "code_execution":
        return "code"
    else:
        return "general"


def build_agent():
    """
    Build and compile the LangGraph orchestrating agent.

    Workflow:
    START
      ↓
    planner
      ↓ (conditional route)
    [ vision | rag | multimodal | calculator | file | spreadsheet | code | general ]
      ↓
    check
      ↓
    answer
      ↓
    END
    """
    graph = StateGraph(AgentState)

    graph.add_node("planner", create_plan)
    graph.add_node("vision", vision_node)
    graph.add_node("rag", rag_node)
    graph.add_node("multimodal", multimodal_node)
    graph.add_node("calculator", calculator_node)
    graph.add_node("file", file_node)
    graph.add_node("spreadsheet", spreadsheet_node)
    graph.add_node("code", code_node)
    graph.add_node("general", general_node)
    graph.add_node("global_rag", global_rag_node)
    graph.add_node("check", check_result)
    graph.add_node("answer", generate_answer)

    graph.add_edge(START, "planner")

    graph.add_conditional_edges(
        "planner",
        route_intent,
        {
            "vision": "vision",
            "rag": "rag",
            "multimodal": "multimodal",
            "calculator": "calculator",
            "file": "file",
            "spreadsheet": "spreadsheet",
            "code": "code",
            "general": "general",
            "global_rag": "global_rag",
        }
    )

    for node_name in [
        "vision",
        "rag",
        "multimodal",
        "calculator",
        "file",
        "spreadsheet",
        "code",
        "general",
        "global_rag",
    ]:
        graph.add_edge(node_name, "check")

    graph.add_edge("check", "answer")
    graph.add_edge("answer", END)

    return graph.compile()