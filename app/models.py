"""Data models for parsed medical bills."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional


@dataclass
class Adjustment:
    """Represents a financial adjustment applied to a line item."""

    type: str
    amount: float


@dataclass
class PatientResponsibility:
    """Breakdown of patient responsibility components."""

    deductible: float = 0.0
    copay: float = 0.0
    coinsurance: float = 0.0
    non_covered: float = 0.0
    other: Dict[str, float] = field(default_factory=dict)

    def total(self) -> float:
        """Return the total patient responsibility for the line."""
        base = self.deductible + self.copay + self.coinsurance + self.non_covered
        return base + sum(self.other.values())


@dataclass
class LineItem:
    """Represents a parsed line item from a medical bill."""

    line_no: int
    date_of_service: Optional[date]
    code_type: str
    code: Optional[str]
    modifiers: List[str]
    description_raw: str
    units: Optional[float]
    charge: float
    allowed: Optional[float]
    adjustments: List[Adjustment]
    payer_paid: Optional[float]
    patient_resp: PatientResponsibility
    patient_owes_line: float
    explanation: str
    confidence: float
    warnings: List[str] = field(default_factory=list)


@dataclass
class Header:
    """Document header metadata."""

    provider: Optional[str]
    payer: Optional[str]
    patient: Optional[str]
    account_number: Optional[str]
    dos_start: Optional[date]
    dos_end: Optional[date]


@dataclass
class Totals:
    """Aggregated totals for the document."""

    total_charge: float = 0.0
    total_allowed: float = 0.0
    total_adjustments: float = 0.0
    payer_paid: float = 0.0
    patient_owes: float = 0.0
    reconciles: bool = False


@dataclass
class MathCheck:
    """Result of a math validation check."""

    name: str
    passed: bool
    details: str


@dataclass
class ParsedDocument:
    """Complete parsed representation of a medical bill."""

    doc_type: str
    header: Header
    lines: List[LineItem]
    totals: Totals
    math_checks: List[MathCheck]
    notes: List[str] = field(default_factory=list)


__all__ = [
    "Adjustment",
    "PatientResponsibility",
    "LineItem",
    "Header",
    "Totals",
    "MathCheck",
    "ParsedDocument",
]
