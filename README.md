# Sovereign AI

### Secure. Private. Intelligent. On-Premise.

Sovereign AI is a secure, on-premise Agentic AI workbench designed for organizations that cannot expose confidential industrial data to external AI services.

It combines local open-weight Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), multimodal AI, controlled tools, Role-Based Access Control (RBAC), audit logging, and evidence-based responses into a single private AI environment.

---

## 🚀 Key Features

- 🔐 **On-Premise AI** — AI processing can run within the organization's infrastructure.
- 🧠 **Local Open-Weight LLMs** — Uses locally hosted models through Ollama.
- 📚 **Private RAG** — Search and retrieve information from confidential organizational documents.
- 👁️ **Multimodal AI** — Analyze images, scanned documents, inspection photographs, and visual information.
- 🤖 **Agentic AI** — AI can plan tasks and use controlled tools to complete multi-step workflows.
- 📊 **Spreadsheet Intelligence** — Analyze CSV and Excel files using deterministic data processing.
- 💻 **Secure Code Execution** — Execute supported analytical tasks inside a controlled sandbox.
- 👥 **RBAC** — Role-based access for administrators and users.
- 🏢 **Company Isolation** — Users can access only data belonging to their organization.
- 📝 **Audit Logging** — Important security and AI actions are recorded for accountability.
- 📖 **Evidence-Based Answers** — Responses can include document sources and citations.
- 🚫 **Evidence-Aware Refusal** — The system avoids presenting unsupported information as fact.
- 🌐 **Zero-Egress Architecture** — Designed to keep confidential AI processing and data inside the organization's environment.

---

## 🏗️ Architecture

```text
                    ┌───────────────────────┐
                    │       User            │
                    │   Web Application     │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │      FastAPI          │
                    │    Backend API        │
                    └───────────┬───────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │     RBAC     │ │ Agentic AI   │ │ Audit Logs   │
        │ Authentication│ │  Workflow    │ │              │
        └──────────────┘ └──────┬───────┘ └──────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
       ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
       │     RAG      │ │ Multimodal   │ │ Local Tools  │
       │ FAISS + BGE  │ │   Qwen-VL    │ │ Excel/Code   │
       └──────┬───────┘ └──────────────┘ └──────────────┘
              │
              ▼
       ┌────────────────────────────────┐
       │       Local AI Layer           │
       │                                │
       │  Ollama + Open-Weight LLMs     │
       └────────────────────────────────┘
              │
              ▼
       ┌────────────────────────────────┐
       │       Organization Data        │
       │ PDFs • DOCX • XLSX • CSV       │
       │ Images • Manuals • Reports     │
       └────────────────────────────────┘

🧠 AI Pipeline
User Request
     │
     ▼
Authentication & RBAC
     │
     ▼
Intent Detection
     │
     ├── Document Task ──────► RAG
     │
     ├── Image Task ─────────► Vision Model
     │
     ├── Spreadsheet Task ───► Pandas / Excel Analysis
     │
     ├── Calculation ────────► Calculator Tool
     │
     └── General Task ───────► Local LLM
                              │
                              ▼
                         Evidence Check
                              │
                              ▼
                       Final Response
                              │
                              ▼
                         Audit Log

🔒 Security & Privacy

Sovereign AI is designed around the principle:

Confidential data should remain under the organization’s control.

The platform is designed to keep sensitive documents, AI processing, embeddings, and enterprise data within the organization’s infrastructure.

Security Controls

* Local model inference
* JWT authentication
* Role-Based Access Control
* Company-level data isolation
* Permission-controlled AI tools
* Upload validation
* File size restrictions
* SSRF protection
* Audit logging
* Evidence verification
* Controlled code execution
* No direct exposure of database or model services

⸻

🛠️ Technology Stack

Backend

* Python
* FastAPI
* Uvicorn
* MySQL

AI / Machine Learning

* Ollama
* Qwen2.5
* Qwen2.5-VL
* Sentence Transformers
* BAAI BGE embeddings
* FAISS
* LangGraph

Data Processing

* Pandas
* NumPy
* PyPDF
* python-docx
* openpyxl

Frontend

* HTML5
* CSS3
* JavaScript
* Responsive UI

Infrastructure

* Local / On-Premise deployment
* Cloudflare Tunnel for development/demo access

📂 Supported Data
Sovereign AI can work with multiple enterprise data formats:
PDF
DOC
DOCX
PPT
PPTX
XLS
XLSX
CSV
TXT
MD
LOG

Images:
PNG
JPG
JPEG
WEBP
