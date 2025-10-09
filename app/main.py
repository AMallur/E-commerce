"""FastAPI application exposing the Aurora accounting workspace."""
from __future__ import annotations

from decimal import Decimal
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from app.accounting import AccountingEngine, JournalLine
from app.config import AppSettings, get_settings
from app.schemas import (
    AccountCreate,
    AccountResponse,
    BalanceSheetResponse,
    BalanceSheetSection,
    CashFlowResponse,
    DashboardMetrics,
    IncomeStatementResponse,
    IncomeStatementSection,
    JournalEntryCreate,
    JournalEntryResponse,
    JournalLineModel,
)

_settings = get_settings()

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>__APP_NAME__</title>
<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\" />
<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin />
<link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap\" rel=\"stylesheet\" />
<style>
:root {
  color-scheme: light;
  font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #0f172a;
}
body {
  margin: 0;
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 45%, #111827 100%);
  color: #e2e8f0;
}
main {
  padding: 3rem 1.5rem 4rem;
  max-width: 1200px;
  margin: 0 auto;
}
header.hero {
  display: grid;
  gap: 1rem;
  margin-bottom: 2.5rem;
}
header.hero h1 {
  font-size: clamp(2.5rem, 4vw, 3.5rem);
  margin: 0;
  font-weight: 700;
}
header.hero p {
  margin: 0;
  font-size: 1.05rem;
  color: rgba(226, 232, 240, 0.75);
}
.dashboard-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}
.card {
  background: rgba(15, 23, 42, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 1rem;
  padding: 1.5rem;
  box-shadow: 0 20px 45px rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(16px);
}
.card h2 {
  margin: 0;
  font-size: 0.9rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(148, 163, 184, 0.8);
}
.card strong {
  display: block;
  margin-top: 0.5rem;
  font-size: 1.75rem;
  font-weight: 600;
  color: #f8fafc;
}
.card small {
  color: rgba(148, 163, 184, 0.75);
}
.flex-row {
  display: grid;
  gap: 1rem;
  margin-top: 2rem;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
}
.section {
  background: rgba(15, 23, 42, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 1rem;
  padding: 1.5rem;
  box-shadow: 0 12px 35px rgba(15, 23, 42, 0.35);
}
.section h3 {
  margin: 0 0 1rem;
  font-size: 1.1rem;
  font-weight: 600;
  color: #f8fafc;
}
.table {
  width: 100%;
  border-collapse: collapse;
}
.table th,
.table td {
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  padding: 0.75rem 0.5rem;
  text-align: left;
}
.table th {
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(148, 163, 184, 0.7);
}
.table tbody tr:last-child td {
  border-bottom: none;
}
.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.3rem 0.75rem;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.15);
  color: #93c5fd;
  font-size: 0.75rem;
  font-weight: 500;
  gap: 0.35rem;
}
.tag {
  padding: 0.25rem 0.5rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.2);
  color: rgba(226, 232, 240, 0.85);
  font-size: 0.7rem;
}
footer {
  margin-top: 3rem;
  color: rgba(148, 163, 184, 0.6);
  font-size: 0.8rem;
}
button.primary {
  border: none;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: white;
  padding: 0.65rem 1.25rem;
  border-radius: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.2s ease;
}
button.primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 25px rgba(37, 99, 235, 0.35);
}
form.entry-form {
  display: grid;
  gap: 0.75rem;
  margin-top: 1.25rem;
}
form.entry-form label {
  display: grid;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: rgba(226, 232, 240, 0.8);
}
form.entry-form input,
form.entry-form select,
form.entry-form textarea {
  background: rgba(15, 23, 42, 0.8);
  color: #f8fafc;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.65rem;
  padding: 0.6rem 0.75rem;
  font-size: 0.9rem;
}
form.entry-form textarea {
  min-height: 5rem;
  resize: vertical;
}
.line-items {
  display: grid;
  gap: 0.75rem;
}
.line-item {
  display: grid;
  gap: 0.5rem;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
}
.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}
.empty-state {
  text-align: center;
  padding: 3rem 1.5rem;
  color: rgba(148, 163, 184, 0.7);
}
</style>
</head>
<body>
<main>
  <header class=\"hero\">
    <div class=\"badge\">AI-assisted close <span>⚡</span></div>
    <h1>__APP_NAME__</h1>
    <p>Live operating metrics, automated reconciliations, and statement generation built for modern finance teams.</p>
    <div>
      <button class=\"primary\" id=\"new-entry\">Capture journal entry</button>
    </div>
  </header>
  <section class=\"dashboard-grid\" id=\"metrics\"></section>
  <section class=\"flex-row\">
    <div class=\"section\">
      <h3>Balance Sheet Snapshot</h3>
      <table class=\"table\" id=\"balance-sheet\"></table>
    </div>
    <div class=\"section\">
      <h3>Income Statement</h3>
      <table class=\"table\" id=\"income-statement\"></table>
    </div>
  </section>
  <section class=\"section\" style=\"margin-top:2rem;\">
    <div style=\"display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap;\">
      <h3>Recent Journal Entries</h3>
      <span class=\"badge\" id=\"cash-flow\"></span>
    </div>
    <div id=\"journal\"></div>
  </section>
  <section class=\"section\" style=\"margin-top:2rem;\" id=\"form-section\" hidden>
    <h3>Quick Journal Capture</h3>
    <form class=\"entry-form\" id=\"entry-form\">
      <label>Entry date
        <input type=\"date\" name=\"entry_date\" required />
      </label>
      <label>Description
        <input type=\"text\" name=\"description\" placeholder=\"e.g. SaaS subscription revenue\" required />
      </label>
      <label>Reference
        <input type=\"text\" name=\"reference\" placeholder=\"Optional reference\" />
      </label>
      <div class=\"line-items\" id=\"line-items\"></div>
      <button type=\"button\" class=\"primary\" id=\"add-line\">Add line</button>
      <label>Tags
        <input type=\"text\" name=\"tags\" placeholder=\"Comma separated (operating, investing, financing)\" />
      </label>
      <button type=\"submit\" class=\"primary\">Post entry</button>
    </form>
  </section>
  <footer>
    Crafted for controller workflows. Auto-balances entries, surfaces operational cash, and keeps a realtime snapshot of the financial position.
  </footer>
