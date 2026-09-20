"""
Sovereign AI - Agent
SIH26117

Fast local routing for:
- Images
- Documents
- Spreadsheets
- Calculator
- General local LLM

Architecture:

    FastAPI
       ↓
    LangGraph
       ↓
    intent_node
       ↓
    execute_tool
       ↓
    vision / spreadsheet / calculator / document / general
       ↓
    check_result
       ↓
    generate_answer

Models:
    Text   -> qwen2.5:3b
    Vision -> llava:7b

Everything is designed for local Ollama processing.
"""

from pathlib import Path
import tempfile

from PIL import Image


# ============================================================
# OPTIONAL IMPORTS
# ============================================================

try:
    import ollama
except ImportError:
    ollama = None


# ============================================================
# STATE
# ============================================================

try:
    from backend.app.agents.state import AgentState
except Exception:

    class AgentState(dict):
        """
        Fallback state.

        The real application uses a TypedDict,
        therefore LangGraph passes dictionaries.
        """

        pass


# ============================================================
# TOOLS
# ============================================================

try:
    from backend.app.tools.calculator import calculate
except Exception:
    calculate = None


try:
    from backend.app.tools.file_reader import read_file
except Exception:
    read_file = None


try:
    from backend.app.tools.spreadsheet import analyze_spreadsheet
except Exception:
    analyze_spreadsheet = None


try:
    from backend.app.tools.code_sandbox import execute_code
except Exception:
    execute_code = None

try:
    from backend.app.tools.pdf_generator import generate_pdf
except Exception:
    generate_pdf = None


# ============================================================
# CONFIGURATION
# ============================================================

TEXT_MODEL = "qwen2.5:3b"
VISION_MODEL = "llava:7b"

VISION_KEEP_ALIVE = "30m"

MAX_IMAGE_SIZE = 1024
JPEG_QUALITY = 80

VISION_NUM_PREDICT = 120
VISION_NUM_CTX = 4096

# Maximum amount of extracted document text sent to Qwen.
# This prevents very large PDFs from overflowing the context.
MAX_DOCUMENT_CHARS = 12000


# ============================================================
# IMAGE PREPARATION
# ============================================================

def prepare_image(image_path):
    """
    Prepare an image for LLaVA.

    Steps:
        1. Check file exists
        2. Open image
        3. Convert to RGB
        4. Resize large images
        5. Save optimized temporary JPEG

    Returns:
        Temporary JPEG path
    """

    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Image file not found: {image_path}"
        )

    image = Image.open(path)

    # Convert PNG/RGBA/etc. to RGB
    image = image.convert("RGB")

    # Resize large images
    if max(image.size) > MAX_IMAGE_SIZE:

        image.thumbnail(
            (MAX_IMAGE_SIZE, MAX_IMAGE_SIZE),
            Image.Resampling.LANCZOS
        )

    # Create temporary JPEG
    temp_file = tempfile.NamedTemporaryFile(
        suffix=".jpg",
        delete=False
    )

    temp_path = temp_file.name
    temp_file.close()

    image.save(
        temp_path,
        format="JPEG",
        quality=JPEG_QUALITY,
        optimize=True
    )

    return temp_path


# ============================================================
# FAST VISION
# ============================================================

