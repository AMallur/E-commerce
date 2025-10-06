"""Language generation helpers for line item explanations."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from app.config import AppSettings
from app.models import Adjustment, PatientResponsibility

LOGGER = logging.getLogger(__name__)


@dataclass
class ExplanationContext:
    """Normalized values passed to the explainer engine."""

    line_no: int
    description: str
    code: Optional[str]
    code_type: str
    date_of_service: Optional[str]
    charge: float
    allowed: Optional[float]
    payer_paid: Optional[float]
    adjustments: Sequence[Adjustment]
    patient_resp: PatientResponsibility
    patient_total: float
    units: Optional[float]
    provider: Optional[str]
    payer: Optional[str]


class BaseExplainer:
    """Base class for all explanation engines."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def explain(self, context: ExplanationContext) -> Tuple[str, float, List[str]]:
        raise NotImplementedError


def _load_code_metadata(settings: AppSettings) -> Dict[str, Dict[str, str]]:
    """Load configurable metadata for known procedure codes."""

    path: Path = settings.code_dictionary_path
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        LOGGER.debug("Code dictionary file missing at %s", path)
        return {}
    except json.JSONDecodeError as exc:  # pragma: no cover - config error path
        LOGGER.warning("Failed to decode code dictionary %s: %s", path, exc)
        return {}

    metadata: Dict[str, Dict[str, str]] = {}
    for code, value in raw.items():
        if isinstance(value, dict):
            description = value.get("description")
            necessity = value.get("necessity")
        else:
            description = str(value)
            necessity = None
        metadata[code] = {
            "description": description or "",
            "necessity": necessity or "",
        }
    return metadata


class DeterministicExplainer(BaseExplainer):
    """Rule-based explanation engine that never invents numbers."""

    def __init__(self, settings: AppSettings) -> None:
        super().__init__(settings)
        self._metadata = _load_code_metadata(settings)

    def explain(self, context: ExplanationContext) -> Tuple[str, float, List[str]]:
        description = context.description
        metadata = self._metadata.get(context.code or "", {})
        friendly = metadata.get("description") or description
        necessity = metadata.get("necessity") or self._fallback_necessity(context)

        adjustment_text = ""
        if context.adjustments:
            total_adj = sum(adj.amount for adj in context.adjustments)
            sign = "reduction" if total_adj < 0 else "increase"
            adjustment_text = (
                f" Contractual {sign} of {self.settings.output_currency}{abs(total_adj):,.2f} "
                "was applied."
            )

        allowed_text = (
            f" Allowed amount is {self.settings.output_currency}{context.allowed:,.2f}."
            if context.allowed is not None
            else ""
        )
        payer_text = (
            f" Insurance paid {self.settings.output_currency}{context.payer_paid:,.2f}."
            if context.payer_paid is not None
            else ""
        )

        components = _describe_patient_components(context.patient_resp, self.settings.output_currency)
        component_sentence = (
            f" Patient responsibility comes from {components} for a total of {self.settings.output_currency}{context.patient_total:,.2f}."
            if components
            else f" Patient owes {self.settings.output_currency}{context.patient_total:,.2f}."
        )

        unit_text = ""
        if context.units and context.units > 1:
            unit_text = f" ({context.units:g} units recorded.)"

        dos_text = f" on {context.date_of_service}" if context.date_of_service else ""

        narrative = (
            f"Line {context.line_no}{dos_text}: {friendly}. {necessity} "
            f"Provider billed {self.settings.output_currency}{context.charge:,.2f}.{unit_text}"
            f"{adjustment_text}{allowed_text}{payer_text}{component_sentence}"
        ).strip()

        confidence = 0.75
        if not components:
            confidence -= 0.1
        if context.allowed is None:
            confidence -= 0.05
        warnings: List[str] = []
        return narrative, max(confidence, 0.1), warnings

    def _fallback_necessity(self, context: ExplanationContext) -> str:
        base = "This service was performed"
        if context.code:
            base += f" to address the clinical need associated with code {context.code}"
        else:
            base += " to support the patient's treatment plan"
        if context.provider:
            base += f" as ordered by {context.provider}"
        return base + "."


class LLMExplainer(BaseExplainer):
    """Wrapper around optional LLM providers for richer narratives."""

    def __init__(self, settings: AppSettings, fallback: BaseExplainer) -> None:
        super().__init__(settings)
        self._fallback = fallback
        self._client = self._build_client()

    def _build_client(self):  # pragma: no cover - optional dependency path
        provider = self.settings.llm_provider
        if not provider:
            return None
        try:
            if provider.lower() == "openai":
                import openai

                openai.api_key = self.settings.llm_api_key
                return openai
        except Exception as exc:
            LOGGER.warning("Failed to initialize LLM provider %s: %s", provider, exc)
        return None

    def explain(self, context: ExplanationContext) -> Tuple[str, float, List[str]]:
        if not self._client:
            return self._fallback.explain(context)
        prompt = self._build_prompt(context)
        try:  # pragma: no cover - network dependent
            response = self._client.ChatCompletion.create(
                model=self.settings.llm_model or "gpt-3.5-turbo",
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a medical billing expert. Explain each service clearly "
                            "and justify why the patient might receive this bill. Use only "
                            "the numbers provided."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            content = response["choices"][0]["message"]["content"].strip()
            return content, 0.9, []
        except Exception as exc:
            LOGGER.warning("LLM explanation failed: %s", exc)
            return self._fallback.explain(context)

    def _build_prompt(self, context: ExplanationContext) -> str:
        adjustments = [
            f"{adj.type} {self.settings.output_currency}{adj.amount:,.2f}"
            for adj in context.adjustments
        ]
        components = _describe_patient_components(context.patient_resp, self.settings.output_currency)
        return (
            "Explain the following medical billing line item in two sentences. "
            "Clarify what the service is, why it was medically necessary, and how the "
            "math results in the patient responsibility. "
            f"Line number: {context.line_no}. Description: {context.description}. "
            f"Code: {context.code or 'unknown'} ({context.code_type}). Date: {context.date_of_service or 'n/a'}. "
            f"Charge: {self.settings.output_currency}{context.charge:,.2f}. "
            f"Allowed: {self.settings.output_currency}{context.allowed:,.2f} if available. "
            f"Insurance paid: {self.settings.output_currency}{context.payer_paid:,.2f} if available. "
            f"Adjustments: {', '.join(adjustments) if adjustments else 'none'}. "
            f"Patient components: {components or 'not provided'}, total {self.settings.output_currency}{context.patient_total:,.2f}."
        )


def _describe_patient_components(resp: PatientResponsibility, currency: str) -> str:
    parts: List[str] = []
    if resp.deductible:
        parts.append(f"deductible {currency}{resp.deductible:,.2f}")
    if resp.copay:
        parts.append(f"copay {currency}{resp.copay:,.2f}")
    if resp.coinsurance:
        parts.append(f"coinsurance {currency}{resp.coinsurance:,.2f}")
    if resp.non_covered:
        parts.append(f"non-covered {currency}{resp.non_covered:,.2f}")
    for name, value in resp.other.items():
        parts.append(f"{name} {currency}{value:,.2f}")
    return ", ".join(parts)


def build_explainer(settings: AppSettings) -> BaseExplainer:
    """Return a configured explanation engine based on settings."""

    deterministic = DeterministicExplainer(settings)
    if settings.enable_llm:
        return LLMExplainer(settings, deterministic)
    return deterministic


__all__ = [
    "BaseExplainer",
    "DeterministicExplainer",
    "LLMExplainer",
    "ExplanationContext",
    "build_explainer",
]