</main>
<script>
const metricsContainer = document.getElementById('metrics');
const balanceSheetTable = document.getElementById('balance-sheet');
const incomeTable = document.getElementById('income-statement');
const journalContainer = document.getElementById('journal');
const cashFlowBadge = document.getElementById('cash-flow');
const formSection = document.getElementById('form-section');
const entryForm = document.getElementById('entry-form');
const addLineBtn = document.getElementById('add-line');
const lineItemsContainer = document.getElementById('line-items');
const newEntryBtn = document.getElementById('new-entry');

function formatCurrency(value) {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency: '__CURRENCY__' }).format(parseFloat(value));
}

function createMetricCard(label, value, deltaText) {
  const card = document.createElement('div');
  card.className = 'card';
  const title = document.createElement('h2');
  title.textContent = label;
  card.appendChild(title);
  const strong = document.createElement('strong');
  strong.textContent = value;
  card.appendChild(strong);
  if (deltaText) {
    const small = document.createElement('small');
    small.textContent = deltaText;
    card.appendChild(small);
  }
  return card;
}

function renderMetrics(data) {
  metricsContainer.innerHTML = '';
  metricsContainer.appendChild(createMetricCard('Cash', formatCurrency(data.cash)));
  metricsContainer.appendChild(createMetricCard('Net income (YTD)', formatCurrency(data.net_income)));
  metricsContainer.appendChild(createMetricCard('Receivables', formatCurrency(data.total_receivables)));
  metricsContainer.appendChild(createMetricCard('Payables', formatCurrency(data.total_payables)));
}