def fast_vision_answer(image_path, query):
    """
    Direct image question answering using LLaVA.

    Flow:

        Image
          ↓
        Prepare image
          ↓
        Ollama
          ↓
        LLaVA 7B
          ↓
        Answer

    No RAG/FAISS is used for simple image-only questions.
    """

    if ollama is None:
        return (
            "Vision error: Python ollama package "
            "is not installed."
        )

    prepared_image = None

    try:

        # ----------------------------------------------------
        # Prepare image
        # ----------------------------------------------------

        prepared_image = prepare_image(image_path)

        # ----------------------------------------------------
        # Clean query
        # ----------------------------------------------------

        query = str(query or "").strip()

        if not query:

            query = (
                "Describe this image briefly "
                "in 2 or 3 sentences."
            )

        # ----------------------------------------------------
        # LLaVA
        # ----------------------------------------------------

        response = ollama.chat(
            model=VISION_MODEL,

            messages=[
                {
                    "role": "user",
                    "content": query,
                    "images": [prepared_image],
                }
            ],

            options={
                "temperature": 0.2,
                "num_predict": VISION_NUM_PREDICT,
                "num_ctx": VISION_NUM_CTX,
            },

            keep_alive=VISION_KEEP_ALIVE,
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Current Ollama Python package returns ChatResponse,
        # not necessarily a normal dictionary.
        # ----------------------------------------------------

        answer = ""

        # Current Ollama ChatResponse
        try:

            answer = response.message.content or ""

        except Exception:

            answer = ""

        # Dictionary fallback
        if not answer and isinstance(response, dict):

            message = response.get(
                "message",
                {}
            )

            if isinstance(message, dict):

                answer = message.get(
                    "content",
                    ""
                )

        answer = str(answer).strip()

        if answer:

            return answer

        return "LLaVA returned an empty response."

    except Exception as e:

        return (
            "Vision processing error: "
            f"{type(e).__name__}: {str(e)}"
        )

    finally:

        # ----------------------------------------------------
        # Delete temporary image
        # ----------------------------------------------------

        if prepared_image:

            try:

                Path(prepared_image).unlink(
                    missing_ok=True
                )

            except Exception:
                pass


# ============================================================
# IMAGE QUESTION DETECTION
# ============================================================

def is_image_only_question(query):
    """
    Detect simple image questions.

    These questions can go directly to LLaVA
    without document retrieval.
    """

    q = str(query or "").lower().strip()

    image_keywords = [

        "describe image",
        "describe this image",

        "what is in this image",
        "what does this image show",

        "what is shown",

        "main subject",

        "identify the object",

        "what object",

        "what do you see",

        "read the image",

        "analyze this image",

        "look at this image",

        "image",

        "photo",

        "picture",

    ]

    return any(
        keyword in q
        for keyword in image_keywords
    )


# ============================================================
# INTENT CLASSIFICATION
# ============================================================

def classify_intent(
    query,
    image_path=None,
    file_path=None
):
    """
    Decide which local tool should handle the request.

    Priority:

        Image
        Spreadsheet
        Calculator
        Code
        Document
        General
    """

    q = str(query or "").lower().strip()

        # ========================================================
    # PDF CREATION
    # ========================================================

    pdf_creation_words = [
        "create pdf",
        "create a pdf",
        "generate pdf",
        "generate a pdf",
        "make pdf",
        "make a pdf",
        "create report pdf",
        "generate report pdf",
        "make report pdf",
    ]

    if any(
        phrase in q
        for phrase in pdf_creation_words
    ):
        return "pdf"

    # ========================================================
    # IMAGE
    # ========================================================

    if image_path:

        if is_image_only_question(q):

            return "vision"

        visual_words = [

            "image",
            "photo",
            "picture",
            "visual",

            "object",
            "person",

            "color",
            "scene",

            "shown",
            "visible",

            "barcode",
            "diagram",

        ]

        if any(
            word in q
            for word in visual_words
        ):

            return "vision"

    # ========================================================
    # SPREADSHEET
    # ========================================================

    spreadsheet_words = [

        "csv",
        "spreadsheet",
        "excel",

        "sales",
        "rows",
        "columns",

        "highest",
        "lowest",

        "average",
        "mean",

        "maximum",
        "minimum",

        "top 5",
        "top 10",

        "bottom 5",
        "bottom 10",

        "correlation",

    ]

    if file_path:

        suffix = Path(
            file_path
        ).suffix.lower()

        if suffix in (
            ".csv",
            ".xlsx",
            ".xls",
        ):

            return "spreadsheet"

    if any(
        word in q
        for word in spreadsheet_words
    ):

        if file_path:

            suffix = Path(
                file_path
            ).suffix.lower()

            if suffix in (
                ".csv",
                ".xlsx",
                ".xls",
            ):

                return "spreadsheet"

    # ========================================================
    # CALCULATOR
    # ========================================================

    calculation_words = [

        "calculate",
        "solve",

        "plus",
        "minus",

        "multiply",
        "divide",

        "percentage",
        "percent",

    ]

    if any(
        word in q
        for word in calculation_words
    ):

        return "calculator"

    # ========================================================
    # CODE
    # ========================================================

    code_words = [

        "write code",

        "python code",
        "cpp code",
        "c++ code",

        "javascript code",

        "program",
        "function",

        "debug",

    ]

    if any(
        word in q
        for word in code_words
    ):

        return "code"

    # ========================================================
    # DOCUMENT
    # ========================================================

    if file_path:

        suffix = Path(
            file_path
        ).suffix.lower()

        document_extensions = (

            ".pdf",
            ".doc",
            ".docx",

            ".ppt",
            ".pptx",

            ".txt",
            ".md",
            ".text",
            ".log",

        )

        if suffix in document_extensions:

            return "document"

    # ========================================================
    # GENERAL
    # ========================================================

    return "general"


# ============================================================
# VISION NODE
# ============================================================

def vision_node(state):
    """
    LangGraph vision node.

    IMPORTANT:
    `state` is a dictionary because AgentState is a TypedDict.
    """

    query = state.get(
        "user_query",
        state.get(
            "query",
            ""
        )
    )

    image_path = state.get(
        "image_path",
        ""
    )

    # --------------------------------------------------------
    # No image
    # --------------------------------------------------------

    if not image_path:

        state["final_answer"] = (
            "No image was provided."
        )

        state["intent"] = "vision"

        return state

    # --------------------------------------------------------
    # Run LLaVA
    # --------------------------------------------------------

    state["final_answer"] = fast_vision_answer(
        image_path=image_path,
        query=query,
    )

    state["intent"] = "vision"

    # Store simple observation metadata
    state["image_observation"] = {
        "model": VISION_MODEL,
        "mode": "direct_vision",
    }

    return state


# ============================================================
# SPREADSHEET NODE
# ============================================================

def spreadsheet_node(state):
    """
    Spreadsheet processing.
    """

    query = state.get(
        "user_query",
        state.get(
            "query",
            ""
        )
    )

    file_path = state.get(
        "file_path",
        ""
    )

    # --------------------------------------------------------
    # No spreadsheet
    # --------------------------------------------------------

    if not file_path:

        state["final_answer"] = (
            "No spreadsheet was provided."
        )

        state["intent"] = "spreadsheet"

        return state

    # --------------------------------------------------------
    # Tool unavailable
    # --------------------------------------------------------

    if analyze_spreadsheet is None:

        state["final_answer"] = (
            "Spreadsheet tool is unavailable."
        )

        state["intent"] = "spreadsheet"

        return state

    # --------------------------------------------------------
    # Analyze
    # --------------------------------------------------------

    try:

        state["final_answer"] = analyze_spreadsheet(
            file_path,
            query
        )

    except Exception as e:

        state["final_answer"] = (
            "Spreadsheet processing error: "
            f"{type(e).__name__}: {str(e)}"
        )

    state["intent"] = "spreadsheet"

    return state


# ============================================================
# CALCULATOR NODE
# ============================================================

def calculator_node(state):
    """
    Calculator processing.
    """

    query = state.get(
        "user_query",
        state.get(
            "query",
            ""
        )
    )

    if calculate is None:

        state["final_answer"] = (
            "Calculator tool is unavailable."
        )

        state["intent"] = "calculator"

        return state

    try:

        state["final_answer"] = calculate(
            query
        )

    except Exception as e:

        state["final_answer"] = (
            "Calculator error: "
            f"{type(e).__name__}: {str(e)}"
        )

    state["intent"] = "calculator"

    return state


# ============================================================
# FILE / DOCUMENT NODE
# ============================================================

def file_node(state):
    """
    Read a local document and answer the user's
    question using the local Qwen2.5 3B model.

    Flow:

        PDF / TXT / MD
              ↓
        read_file()
              ↓
        Extracted text
              ↓
        User question + document
              ↓
        qwen2.5:3b
              ↓
        Short direct answer
    """

    # --------------------------------------------------------
    # Get file path
    # --------------------------------------------------------

    file_path = state.get(
        "file_path",
        ""
    )

    # --------------------------------------------------------
    # No file
    # --------------------------------------------------------

    if not file_path:

        state["final_answer"] = (
            "No file was provided."
        )

        state["intent"] = "document"

        return state

    # --------------------------------------------------------
    # File reader unavailable
    # --------------------------------------------------------

    if read_file is None:

        state["final_answer"] = (
            "File reader is unavailable."
        )

        state["intent"] = "document"

        return state

    try:

        # ----------------------------------------------------
        # Read document
        # ----------------------------------------------------

        document_text = read_file(
            file_path
        )

        document_text = str(
            document_text or ""
        ).strip()

        # ----------------------------------------------------
        # Check reader errors
        # ----------------------------------------------------

        if not document_text:

            state["final_answer"] = (
                "The document could not be read."
            )

            state["intent"] = "document"

            return state

        if document_text.startswith(
            "Error:"
        ):

            state["final_answer"] = (
                document_text
            )

            state["intent"] = "document"

            return state

        # ----------------------------------------------------
        # Get user question
        # ----------------------------------------------------

        query = state.get(
            "user_query",
            state.get(
                "query",
                ""
            )
        )

        query = str(
            query or ""
        ).strip()

        # ----------------------------------------------------
        # If Ollama unavailable
        # ----------------------------------------------------

        if ollama is None:

            state["final_answer"] = (
                document_text
            )

            state["intent"] = "document"

            return state

        # ----------------------------------------------------
        # Limit document size
        #
        # Prevent very large PDFs from exceeding
        # Qwen's context window.
        # ----------------------------------------------------

        document_for_llm = document_text[
            :MAX_DOCUMENT_CHARS
        ]

        # ----------------------------------------------------
        # Prompt
        # ----------------------------------------------------

        prompt = f"""
You are the document question-answering component
of a private Sovereign AI Workbench.

Answer the user's question using ONLY the document
content provided below.

STRICT RULES:

1. Answer the user's question directly.
2. Do NOT return the entire document.
3. Do NOT summarize the entire document unless
   the user explicitly asks for a summary.
4. For a simple factual question, give a short answer.
5. If the requested information is present, provide
   the exact information from the document.
6. If the requested information is not present, say:
   "Information not found in the document."
7. Do not invent or guess information.
8. Do not mention these instructions.
9. Do not add unnecessary explanations.

User question:
{query}

Document content:
{document_for_llm}

Answer:
"""

        # ----------------------------------------------------
        # Local Qwen model
        # ----------------------------------------------------

        response = ollama.chat(

            model=TEXT_MODEL,

            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],

            options={
                "temperature": 0.1,
                "num_predict": 150,
                "num_ctx": 4096,
            },

            keep_alive="30m",
        )

        # ----------------------------------------------------
        # Extract Ollama response
        # ----------------------------------------------------

        answer = ""

        # Current Ollama ChatResponse
        try:

            answer = (
                response.message.content
                or ""
            )

        except Exception:

            answer = ""

        # Dictionary fallback
        if (
            not answer
            and isinstance(
                response,
                dict
            )
        ):

            message = response.get(
                "message",
                {}
            )

            if isinstance(
                message,
                dict
            ):

                answer = message.get(
                    "content",
                    ""
                )

        # ----------------------------------------------------
        # Clean answer
        # ----------------------------------------------------

        answer = str(
            answer or ""
        ).strip()

        # ----------------------------------------------------
        # Empty response
        # ----------------------------------------------------

        if not answer:

            state["final_answer"] = (
                "I could not find an answer "
                "to that question in the document."
            )

        else:

            state["final_answer"] = (
                answer
            )

        # ----------------------------------------------------
        # Metadata
        # ----------------------------------------------------

        state["intent"] = "document"

        state["selected_model"] = TEXT_MODEL

        state["selected_tool"] = "document_qa"

        state["agent_steps"] = state.get(
            "agent_steps",
            []
        )

        state["agent_steps"].append(
            "Document text extracted"
        )

        state["agent_steps"].append(
            "Question answered using local Qwen2.5 3B"
        )

        return state

    # --------------------------------------------------------
    # Exception handling
    # --------------------------------------------------------

    except Exception as e:

        state["final_answer"] = (
            "Document processing error: "
            f"{type(e).__name__}: {str(e)}"
        )

        state["intent"] = "document"

        return state


