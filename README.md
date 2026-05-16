# Collections Email Automation

This project is a Python-based collections email automation prototype.

The system reads an Accounts Receivable Excel file, identifies overdue invoices eligible for collection reminders, checks sample customer replies, classifies replies using rule-based logic, decides the final action, generates email templates, and exports CSV output reports.

> This project runs in safe/test mode. It does not send real emails.


## How to Run the Project

This project has three runnable parts:

1. Python command-line workflow
2. FastAPI backend
3. React frontend UI

---

## 1. Run the Python Command-Line Workflow

Use this option if you only want to process the Excel file and generate CSV outputs.

From the project root folder, run:

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/main.py
```
## 2. Run the FastAPI Backend

Use this option if you want to run the backend API for the React UI.

From the project root folder, run:

```bash
uvicorn backend.api:app --reload --port 8000

http://localhost:8000
```

## 3. Run the React Frontend

Open a new terminal and run:

```bash
cd frontend
npm install
npm run dev
```

The React app will usually run at:


### Terminal 1: Start Backend

```bash
uvicorn src.api:app --reload --port 8000
```

### Terminal 2: Start Frontend

```bash
cd frontend
npm install
npm run dev
```
## Technology Stack

This prototype uses:

```txt
Python
Pandas
OpenPyXL
JSON
CSV
FastAPI
React
Rule-based classification
```

---