function renderBalanceSheet(sheet) {
  balanceSheetTable.innerHTML = '';
  const header = document.createElement('thead');
  header.innerHTML = '<tr><th>Section</th><th>Account</th><th>Amount</th></tr>';
  balanceSheetTable.appendChild(header);
  const body = document.createElement('tbody');
  ['assets', 'liabilities', 'equity'].forEach(section => {
    const data = sheet[section];
    const accounts = Object.entries(data.accounts);
    if (!accounts.length) {
      const row = document.createElement('tr');
      row.innerHTML = '<td>' + section + '</td><td colspan="2">—</td>';
      body.appendChild(row);
    } else {
      accounts.forEach(([name, amount], index) => {
        const row = document.createElement('tr');
        row.innerHTML = '<td>' + (index === 0 ? section : '') + '</td>' +
          '<td>' + name + '</td>' +
          '<td>' + formatCurrency(amount) + '</td>';
        body.appendChild(row);
      });
    }
    const totalRow = document.createElement('tr');
    totalRow.innerHTML = '<td></td>' +
      '<td style="font-weight:600;">Total ' + section + '</td>' +
      '<td style="font-weight:600;">' + formatCurrency(data.total) + '</td>';
    body.appendChild(totalRow);
  });
  balanceSheetTable.appendChild(body);
}

function renderIncomeStatement(statement) {
  incomeTable.innerHTML = '';
  const header = document.createElement('thead');
  header.innerHTML = '<tr><th>Type</th><th>Account</th><th>Amount</th></tr>';
  incomeTable.appendChild(header);
  const body = document.createElement('tbody');
  ['income', 'expenses'].forEach(section => {
    const data = statement[section];
    const accounts = Object.entries(data.accounts);
    if (!accounts.length) {
      const row = document.createElement('tr');
      row.innerHTML = '<td>' + section + '</td><td colspan="2">—</td>';
      body.appendChild(row);
    } else {
      accounts.forEach(([name, amount], index) => {
        const row = document.createElement('tr');
        row.innerHTML = '<td>' + (index === 0 ? section : '') + '</td>' +
          '<td>' + name + '</td>' +
          '<td>' + formatCurrency(amount) + '</td>';
        body.appendChild(row);
      });
    }
    const totalRow = document.createElement('tr');
    totalRow.innerHTML = '<td></td>' +
      '<td style="font-weight:600;">Total ' + section + '</td>' +
      '<td style="font-weight:600;">' + formatCurrency(data.total) + '</td>';
    body.appendChild(totalRow);
  });
  const netRow = document.createElement('tr');
  netRow.innerHTML = '<td></td>' +
    '<td style="font-weight:700;">Net income</td>' +
    '<td style="font-weight:700;">' + formatCurrency(statement.net_income) + '</td>';
  body.appendChild(netRow);
  incomeTable.appendChild(body);
}

function renderJournal(entries) {
  journalContainer.innerHTML = '';
  if (!entries.length) {
    journalContainer.innerHTML = '<div class="empty-state">No journal entries posted yet.</div>';
    return;
  }
  entries.forEach(entry => {
    const card = document.createElement('div');
    card.className = 'card';
    card.style.marginBottom = '1rem';
    const tags = entry.tags.map(tag => '<span class="tag">' + tag + '</span>').join('');
    card.innerHTML = '<h2 style="margin-bottom:0.5rem;">' + entry.description + '</h2>' +
      '<div style="display:flex;flex-wrap:wrap;gap:0.75rem;align-items:center;margin-bottom:0.75rem;color:rgba(148,163,184,0.75);">' +
      '<span>' + new Date(entry.entry_date).toLocaleDateString() + '</span>' +
      (entry.reference ? '<span class="tag">Ref: ' + entry.reference + '</span>' : '') +
      tags +
      '</div>';
    const table = document.createElement('table');
    table.className = 'table';
    const header = document.createElement('thead');
    header.innerHTML = '<tr><th>Account</th><th>Direction</th><th>Amount</th></tr>';
    table.appendChild(header);
    const body = document.createElement('tbody');
    entry.lines.forEach(line => {
      const row = document.createElement('tr');
      row.innerHTML = '<td>' + line.account_id + '</td>' +
        '<td style="text-transform:capitalize;">' + line.direction + '</td>' +
        '<td>' + formatCurrency(line.amount) + '</td>';
      body.appendChild(row);
    });
    table.appendChild(body);
    card.appendChild(table);
    journalContainer.appendChild(card);
  });
}

