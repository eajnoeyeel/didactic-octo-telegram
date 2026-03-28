"""HeuristicAnalyzer — regex/rule-based GEO dimension scorer."""

import re

from loguru import logger

from description_optimizer.analyzer.base import DescriptionAnalyzer
from description_optimizer.models import AnalysisReport, DimensionScore


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a float value to [lo, hi]."""
    return max(lo, min(hi, value))


class HeuristicAnalyzer(DescriptionAnalyzer):
    """Rule-based GEO scorer using regex patterns.

    Scores six dimensions purely via heuristic rules with no external API calls,
    making it fast, deterministic, and cost-free.
    """

    # --- Clarity patterns ---
    _ACTION_VERBS: re.Pattern[str] = re.compile(
        r"\b(search(?:es)?|find(?:s)?|retriev(?:e|es)|creat(?:e|es)|updat(?:e|es)|delet(?:e|es)"
        r"|read(?:s)?|writ(?:e|es)|list(?:s)?|fetch(?:es)?|execut(?:e|es)|run(?:s)?"
        r"|send(?:s)?|get(?:s)?|post(?:s)?|quer(?:y|ies)|pars(?:e|es)|convert(?:s)?"
        r"|generat(?:e|es)|analyz(?:e|es)|monitor(?:s)?|check(?:s)?|validat(?:e|es))\b",
        re.IGNORECASE,
    )
    _WHEN_TO_USE: re.Pattern[str] = re.compile(
        r"\b(use when|use this|use for|useful for|designed for|intended for|when you need)\b",
        re.IGNORECASE,
    )
    _SCOPE_MARKERS: re.Pattern[str] = re.compile(
        r"\b(from the|in the|via the|through the|across|within|for the)\b",
        re.IGNORECASE,
    )

    # --- Disambiguation patterns ---
    _CONTRAST_PHRASES: re.Pattern[str] = re.compile(
        r"\b(unlike|not to be confused with|as opposed to|different from"
        r"|specifically for|only for|exclusively)\b",
        re.IGNORECASE,
    )
    _DOMAIN_QUALIFIERS: re.Pattern[str] = re.compile(
        r"\b(only|specifically|exclusively)\b",
        re.IGNORECASE,
    )
    _NEGATIVE_INSTRUCTIONS: re.Pattern[str] = re.compile(
        r"\b(not for|cannot|does not|will not|unable to|should not|won't|isn't|doesn't"
        r"|not suitable|not designed|limitations?:?)\b",
        re.IGNORECASE,
    )

    # --- Parameter coverage patterns ---
    _PARAM_REFS: re.Pattern[str] = re.compile(
        r"\b(parameter|param|argument|input|field|option|flag)\b",
        re.IGNORECASE,
    )
    _TYPE_REFS: re.Pattern[str] = re.compile(
        r"\b(string|int|float|bool|list|dict|array|object|required|optional|default)\b",
        re.IGNORECASE,
    )
    _INLINE_EXAMPLES: re.Pattern[str] = re.compile(
        r'`[^`]+`|"[^"]{2,}"',
    )

    # --- Boundary patterns ---
    _NEGATIVE_BOUNDARY: re.Pattern[str] = re.compile(
        r"\b(not for|cannot|does not|will not|unable to|should not|won't|isn't|doesn't"
        r"|not suitable|not designed|limitations?:?)\b",
        re.IGNORECASE,
    )
    _LIMITATION_KEYWORDS: re.Pattern[str] = re.compile(
        r"\b(limitation|caveat|restriction|constraint|warning)\b",
        re.IGNORECASE,
    )

    # --- Stats patterns ---
    _STAT_WITH_UNITS: re.Pattern[str] = re.compile(
        r"\d[\d,]*\.?\d*\s*(%|ms|seconds?|minutes?|results?|per\s+\w+|uptime|latency|\+)",
        re.IGNORECASE,
    )
    _STANDALONE_NUMBERS: re.Pattern[str] = re.compile(
        r"\b\d{2,}[\d,]*\b",
    )

    # --- Precision patterns ---
    _TECHNICAL_TERMS: re.Pattern[str] = re.compile(
        r"\b(SQL|PostgreSQL|MySQL|MongoDB|Redis|REST|GraphQL|gRPC|HTTP|JSON|XML|YAML|CSV"
        r"|API|SDK|OAuth|JWT|WebSocket|TCP|UDP|S3|AWS|GCP|Azure|Docker|Kubernetes"
        r"|Git|GitHub|Slack|Notion|MCP|SSE|stdio|protocol|schema|specification)\b",
        re.IGNORECASE,
    )
    _PROTOCOL_FORMAT: re.Pattern[str] = re.compile(
        r"\b(wire protocol|file format|encoding|specification|standard|extension"
        r"|plugin|middleware|connector)\b",
        re.IGNORECASE,
    )

    async def analyze(self, tool_id: str, description: str | None) -> AnalysisReport:
        """Analyze tool description using heuristic rules and return a GEO AnalysisReport."""
        safe_desc = description if description else ""
        logger.debug(f"HeuristicAnalyzer analyzing tool_id={tool_id!r}, desc_len={len(safe_desc)}")

        dimension_scores = [
            self._score_clarity(safe_desc),
            self._score_disambiguation(safe_desc),
            self._score_parameter_coverage(safe_desc),
            self._score_boundary(safe_desc),
            self._score_stats(safe_desc),
            self._score_precision(safe_desc),
        ]

        return AnalysisReport(
            tool_id=tool_id,
            original_description=safe_desc,
            dimension_scores=dimension_scores,
        )

    # ------------------------------------------------------------------
    # Private scoring methods
    # ------------------------------------------------------------------

    def _score_clarity(self, desc: str) -> DimensionScore:
        score = 0.0
        reasons: list[str] = []

        # Length baseline
        if len(desc) >= 50:
            score += 0.2
            reasons.append("length>=50")
        elif len(desc) >= 20:
            score += 0.1
            reasons.append("length>=20")

        # Action verbs — each +0.15, cap 0.3
        verb_matches = self._ACTION_VERBS.findall(desc)
        verb_contribution = _clamp(len(verb_matches) * 0.15, hi=0.3)
        score += verb_contribution
        if verb_matches:
            reasons.append(f"action_verbs={len(verb_matches)}")

        # When-to-use phrases — +0.25
        if self._WHEN_TO_USE.search(desc):
            score += 0.25
            reasons.append("when_to_use")

        # Scope markers — each +0.1, cap 0.25
        scope_matches = self._SCOPE_MARKERS.findall(desc)
        scope_contribution = _clamp(len(scope_matches) * 0.1, hi=0.25)
        score += scope_contribution
        if scope_matches:
            reasons.append(f"scope_markers={len(scope_matches)}")

        final = _clamp(score)
        return DimensionScore(
            dimension="clarity",
            score=final,
            explanation=f"Clarity score {final:.2f}: {', '.join(reasons) or 'no signals'}",
        )

    def _score_disambiguation(self, desc: str) -> DimensionScore:
        score = 0.0
        reasons: list[str] = []

        # Contrast phrases — each +0.3, cap 0.5
        contrast_matches = self._CONTRAST_PHRASES.findall(desc)
        contrast_contribution = _clamp(len(contrast_matches) * 0.3, hi=0.5)
        score += contrast_contribution
        if contrast_matches:
            reasons.append(f"contrast_phrases={len(contrast_matches)}")

        # Domain qualifiers — each +0.2, cap 0.3
        qualifier_matches = self._DOMAIN_QUALIFIERS.findall(desc)
        qualifier_contribution = _clamp(len(qualifier_matches) * 0.2, hi=0.3)
        score += qualifier_contribution
        if qualifier_matches:
            reasons.append(f"domain_qualifiers={len(qualifier_matches)}")

        # Negative instructions present — +0.2
        if self._NEGATIVE_INSTRUCTIONS.search(desc):
            score += 0.2
            reasons.append("negative_instructions")

        final = _clamp(score)
        return DimensionScore(
            dimension="disambiguation",
            score=final,
            explanation=f"Disambiguation score {final:.2f}: {', '.join(reasons) or 'no signals'}",
        )

    def _score_parameter_coverage(self, desc: str) -> DimensionScore:
        score = 0.0
        reasons: list[str] = []

        # Param references — each +0.15, cap 0.3
        param_matches = self._PARAM_REFS.findall(desc)
        param_contribution = _clamp(len(param_matches) * 0.15, hi=0.3)
        score += param_contribution
        if param_matches:
            reasons.append(f"param_refs={len(param_matches)}")

        # Type references — each +0.15, cap 0.4
        type_matches = self._TYPE_REFS.findall(desc)
        type_contribution = _clamp(len(type_matches) * 0.15, hi=0.4)
        score += type_contribution
        if type_matches:
            reasons.append(f"type_refs={len(type_matches)}")

        # Inline examples — each +0.1, cap 0.3
        example_matches = self._INLINE_EXAMPLES.findall(desc)
        example_contribution = _clamp(len(example_matches) * 0.1, hi=0.3)
        score += example_contribution
        if example_matches:
            reasons.append(f"inline_examples={len(example_matches)}")

        final = _clamp(score)
        return DimensionScore(
            dimension="parameter_coverage",
            score=final,
            explanation=(
                f"Parameter coverage score {final:.2f}: {', '.join(reasons) or 'no signals'}"
            ),
        )

    def _score_boundary(self, desc: str) -> DimensionScore:
        score = 0.0
        reasons: list[str] = []

        # Negative instructions — each +0.3, cap 0.7
        neg_matches = self._NEGATIVE_BOUNDARY.findall(desc)
        neg_contribution = _clamp(len(neg_matches) * 0.3, hi=0.7)
        score += neg_contribution
        if neg_matches:
            reasons.append(f"negative_instructions={len(neg_matches)}")

        # Limitation keywords — +0.3
        if self._LIMITATION_KEYWORDS.search(desc):
            score += 0.3
            reasons.append("limitation_keywords")

        final = _clamp(score)
        return DimensionScore(
            dimension="boundary",
            score=final,
            explanation=f"Boundary score {final:.2f}: {', '.join(reasons) or 'no signals'}",
        )

    def _score_stats(self, desc: str) -> DimensionScore:
        score = 0.0
        reasons: list[str] = []

        # Numeric stats with units — each +0.25, cap 0.8
        stat_matches = self._STAT_WITH_UNITS.findall(desc)
        if stat_matches:
            stat_contribution = _clamp(len(stat_matches) * 0.25, hi=0.8)
            score += stat_contribution
            reasons.append(f"stat_with_units={len(stat_matches)}")
        else:
            # Standalone large numbers (2+ digits) — each +0.1, cap 0.2 (only if no stat_matches)
            num_matches = self._STANDALONE_NUMBERS.findall(desc)
            num_contribution = _clamp(len(num_matches) * 0.1, hi=0.2)
            score += num_contribution
            if num_matches:
                reasons.append(f"standalone_numbers={len(num_matches)}")

        final = _clamp(score)
        return DimensionScore(
            dimension="stats",
            score=final,
            explanation=f"Stats score {final:.2f}: {', '.join(reasons) or 'no signals'}",
        )

    def _score_precision(self, desc: str) -> DimensionScore:
        score = 0.0
        reasons: list[str] = []

        # Technical terms — each +0.15, cap 0.7
        tech_matches = self._TECHNICAL_TERMS.findall(desc)
        tech_contribution = _clamp(len(tech_matches) * 0.15, hi=0.7)
        score += tech_contribution
        if tech_matches:
            reasons.append(f"technical_terms={len(tech_matches)}")

        # Protocol/format words — each +0.15, cap 0.3
        proto_matches = self._PROTOCOL_FORMAT.findall(desc)
        proto_contribution = _clamp(len(proto_matches) * 0.15, hi=0.3)
        score += proto_contribution
        if proto_matches:
            reasons.append(f"protocol_format={len(proto_matches)}")

        final = _clamp(score)
        return DimensionScore(
            dimension="precision",
            score=final,
            explanation=f"Precision score {final:.2f}: {', '.join(reasons) or 'no signals'}",
        )
