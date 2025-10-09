"""Pydantic schemas for the accounting application API."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, validator

AccountType = Literal["asset", "liability", "equity", "income", "expense"]
BalanceSide = Literal["debit", "credit"]


class AccountBase(BaseModel):
    id: str = Field(..., description="Unique account identifier")
    name: str
    type: AccountType
    currency: str = Field(default="USD", max_length=3)
    subtype: Optional[str] = None
    description: Optional[str] = None


class AccountCreate(AccountBase):
    pass


class AccountResponse(AccountBase):
    class Config:
        orm_mode = True


class JournalLineModel(BaseModel):
    account_id: str
    direction: BalanceSide
    amount: Decimal = Field(..., gt=0)
    memo: Optional[str] = None

    @validator("amount", pre=True)
    def _normalize_amount(cls, value: Decimal | float | int | str) -> Decimal:
        return Decimal(str(value))


class JournalEntryCreate(BaseModel):
    description: str
    entry_date: date
    lines: List[JournalLineModel]
    reference: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class JournalEntryResponse(BaseModel):
    id: str
    description: str
    entry_date: date
    lines: List[JournalLineModel]
    reference: Optional[str] = None
    tags: List[str]
    created_at: datetime


class DashboardMetrics(BaseModel):
    cash: Decimal
    net_income: Decimal
    total_receivables: Decimal
    total_payables: Decimal


class BalanceSheetSection(BaseModel):
    total: Decimal
    accounts: Dict[str, Decimal]


class BalanceSheetResponse(BaseModel):
    assets: BalanceSheetSection
    liabilities: BalanceSheetSection
    equity: BalanceSheetSection


class IncomeStatementSection(BaseModel):
    accounts: Dict[str, Decimal]
    total: Decimal


class IncomeStatementResponse(BaseModel):
    income: IncomeStatementSection
    expenses: IncomeStatementSection
    net_income: Decimal


class CashFlowResponse(BaseModel):
    operating: Decimal
    investing: Decimal
    financing: Decimal
    net_change: Decimal