function renderCashFlow(summary) {
  cashFlowBadge.textContent = 'Cash Δ ' + formatCurrency(summary.net_change) +
    ' | Ops ' + formatCurrency(summary.operating) +
    ' | Inv ' + formatCurrency(summary.investing) +
    ' | Fin ' + formatCurrency(summary.financing);
}

async function refresh() {
  const [metricsRes, sheetRes, incomeRes, journalRes, cashFlowRes] = await Promise.all([
    fetch('/api/dashboard'),
    fetch('/api/reports/balance-sheet'),
    fetch('/api/reports/income-statement'),
    fetch('/api/journal'),
    fetch('/api/reports/cash-flow'),
  ]);
  const [metrics, sheet, income, journalEntries, cashFlow] = await Promise.all([
    metricsRes.json(),
    sheetRes.json(),
    incomeRes.json(),
    journalRes.json(),
    cashFlowRes.json(),
  ]);
  renderMetrics(metrics);
  renderBalanceSheet(sheet);
  renderIncomeStatement(income);
  renderJournal(journalEntries);
  renderCashFlow(cashFlow);
}

function addLineItem() {
  const wrapper = document.createElement('div');
  wrapper.className = 'line-item';
  wrapper.innerHTML = '<label>Account ID<input name="account_id" required /></label>' +
    '<label>Direction<select name="direction"><option value="debit">Debit</option><option value="credit">Credit</option></select></label>' +
    '<label>Amount<input type="number" step="0.01" name="amount" required /></label>' +
    '<label>Memo<input name="memo" placeholder="Optional" /></label>';
  lineItemsContainer.appendChild(wrapper);
}

addLineBtn.addEventListener('click', () => {
  addLineItem();
});

entryForm.addEventListener('submit', async event => {
  event.preventDefault();
  const formData = new FormData(entryForm);
  const lines = Array.from(lineItemsContainer.querySelectorAll('.line-item')).map(row => ({
    account_id: row.querySelector('input[name="account_id"]').value,
    direction: row.querySelector('select[name="direction"]').value,
    amount: row.querySelector('input[name="amount"]').value,
    memo: row.querySelector('input[name="memo"]').value || null,
  }));
  const payload = {
    entry_date: formData.get('entry_date'),
    description: formData.get('description'),
    reference: formData.get('reference') || null,
    tags: (formData.get('tags') || '').split(',').map(tag => tag.trim()).filter(Boolean),
    lines,
  };
  const response = await fetch('/api/journal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const message = await response.json().catch(() => ({ detail: 'Failed to post entry' }));
    alert(message.detail || 'Failed to post entry');
    return;
  }
  entryForm.reset();
  lineItemsContainer.innerHTML = '';
  addLineItem();
  refresh();
});

newEntryBtn.addEventListener('click', () => {
  formSection.hidden = !formSection.hidden;
  if (!formSection.hidden && !lineItemsContainer.children.length) {
    addLineItem();
  }
});

