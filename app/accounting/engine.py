"""Accounting engine providing double-entry bookkeeping utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Iterable, List, Literal, Optional
from uuid import uuid4

AccountType = Literal["asset", "liability", "equity", "income", "expense"]
BalanceSide = Literal["debit", "credit"]


@dataclass
class Account:
    """Represents a ledger account."""

    id: str
    name: str
    type: AccountType
    currency: str = "USD"
    subtype: Optional[str] = None
    description: Optional[str] = None


@dataclass
class JournalLine:
    """A single debit or credit line in a journal entry."""

    account_id: str
    direction: BalanceSide
    amount: Decimal
    memo: Optional[str] = None


@dataclass
class JournalEntry:
    """A journal entry grouping multiple lines that balance to zero."""

    id: str
    description: str
    entry_date: date
    lines: List[JournalLine]
    reference: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


class AccountingEngine:
    """In-memory accounting engine used by the application API."""

    def __init__(
        self,
        default_currency: str = "USD",
        fiscal_year_start_month: int = 1,
        seed_demo_data: bool = False,
    ) -> None:
        self._default_currency = default_currency
        self._fiscal_year_start_month = fiscal_year_start_month
        self._accounts: Dict[str, Account] = {}
        self._entries: List[JournalEntry] = []
        if seed_demo_data:
            self._seed_demo_ledger()

    # ------------------------------------------------------------------
    # Account management
    # ------------------------------------------------------------------
    def list_accounts(self) -> List[Account]:
        return list(self._accounts.values())

    def get_account(self, account_id: str) -> Account:
        try:
            return self._accounts[account_id]
        except KeyError as exc:
            raise KeyError(f"Unknown account '{account_id}'") from exc

    def add_account(
        self,
        *,
        account_id: str,
        name: str,
        type: AccountType,
        currency: Optional[str] = None,
        subtype: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Account:
        if account_id in self._accounts:
            raise ValueError(f"Account '{account_id}' already exists")
        currency = currency or self._default_currency
        account = Account(
            id=account_id,
            name=name,
            type=type,
            currency=currency,
            subtype=subtype,
            description=description,
        )
        self._accounts[account_id] = account
        return account

    # ------------------------------------------------------------------
    # Journal management
    # ------------------------------------------------------------------
    def list_entries(self) -> List[JournalEntry]:
        return list(self._entries)

    def record_entry(
        self,
        *,
        description: str,
        entry_date: date,
        lines: Iterable[JournalLine],
        reference: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> JournalEntry:
        normalized_lines = [self._normalize_line(line) for line in lines]
        if len(normalized_lines) < 2:
            raise ValueError("Journal entry requires at least two lines")

        debit_total = sum(
            line.amount for line in normalized_lines if line.direction == "debit"
        )
        credit_total = sum(
            line.amount for line in normalized_lines if line.direction == "credit"
        )
        if debit_total != credit_total:
            raise ValueError(
                "Journal entry debits and credits must balance: "
                f"debits={debit_total} credits={credit_total}"
            )

        entry = JournalEntry(
            id=str(uuid4()),
            description=description,
            entry_date=entry_date,
            lines=normalized_lines,
            reference=reference,
            tags=list(tags or []),
        )
        self._entries.append(entry)
        return entry

    def _normalize_line(self, line: JournalLine) -> JournalLine:
        if line.account_id not in self._accounts:
            raise KeyError(f"Account '{line.account_id}' does not exist")
        if line.direction not in {"debit", "credit"}:
            raise ValueError("Line direction must be either 'debit' or 'credit'")
        amount = self._quantize(line.amount)
        if amount <= Decimal("0"):
            raise ValueError("Line amount must be positive")
        return JournalLine(
            account_id=line.account_id,
            direction=line.direction,
            amount=amount,
            memo=line.memo,
        )

    # ------------------------------------------------------------------
    # Reporting helpers
    # ------------------------------------------------------------------
    def trial_balance(self, *, as_of: Optional[date] = None) -> Dict[str, Decimal]:
        balances: Dict[str, Decimal] = {}
        for account in self._accounts.values():
            balances[account.id] = self.account_balance(account.id, as_of=as_of)
        return balances

    def account_balance(self, account_id: str, *, as_of: Optional[date] = None) -> Decimal:
        account = self.get_account(account_id)
        debit_total = Decimal("0")
        credit_total = Decimal("0")
        for entry in self._entries:
            if as_of and entry.entry_date > as_of:
                continue
            for line in entry.lines:
                if line.account_id != account_id:
                    continue
                if line.direction == "debit":
                    debit_total += line.amount
                else:
                    credit_total += line.amount
        return self._net_balance(account, debit_total, credit_total)

    def balance_sheet(self, *, as_of: Optional[date] = None) -> Dict[str, Dict[str, Decimal]]:
        assets: Dict[str, Decimal] = {}
        liabilities: Dict[str, Decimal] = {}
        equity: Dict[str, Decimal] = {}
        for account in self._accounts.values():
            balance = self.account_balance(account.id, as_of=as_of)
            if account.type == "asset":
                assets[account.name] = balance
            elif account.type == "liability":
                liabilities[account.name] = balance
            elif account.type == "equity":
                equity[account.name] = balance
        return {
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "total_assets": sum(assets.values(), Decimal("0")),
            "total_liabilities": sum(liabilities.values(), Decimal("0")),
            "total_equity": sum(equity.values(), Decimal("0")),
        }

    def income_statement(
        self, *, start: Optional[date] = None, end: Optional[date] = None
    ) -> Dict[str, Dict[str, Decimal]]:
        income: Dict[str, Decimal] = {}
        expenses: Dict[str, Decimal] = {}
        for account in self._accounts.values():
            if account.type not in {"income", "expense"}:
                continue
            net = self._net_activity(account, start=start, end=end)
            if account.type == "income":
                income[account.name] = net
            else:
                expenses[account.name] = net
        revenue_total = sum(income.values(), Decimal("0"))
        expense_total = sum(expenses.values(), Decimal("0"))
        net_income = revenue_total - expense_total
        return {
            "income": income,
            "expenses": expenses,
            "total_income": revenue_total,
            "total_expenses": expense_total,
            "net_income": net_income,
        }

    def cash_flow_summary(
        self, *, start: Optional[date] = None, end: Optional[date] = None
    ) -> Dict[str, Decimal]:
        segments = {"operating": Decimal("0"), "investing": Decimal("0"), "financing": Decimal("0")}
        cash_accounts = {
            account.id
            for account in self._accounts.values()
            if account.type == "asset" and (account.subtype or "").lower() == "cash"
        }
        for entry in self._entries:
            if start and entry.entry_date < start:
                continue
            if end and entry.entry_date > end:
                continue
            tag = next((t for t in entry.tags if t in segments), "operating")
            delta = Decimal("0")
            for line in entry.lines:
                if line.account_id not in cash_accounts:
                    continue
                if line.direction == "debit":
                    delta += line.amount
                else:
                    delta -= line.amount
            segments[tag] += delta
        segments["net_change"] = sum(segments.values(), Decimal("0"))
        return segments

    def dashboard_metrics(self, *, as_of: Optional[date] = None) -> Dict[str, Decimal]:
        as_of = as_of or date.today()
        balance_sheet = self.balance_sheet(as_of=as_of)
        income = self.income_statement(
            start=date(as_of.year, self._fiscal_year_start_month, 1), end=as_of
        )
        cash_accounts = [
            account.id
            for account in self._accounts.values()
            if account.type == "asset" and (account.subtype or "").lower() == "cash"
        ]
        cash_total = sum(
            (self.account_balance(account_id, as_of=as_of) for account_id in cash_accounts),
            Decimal("0"),
        )
        return {
            "cash": cash_total,
            "net_income": income["net_income"],
            "total_receivables": sum(
                (
                    balance
                    for name, balance in balance_sheet["assets"].items()
                    if "receivable" in name.lower()
                ),
                Decimal("0"),
            ),
            "total_payables": sum(
                (
                    balance
                    for name, balance in balance_sheet["liabilities"].items()
                    if "payable" in name.lower()
                ),
                Decimal("0"),
            ),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normal_balance(account: Account) -> BalanceSide:
        return "debit" if account.type in {"asset", "expense"} else "credit"

    def _net_balance(
        self, account: Account, debit_total: Decimal, credit_total: Decimal
    ) -> Decimal:
        if self._normal_balance(account) == "debit":
            return debit_total - credit_total
        return credit_total - debit_total

    def _net_activity(
        self, account: Account, *, start: Optional[date], end: Optional[date]
    ) -> Decimal:
        debit_total = Decimal("0")
        credit_total = Decimal("0")
        for entry in self._entries:
            if start and entry.entry_date < start:
                continue
            if end and entry.entry_date > end:
                continue
            for line in entry.lines:
                if line.account_id != account.id:
                    continue
                if line.direction == "debit":
                    debit_total += line.amount
                else:
                    credit_total += line.amount
        if self._normal_balance(account) == "debit":
            return credit_total - debit_total
        return debit_total - credit_total

    @staticmethod
    def _quantize(value: Decimal | float | int | str) -> Decimal:
        if isinstance(value, Decimal):
            amount = value
        else:
            amount = Decimal(str(value))
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _seed_demo_ledger(self) -> None:
        """Populate the ledger with sample accounts and entries for the demo UI."""

        self.add_account(account_id="1000", name="Operating Cash", type="asset", subtype="cash")
        self.add_account(account_id="1100", name="Accounts Receivable", type="asset")
        self.add_account(account_id="1200", name="Deferred Revenue", type="liability")
        self.add_account(account_id="2000", name="Accounts Payable", type="liability")
        self.add_account(account_id="3000", name="Common Stock", type="equity")
        self.add_account(account_id="3100", name="Retained Earnings", type="equity")
        self.add_account(account_id="4000", name="Subscription Revenue", type="income")
        self.add_account(account_id="5000", name="Research Expense", type="expense")
        self.add_account(account_id="5100", name="Operations Expense", type="expense")

        today = date.today()
        opening_balance_date = date(today.year, self._fiscal_year_start_month, 1)

        self.record_entry(
            description="Seed funding",
            entry_date=opening_balance_date,
            lines=[
                JournalLine(account_id="1000", direction="debit", amount=Decimal("250000")),
                JournalLine(account_id="3000", direction="credit", amount=Decimal("200000")),
                JournalLine(account_id="3100", direction="credit", amount=Decimal("50000")),
            ],
            tags=["financing"],
        )

        self.record_entry(
            description="Enterprise subscription invoice",
            entry_date=opening_balance_date,
            lines=[
                JournalLine(account_id="1100", direction="debit", amount=Decimal("42000")),
                JournalLine(account_id="4000", direction="credit", amount=Decimal("42000")),
            ],
            tags=["operating"],
        )

        self.record_entry(
            description="Monthly payroll",
            entry_date=opening_balance_date,
            lines=[
                JournalLine(account_id="5000", direction="debit", amount=Decimal("30000")),
                JournalLine(account_id="5100", direction="debit", amount=Decimal("12000")),
                JournalLine(account_id="1000", direction="credit", amount=Decimal("42000")),
            ],
            tags=["operating"],
        )

        self.record_entry(
            description="Customer payment",
            entry_date=opening_balance_date,
            lines=[
                JournalLine(account_id="1000", direction="debit", amount=Decimal("42000")),
                JournalLine(account_id="1100", direction="credit", amount=Decimal("42000")),
            ],
            tags=["operating"],
        )

        self.record_entry(
            description="Deferred revenue recognition",
            entry_date=opening_balance_date,
            lines=[
                JournalLine(account_id="1200", direction="debit", amount=Decimal("7000")),
                JournalLine(account_id="4000", direction="credit", amount=Decimal("7000")),
            ],
            tags=["operating"],
        )

        self.record_entry(
            description="Equipment purchase",
            entry_date=opening_balance_date,
            lines=[
                JournalLine(account_id="1000", direction="credit", amount=Decimal("15000")),
                JournalLine(account_id="5100", direction="debit", amount=Decimal("15000")),
            ],
            tags=["investing"],
        )
