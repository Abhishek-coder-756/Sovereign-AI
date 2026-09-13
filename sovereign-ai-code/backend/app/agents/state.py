from typing import TypedDict, List, Dict, Any, Optional


class AgentState(TypedDict, total=False):
    # Session & User context
    conversation_id: str
    company: str
    username: str
    user_query: str
    image_path: str
    uploaded_files: List[str]
    uploaded_images: List[str]
    conversation_history: List[Dict[str, Any]]
    knowledge_mode: Optional[str]  # "private" or "global"
    global_sources: Optional[List[Dict[str, Any]]]

    # Agent planning & routing
    intent: str
    source_scope: Optional[str]
    selected_documents: Optional[List[str]]
    plan: List[str]
    selected_model: str
    selected_tool: str
    agent_steps: List[str]

    # Execution & results
    results: List[str]
    documents: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    image_observation: Optional[Dict[str, Any]]
    verification: Dict[str, Any]
    final_answer: str
    result_checked: bool
    timings: Optional[Dict[str, Any]]
    error: Optional[str]