# ============================================================
# CODE NODE
# ============================================================

def code_node(state):
    """
    Execute code if the code sandbox is available.

    This node is included for compatibility,
    but the current workflow may route code requests
    to the general node depending on workflow.py.
    """

    query = state.get(
        "user_query",
        state.get(
            "query",
            ""
        )
    )

    if execute_code is None:

        state["final_answer"] = (
            "Code execution tool is unavailable."
        )

        state["intent"] = "code"

        return state

    try:

        state["final_answer"] = execute_code(
            query
        )

    except Exception as e:

        state["final_answer"] = (
            "Code execution error: "
            f"{type(e).__name__}: {str(e)}"
        )

    state["intent"] = "code"

    return state


# ============================================================
# GENERAL TEXT NODE
# ============================================================

def general_node(state):
    """
    General local text question using Qwen2.5 3B.
    """

    query = state.get(
        "user_query",
        state.get(
            "query",
            ""
        )
    )

    if ollama is None:

        state["final_answer"] = (
            "Ollama is unavailable."
        )

        state["intent"] = "general"

        return state

    try:

        response = ollama.chat(

            model=TEXT_MODEL,

            messages=[
                {
                    "role": "user",
                    "content": query,
                }
            ],

            options={
                "temperature": 0.3,
                "num_predict": 250,
                "num_ctx": 2048,
            },

            keep_alive="30m",
        )

        answer = ""

        # Current Ollama response
        try:

            answer = response.message.content or ""

        except Exception:

            answer = ""

        # Dictionary fallback
        if not answer and isinstance(
            response,
            dict
        ):

            answer = (
                response
                .get("message", {})
                .get("content", "")
            )

        state["final_answer"] = (
            str(answer).strip()
        )

    except Exception as e:

        state["final_answer"] = (
            "LLM error: "
            f"{type(e).__name__}: {str(e)}"
        )

    state["intent"] = "general"

    return state


