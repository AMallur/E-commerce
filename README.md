# Aurora Accounting Workspace

Aurora Accounting Workspace is an AI-augmented bookkeeping cockpit inspired by modern close platforms. It ships with a FastAPI backend, a glassmorphism dashboard UI, and an in-memory double-entry engine that can be swapped for a persistent datastore. The app highlights real-time metrics, renders core financial statements, and lets teams capture balanced journal entries directly from the browser.

## Features

- FastAPI service with JSON endpoints for accounts, journal entries, and financial statements
- In-memory accounting engine with double-entry enforcement, demo data seeding, and cash-flow tagging
- Rich single-page dashboard showing cash, receivables, payables, income statement, and balance sheet snapshots
- Quick journal capture form with automatic balancing validation and tag support for operating/investing/financing activities
- Configurable currency, fiscal year start month, and demo seeding via environment variables

## Getting Started

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
```

Create a `.env` file to override settings if desired:

```
APP_NAME=Aurora Accounting Workspace
DEFAULT_CURRENCY=USD
FISCAL_YEAR_START_MONTH=1
SEED_DEMO_DATA=true
MAX_ENTRIES_RETURNED=200
```

Run the development server:

```bash
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) to interact with the dashboard. The API surface is available under `/docs` thanks to FastAPI's automatic OpenAPI generation.

## API Overview

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/accounts` | GET | List all accounts in the ledger |
| `/api/accounts` | POST | Create a new ledger account |
| `/api/journal` | GET | Return recent journal entries (bounded by `MAX_ENTRIES_RETURNED`) |
| `/api/journal` | POST | Record a balanced journal entry |
| `/api/dashboard` | GET | Aggregated cash, net income, receivables, and payables |
| `/api/reports/balance-sheet` | GET | Balance sheet snapshot |
| `/api/reports/income-statement` | GET | Income statement snapshot |
| `/api/reports/cash-flow` | GET | Cash flow summary grouped by operating/investing/financing |

All monetary values are returned as decimal numbers rounded to two places.

## Testing

```bash
pytest
```

The test suite covers the accounting engine to ensure debits and credits balance, statement rollups reconcile, and cash-flow tags allocate changes correctly.

## Extending

- Replace the in-memory engine with a database-backed repository by adapting `AccountingEngine`
- Add authentication middleware for multi-tenant deployments
- Wire up LLM copilots for anomaly detection, variance explanations, and proactive close tasks

## License

This project is provided for educational and prototyping purposes.
