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

---

## 👨‍💻 My Contributions — Abhishek Singh Chauhan

I primarily contributed to the **backend development and AI integration** of
the Sovereign AI Workbench as part of the SIH26117 team project.

### 🔹 Backend Development

- Worked on the **FastAPI backend** and backend API architecture.
- Worked on API routing and request/response handling.
- Integrated frontend requests with backend AI workflows.
- Worked on AI-related backend endpoints and services.
- Worked with backend health monitoring and service-status functionality.
- Debugged and tested backend services during development.

### 🔹 RAG & Document Processing

- Worked on the backend **Retrieval-Augmented Generation (RAG)** workflow.
- Worked with document loading and processing.
- Worked with embeddings and **FAISS vector search**.
- Worked on connecting retrieved document context with local LLM processing.
- Tested document-based question-answering workflows.

### 🔹 CSV & Spreadsheet Processing

- Worked on backend processing of CSV and spreadsheet data.
- Worked on **column-wise CSV data handling**.
- Tested structured-data analysis through the backend.
- Worked on connecting spreadsheet analysis with AI responses.

### 🔹 Local AI Integration

- Worked on integrating **Ollama** with the backend.
- Connected backend workflows with locally running open-weight models.
- Worked with Qwen, Qwen2.5-Coder, LLaVA and Llama.
- Worked on connecting different AI models with appropriate backend workflows.

### 🔹 Multimodal / Vision AI

- Worked on the backend multimodal AI workflow.
- Integrated image-analysis requests with the local vision model.
- Worked with the FastAPI → AI workflow → Ollama → LLaVA pipeline.
- Tested and optimized image-analysis functionality.
- Worked on reducing vision-processing latency.

### 🔹 Performance Optimization

- Worked on improving local AI response performance.
- Worked with Ollama keep-alive configuration.
- Worked with embedding-cache optimization.
- Worked on optimizing the vision-processing workflow.

### 🔹 Security & Testing

- Worked with backend authentication and **Role-Based Access Control (RBAC)**.
- Worked with company/user access separation.
- Worked with audit-related backend functionality.
- Debugged FastAPI, dependency and AI integration issues.
- Tested backend APIs and complete AI workflows.

### 🔹 Development & Integration

- Integrated different backend components into the final application.
- Worked on debugging issues across backend, RAG, CSV and multimodal workflows.
- Contributed to testing and stabilizing the overall Sovereign AI Workbench.