# ============================================================
# INTENT NODE
# ============================================================

def intent_node(state):
    """
    Determine the correct route.

    This is intentionally dictionary-based because
    LangGraph passes AgentState as a dictionary.
    """

    query = state.get(
        "user_query",
        state.get(
            "query",
            ""
        )
    )

    image_path = state.get(
        "image_path",
        ""
    )

    file_path = state.get(
        "file_path",
        ""
    )

    intent = classify_intent(

        query=query,

        image_path=image_path,

        file_path=file_path,

    )

    state["intent"] = intent

    return state

# ============================================================
# PDF NODE
# ============================================================

def pdf_node(state):
    """
    Generate a PDF locally using ReportLab.
    """

    query = state.get(
        "user_query",
        state.get(
            "query",
            ""
        )
    )

    query = str(
        query or ""
    ).strip()

    if generate_pdf is None:

        state["final_answer"] = (
            "PDF generator is unavailable."
        )

        state["intent"] = "pdf"

        return state

    try:

        # Extract actual PDF content from the user's request
        content = query
        bottom_text = ""

        lower_query = query.lower()

        # "and write at bottom hello world"
        marker = " and write at bottom "

        if marker in lower_query:

            marker_index = lower_query.index(marker)

            before_footer = query[:marker_index]

            bottom_text = query[
                marker_index + len(marker):
            ].strip()

            include_marker = "include "
            containing_marker = "containing "

            include_index = before_footer.lower().find(
                include_marker
            )

            containing_index = before_footer.lower().find(
                containing_marker
            )

            if include_index != -1:

                content = before_footer[
                    include_index + len(include_marker):
                ].strip()

            elif containing_index != -1:

                content = before_footer[
                    containing_index + len(containing_marker):
                ].strip()

            else:

                content = before_footer.strip()

        # "and put Team Tech Byte at the bottom"
        elif (
            " and put " in lower_query
            and " at the bottom" in lower_query
        ):

            put_start = lower_query.index(
                " and put "
            )

            bottom_end = lower_query.index(
                " at the bottom",
                put_start
            )

            bottom_text = query[
                put_start + len(" and put "):
                bottom_end
            ].strip()

            before_footer = query[
                :put_start
            ].strip()

            include_marker = "include "
            containing_marker = "containing "

            include_index = before_footer.lower().find(
                include_marker
            )

            containing_index = before_footer.lower().find(
                containing_marker
            )

            if include_index != -1:

                content = before_footer[
                    include_index + len(include_marker):
                ].strip()

            elif containing_index != -1:

                content = before_footer[
                    containing_index + len(containing_marker):
                ].strip()

            else:

                content = before_footer.strip()

        result = generate_pdf(
            content=content,
            filename="sovereign_ai_report.pdf",
            title="Sovereign AI Report",
            bottom_text=bottom_text
        )

        state["final_answer"] = result

        state["intent"] = "pdf"

        state["selected_tool"] = "pdf_generator"

        state["pdf_filename"] = "sovereign_ai_report.pdf"

        state["agent_steps"] = state.get(
            "agent_steps",
            []
        )

        state["agent_steps"].append(
            "PDF generated locally using ReportLab"
        )

        return state

    except Exception as e:

        state["final_answer"] = (
            "PDF generation error: "
            f"{type(e).__name__}: {str(e)}"
        )

        state["intent"] = "pdf"

        return state