addLineItem();
refresh();
</script>
</body>
</html>"""

app = FastAPI(title=_settings.app_name, version="0.1.0")


def get_engine(settings: AppSettings = Depends(get_settings)) -> AccountingEngine:
    engine = getattr(app.state, "engine", None)
    if engine is None:
        engine = AccountingEngine(
            default_currency=settings.default_currency,
            fiscal_year_start_month=settings.fiscal_year_start_month,
            seed_demo_data=settings.seed_demo_data,
        )
        app.state.engine = engine
    return engine


@app.get("/api/accounts", response_model=List[AccountResponse])
def list_accounts(engine: AccountingEngine = Depends(get_engine)) -> List[AccountResponse]:
    return [AccountResponse(**account.__dict__) for account in engine.list_accounts()]


@app.post("/api/accounts", response_model=AccountResponse, status_code=201)
def create_account(
    payload: AccountCreate,
    engine: AccountingEngine = Depends(get_engine),
) -> AccountResponse:
    try:
        account = engine.add_account(
            account_id=payload.id,
            name=payload.name,
            type=payload.type,
            currency=payload.currency,
            subtype=payload.subtype,
            description=payload.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AccountResponse(**account.__dict__)


@app.get("/api/journal", response_model=List[JournalEntryResponse])
def list_journal_entries(
    engine: AccountingEngine = Depends(get_engine),
    settings: AppSettings = Depends(get_settings),
) -> List[JournalEntryResponse]:
    entries = engine.list_entries()
    if len(entries) > settings.max_entries_returned:
        entries = entries[-settings.max_entries_returned :]
    return [
        JournalEntryResponse(
            id=entry.id,
            description=entry.description,
            entry_date=entry.entry_date,
            lines=[
                JournalLineModel(
                    account_id=line.account_id,
                    direction=line.direction,
                    amount=line.amount,
                    memo=line.memo,
                )
                for line in entry.lines
            ],
            reference=entry.reference,
            tags=entry.tags,
            created_at=entry.created_at,
        )
        for entry in entries
    ]


@app.post("/api/journal", response_model=JournalEntryResponse, status_code=201)
def create_journal_entry(
    payload: JournalEntryCreate,
    engine: AccountingEngine = Depends(get_engine),
) -> JournalEntryResponse:
    try:
        entry = engine.record_entry(
            description=payload.description,
            entry_date=payload.entry_date,
            lines=[
                JournalLine(
                    account_id=line.account_id,
                    direction=line.direction,
                    amount=line.amount,
                    memo=line.memo,
                )
                for line in payload.lines
            ],
            reference=payload.reference,
            tags=payload.tags,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JournalEntryResponse(
        id=entry.id,
        description=entry.description,
        entry_date=entry.entry_date,
        lines=[
            JournalLineModel(
                account_id=line.account_id,
                direction=line.direction,
                amount=line.amount,
                memo=line.memo,
            )
            for line in entry.lines
        ],
        reference=entry.reference,
        tags=entry.tags,
        created_at=entry.created_at,
    )


@app.get("/api/dashboard", response_model=DashboardMetrics)
def dashboard(engine: AccountingEngine = Depends(get_engine)) -> DashboardMetrics:
    metrics = engine.dashboard_metrics()
    return DashboardMetrics(**{key: _quantize_decimal(value) for key, value in metrics.items()})


@app.get("/api/reports/balance-sheet", response_model=BalanceSheetResponse)
def balance_sheet(engine: AccountingEngine = Depends(get_engine)) -> BalanceSheetResponse:
    sheet = engine.balance_sheet()
    return BalanceSheetResponse(
        assets=BalanceSheetSection(
            accounts={k: _quantize_decimal(v) for k, v in sheet["assets"].items()},
            total=_quantize_decimal(sheet["total_assets"]),
        ),
        liabilities=BalanceSheetSection(
            accounts={k: _quantize_decimal(v) for k, v in sheet["liabilities"].items()},
            total=_quantize_decimal(sheet["total_liabilities"]),
        ),
        equity=BalanceSheetSection(
            accounts={k: _quantize_decimal(v) for k, v in sheet["equity"].items()},
            total=_quantize_decimal(sheet["total_equity"]),
        ),
    )


@app.get("/api/reports/income-statement", response_model=IncomeStatementResponse)
def income_statement(engine: AccountingEngine = Depends(get_engine)) -> IncomeStatementResponse:
    statement = engine.income_statement()
    return IncomeStatementResponse(
        income=IncomeStatementSection(
            accounts={k: _quantize_decimal(v) for k, v in statement["income"].items()},
            total=_quantize_decimal(statement["total_income"]),
        ),
        expenses=IncomeStatementSection(
            accounts={k: _quantize_decimal(v) for k, v in statement["expenses"].items()},
            total=_quantize_decimal(statement["total_expenses"]),
        ),
        net_income=_quantize_decimal(statement["net_income"]),
    )


@app.get("/api/reports/cash-flow", response_model=CashFlowResponse)
def cash_flow(engine: AccountingEngine = Depends(get_engine)) -> CashFlowResponse:
    summary = engine.cash_flow_summary()
    return CashFlowResponse(**{key: _quantize_decimal(value) for key, value in summary.items()})


@app.get("/", response_class=HTMLResponse)
async def index(settings: AppSettings = Depends(get_settings)) -> str:
    return (
        HTML_TEMPLATE
        .replace("__APP_NAME__", settings.app_name)
        .replace("__CURRENCY__", settings.default_currency)
    )


def _quantize_decimal(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


__all__ = ["app"]
