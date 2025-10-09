from datetime import date
from decimal import Decimal

import pytest

from app.accounting import AccountingEngine, JournalLine


@pytest.fixture()
def engine() -> AccountingEngine:
    return AccountingEngine(seed_demo_data=True)


def test_debits_equal_credits(engine: AccountingEngine) -> None:
    entries = engine.list_entries()
    debit_total = Decimal("0")
    credit_total = Decimal("0")
    for entry in entries:
        for line in entry.lines:
            if line.direction == "debit":
                debit_total += line.amount
            else:
                credit_total += line.amount
    assert debit_total == credit_total


def test_record_entry_requires_balance(engine: AccountingEngine) -> None:
    with pytest.raises(ValueError):
        engine.record_entry(
            description="Unbalanced entry",
            entry_date=date.today(),
            lines=[
                JournalLine(account_id="1000", direction="debit", amount=Decimal("100")),
                JournalLine(account_id="2000", direction="credit", amount=Decimal("50")),
            ],
        )


def test_income_statement_rollup(engine: AccountingEngine) -> None:
    statement = engine.income_statement()
    assert statement["total_income"] - statement["total_expenses"] == statement["net_income"]


def test_cash_flow_segments_sum(engine: AccountingEngine) -> None:
    summary = engine.cash_flow_summary()
    expected = summary["operating"] + summary["investing"] + summary["financing"]
    assert summary["net_change"] == expected


def test_create_new_account(engine: AccountingEngine) -> None:
    account = engine.add_account(account_id="6100", name="Marketing Expense", type="expense")
    assert account.id == "6100"
    assert engine.get_account("6100").name == "Marketing Expense"