# ============================================================
# EXECUTE TOOL
# ============================================================

def execute_tool(state):
    """
    Execute the node selected by intent.
    """

    intent = state.get(
        "intent",
        "general"
    )

    if intent == "pdf":
        return pdf_node(state)

    if intent == "vision":

        return vision_node(state)

    if intent == "spreadsheet":

        return spreadsheet_node(state)

    if intent == "calculator":

        return calculator_node(state)

    if intent == "document":

        return file_node(state)

    if intent == "code":

        return code_node(state)

    return general_node(state)


# ============================================================
# RESULT CHECK
# ============================================================

def check_result(state):
    """
    Check whether a result was produced.
    """

    answer = state.get(
        "final_answer",
        ""
    )

    answer = str(
        answer or ""
    ).strip()

    state["result_checked"] = bool(
        answer
    )

    if not answer:

        state["final_answer"] = (
            "I could not generate an answer."
        )

        state["result_checked"] = False

    return state


# ============================================================
# ANSWER GENERATION
# ============================================================

def generate_answer(state):
    """
    Final answer node.

    Tool nodes already generate the final answer,
    so this node simply returns that answer.
    """

    answer = state.get(
        "final_answer",
        ""
    )

    answer = str(
        answer or ""
    ).strip()

    if answer:

        state["final_answer"] = answer

        return state

    state["final_answer"] = (
        "I could not generate an answer."
    )

    return state


