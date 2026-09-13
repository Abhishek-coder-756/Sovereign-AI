# Sovereign AI (SIH26117) — Quick Start Guide

## Prerequisites
1. **Python 3.10+** (with virtual environment recommended)
2. **MySQL Server** (running locally on port 3306)
3. **Ollama** (running locally with `qwen2.5:3b` and `qwen2.5vl:3b`)

---

## 1. Installation
Install all required dependencies:
```bash
pip install -r requirements.txt
```

---

## 2. Database Configuration
Database connection details are defined in `db.py`:
- **Host**: `127.0.0.1`
- **Port**: `3306`
- **Database**: `sovereign_ai`
- **User**: `sovereign_app` (or your MySQL user)
- **Password**: `SovAI2026_Test!` (or your MySQL password)

Database schema migrations run **automatically** on FastAPI startup (`backend/app/security/migration.py`). No manual schema alteration is required.

---

## 3. Mandatory Role-Based Password Rules
When registering or creating passwords, the following organizational prefix convention is strictly enforced:
- **Administrator**: Prefix `admin` (e.g., `adminSecret123!`, min 8 characters)
- **Operator**: Prefix `operator` (e.g., `operatorPass2026`, min 8 characters)
- **Employee**: Prefix `emp` (e.g., `empSecure#88`, min 8 characters)

---

## 4. Default Seed Accounts
Pre-configured approved accounts for testing:
- **Admin**:
  - Username: `admin`
  - Password: `admin12345`
  - Company: `MRPL`
  - Role: `admin`
- **Operator**:
  - Username: `operator`
  - Password: `operator12345`
  - Company: `MRPL`
  - Role: `operator`

---

## 5. Starting the Server
Run the FastAPI application with Uvicorn:
```bash
python app.py
# or
uvicorn app.py:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser and navigate to:
```
http://localhost:8000/
```

---

## 6. Running Verification Tests
Execute the comprehensive 70-test verification suite:
```bash
python test_auth_admin_suite.py
```
This tests:
- Database integrity & table preservation
- Role prefix validation & bcrypt hashing
- Registration & pending approval lifecycle
- RBAC permissions & admin endpoint security
- User disable/enable & soft deletion
- Audit logging in MySQL
- Document, conversation, and company data isolation