# ============================================================
# MAIN AGENT
# ============================================================

def run_agent(
    query,
    image_path=None,
    file_path=None,
    **kwargs
):
    """
    Direct agent entry point.

    Example:

        run_agent(
            query="Describe this image",
            image_path="/path/to/image.jpg"
        )

    Example:

        run_agent(
            query="What is the PS category?",
            file_path="/path/to/file.pdf"
        )
    """

    # --------------------------------------------------------
    # Create dictionary state
    # --------------------------------------------------------

    state = {

        "user_query": query or "",

        "image_path": image_path or "",

        "file_path": file_path or "",

        "results": [],

        "plan": [],

        "sources": [],

        "agent_steps": [],

    }

    # Add optional values
    state.update(kwargs)

    # --------------------------------------------------------
    # Intent
    # --------------------------------------------------------

    state = intent_node(
        state
    )

    # --------------------------------------------------------
    # Execute
    # --------------------------------------------------------

    state = execute_tool(
        state
    )

    # --------------------------------------------------------
    # Check
    # --------------------------------------------------------

    state = check_result(
        state
    )

    # --------------------------------------------------------
    # Final answer
    # --------------------------------------------------------

    state = generate_answer(
        state
    )

    return state.get(
        "final_answer",
        ""
    )


# ============================================================
# COMPATIBILITY ALIASES
# ============================================================

agent = run_agent

process_request = run_agent

handle_request = run_agent


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)

    print("SOVEREIGN AI AGENT")

    print("=" * 60)

    print(
        f"Text model   : {TEXT_MODEL}"
    )

    print(
        f"Vision model : {VISION_MODEL}"
    )

    print(
        f"Keep alive   : {VISION_KEEP_ALIVE}"
    )

    print(
        f"Image size   : {MAX_IMAGE_SIZE}px"
    )

    print(
        f"Max document : {MAX_DOCUMENT_CHARS} chars"
    )

    print("=" * 60)