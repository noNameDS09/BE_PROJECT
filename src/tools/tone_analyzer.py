"""
Loughran-McDonald Financial Tone & Tone Shift Analyzer.

Evaluates managerial sentiment, tone polarity, uncertainty, and tone shifts
across reporting periods (QoQ, YoY, or Presentation vs Q&A) using the
domain-standard Loughran-McDonald (LM) financial lexicon.

RESEARCH DATA LIMITATION:
SEC Company Facts ('companyfacts.zip') contains structured numerical XBRL data.
It does NOT contain spoken earnings call transcripts, audio, or full 10-K Item 1A
narrative sections. Tone is either:
1. Evaluated directly on user-supplied textual excerpts (transcripts, MD&A, management remarks).
2. Derived via a quantitative fundamental momentum proxy from SEC reported facts.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from src.data.company_registry import CompanyMetadata, CompanyRegistry, get_registry
from src.retrieval.financial_query import (
    FinancialFactResult,
    FinancialQueryEngine,
    get_default_query_engine,
)

logger = logging.getLogger(__name__)

TONE_LIMITATION_NOTICE = (
    "RESEARCH DATA LIMITATION: SEC Company Facts contains structured numerical XBRL facts. "
    "Spoken earnings call transcripts and Item 1A narrative text are not present in the numeric dataset. "
    "When qualitative text is provided, the engine computes Loughran-McDonald financial tone scores and "
    "tone shifts. In the absence of text, tone is modeled via quantitative fundamental momentum proxies."
)

# -----------------------------------------------------------------------------
# Curated Loughran-McDonald Financial Sentiment Lexicon
# -----------------------------------------------------------------------------

LM_POSITIVE: Set[str] = {
    "achieve", "achieved", "achieves", "achieving", "advantage", "advantageous",
    "attain", "attained", "attaining", "attractive", "beautiful", "benefit",
    "benefited", "benefiting", "benefits", "beneficial", "boom", "booming",
    "breakthrough", "breakthroughs", "collaborate", "collaborated", "collaboration",
    "collaborative", "confidence", "confident", "delighted", "effective",
    "effectively", "effectiveness", "efficiencies", "efficiency", "efficient",
    "efficiently", "empower", "empowered", "enable", "enabled", "enabling",
    "enhance", "enhanced", "enhancement", "enhancements", "enhancing", "excel",
    "excelled", "excelling", "exceptional", "exceptionally", "excited", "exciting",
    "expansion", "favourable", "favorable", "favorably", "gain", "gained",
    "gaining", "gains", "generate", "generated", "generating", "good", "great",
    "greater", "greatest", "greatly", "growth", "grow", "growing", "grew",
    "innovate", "innovated", "innovating", "innovation", "innovations", "innovative",
    "lucrative", "momentum", "optimize", "optimized", "optimizing", "optimization",
    "outperform", "outperformed", "outperforming", "outperforms", "outstanding",
    "pleased", "pleasing", "plentiful", "positive", "positively", "positives",
    "profit", "profitable", "profitability", "profitably", "profits", "profited",
    "prosper", "prospered", "prospering", "prosperity", "prosperous", "rebound",
    "rebounded", "rebounding", "recover", "recovered", "recovering", "recovery",
    "resilience", "resilient", "resolve", "resolved", "resolving", "reward",
    "rewarded", "rewarding", "rewards", "robust", "robustly", "solid", "solidly",
    "spectacular", "stability", "stable", "strengthen", "strengthened", "strengthening",
    "strong", "stronger", "strongest", "strongly", "succeed", "succeeded",
    "succeeding", "succeeds", "success", "successes", "successful", "successfully",
    "superior", "surpass", "surpassed", "surpassing", "tremendous", "unprecedented",
    "upbeat", "upgrade", "upgraded", "upgrades", "valuable", "value", "win", "winning", "won"
}

LM_NEGATIVE: Set[str] = {
    "abandon", "abandoned", "abandoning", "adverse", "adversely", "adversity",
    "bad", "badly", "bankrupt", "bankruptcy", "bankruptcies", "burden", "burdens",
    "burdensome", "cancel", "canceled", "cancelling", "cancellation", "cancellations",
    "cease", "ceased", "ceasing", "claim", "claims", "close", "closed", "closing",
    "closure", "closures", "collapse", "collapsed", "collapsing", "complaint",
    "complaints", "conflict", "conflicts", "costly", "curtail", "curtailed",
    "curtailment", "cut", "cuts", "cutting", "damage", "damaged", "damages",
    "damaging", "decline", "declined", "declines", "declining", "default",
    "defaulted", "defaulting", "defaults", "defect", "defective", "defects",
    "deficiency", "deficient", "deficit", "deficits", "depress", "depressed",
    "depression", "destroy", "destroyed", "destroying", "destruction", "destructive",
    "deteriorate", "deteriorated", "deteriorates", "deteriorating", "deterioration",
    "detriment", "detrimental", "difficult", "difficulties", "difficulty",
    "disappoint", "disappointed", "disappointing", "disappointment", "disappointments",
    "dispute", "disputed", "disputes", "disrupt", "disrupted", "disrupting",
    "disruption", "disruptions", "distress", "distressed", "down", "downturn",
    "downturns", "drop", "dropped", "dropping", "drops", "erosion", "erode",
    "eroded", "eroding", "fail", "failed", "failing", "fails", "failure", "failures",
    "fall", "fallen", "falling", "falls", "flaw", "flaws", "foreclose", "foreclosed",
    "foreclosure", "forfeit", "forfeited", "fraud", "fraudulent", "grievance",
    "harm", "harmed", "harming", "harmful", "hinder", "hindered", "hindering",
    "hindrance", "hurt", "hurting", "hurts", "impair", "impaired", "impairing",
    "impairment", "impairments", "impairs", "inability", "inadequate", "incapable",
    "ineffective", "ineffectiveness", "inferior", "injure", "injured", "injuring",
    "injuries", "injury", "insolvency", "insolvent", "layoff", "layoffs", "leak",
    "loss", "losses", "lost", "negative", "negatively", "neglect", "neglected",
    "obsolete", "obstacle", "obstacles", "penalty", "penalties", "plummet",
    "plummeted", "plummeting", "poor", "poorly", "recall", "recalled", "recalls",
    "recession", "recessionary", "recessions", "restructure", "restructured",
    "restructuring", "restructurings", "revoke", "revoked", "revoking", "risk",
    "risks", "risky", "scandal", "severe", "severely", "severity", "shortage",
    "shortages", "shortfall", "shortfalls", "shrink", "shrinking", "shrunk",
    "slump", "slumped", "slumping", "stagnant", "stagnation", "strain", "strained",
    "straining", "strains", "stress", "stressed", "strike", "strikes", "sue",
    "sued", "sues", "suing", "terminate", "terminated", "terminates", "terminating",
    "termination", "terminations", "threat", "threaten", "threatened", "threatening",
    "threats", "trouble", "troubled", "turbulence", "turmoil", "unable", "unfavourable",
    "unfavorable", "unfavorably", "unfortunate", "unlikely", "unprofitable",
    "volatile", "volatility", "vulnerable", "vulnerability", "vulnerabilities",
    "warning", "warnings", "weak", "weaken", "weakened", "weakening", "weakens",
    "weakness", "weaknesses", "worse", "worsen", "worsened", "worsening", "worsens",
    "worst", "writedown", "writedowns", "writeoff", "writeoffs"
}

LM_UNCERTAINTY: Set[str] = {
    "anticipate", "anticipated", "anticipates", "anticipating", "anticipation",
    "approximate", "approximately", "assume", "assumed", "assumes", "assuming",
    "assumption", "assumptions", "believe", "believed", "believes", "believing",
    "cautious", "cautiously", "conceivable", "contingency", "contingencies",
    "contingent", "depend", "depended", "depending", "depends", "doubt", "doubtful",
    "estimate", "estimated", "estimates", "estimating", "estimation", "expect",
    "expected", "expectancy", "expectation", "expectations", "expecting", "expects",
    "fluctuate", "fluctuated", "fluctuates", "fluctuating", "fluctuation",
    "fluctuations", "forecast", "forecasted", "forecasting", "forecasts", "gamble",
    "indefinite", "indeterminate", "maybe", "might", "pending", "perhaps",
    "possibility", "possibilities", "possible", "possibly", "predict", "predicted",
    "predicting", "prediction", "predictions", "predicts", "preliminary", "presume",
    "presumed", "presumes", "presuming", "presumption", "probable", "probably",
    "probability", "probabilities", "project", "projected", "projecting",
    "projection", "projections", "projects", "recalculate", "rough", "roughly",
    "seldom", "somewhat", "speculate", "speculated", "speculating", "speculation",
    "speculative", "suggest", "suggested", "suggesting", "suggests", "tentative",
    "tentatively", "uncertain", "uncertainties", "uncertainty", "unclear",
    "unconfirmed", "undecided", "undefined", "unforeseen", "unknown", "unpredictable",
    "unpredictability", "unsure", "variable", "variables", "variation", "variations",
    "vary", "varying", "varies"
}

LM_LITIGIOUS: Set[str] = {
    "allege", "alleged", "alleges", "alleging", "allegation", "allegations",
    "amend", "amended", "amendment", "amendments", "antitrust", "appeal",
    "appealed", "appealing", "appeals", "arbitrate", "arbitration", "arbitrator",
    "attorney", "attorneys", "breach", "breached", "breaches", "breaching",
    "claim", "claimed", "claiming", "claims", "claimant", "claimants",
    "compensation", "complaint", "complaints", "court", "courts", "covenant",
    "covenants", "damage", "damages", "defendant", "defendants", "dismiss",
    "dismissal", "dismissed", "dispute", "disputes", "disputed", "injunction",
    "injunctions", "judge", "judges", "judgment", "judgments", "judicial",
    "jurisdiction", "lawsuit", "lawsuits", "legal", "legality", "legally",
    "legislation", "legislative", "liability", "liabilities", "liable",
    "litigate", "litigated", "litigating", "litigation", "litigations",
    "patent", "patents", "plaintiff", "plaintiffs", "plea", "plead",
    "proceedings", "prosecute", "prosecuted", "prosecution", "regulatory",
    "settle", "settled", "settlement", "settlements", "statute", "statutes",
    "statutory", "subpoena", "subpoenas", "sue", "sued", "suing", "suit",
    "suits", "verdict", "verdicts", "violate", "violated", "violates",
    "violating", "violation", "violations"
}

LM_CONSTRAINING: Set[str] = {
    "abide", "bound", "commit", "committed", "committing", "commitment",
    "commitments", "compel", "compelled", "compulsory", "confine", "confined",
    "confining", "constraint", "constraints", "constrain", "constrained",
    "constraining", "duty", "duties", "limit", "limited", "limiting", "limits",
    "limitation", "limitations", "mandatory", "mandate", "mandated", "mandating",
    "mandates", "necessitate", "necessitated", "necessitates", "necessitating",
    "oblige", "obliged", "obliging", "obligation", "obligations", "obligatory",
    "prescribe", "prescribed", "prescribes", "prescribing", "prescription",
    "require", "required", "requires", "requiring", "requirement", "requirements",
    "restrict", "restricted", "restricting", "restricts", "restriction",
    "restrictions", "restrictive", "restrictively", "strict", "strictly"
}


@dataclass
class ToneScore:
    """
    Detailed Loughran-McDonald sentiment scores for a textual passage.
    """
    total_words: int
    positive_count: int
    negative_count: int
    uncertainty_count: int
    litigious_count: int
    constraining_count: int
    polarity_score: float  # (Pos - Neg) / (Pos + Neg + eps) -> [-1.0, +1.0]
    subjectivity: float    # (Pos + Neg) / (TotalWords + eps)
    uncertainty_ratio: float  # Uncertainty / (TotalWords + eps)
    dominant_sentiment: str   # POSITIVE, NEGATIVE, or NEUTRAL
    top_positive_words: List[str] = field(default_factory=list)
    top_negative_words: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __repr__(self) -> str:
        return (
            f"ToneScore(dominant='{self.dominant_sentiment}', polarity={self.polarity_score:+.3f}, "
            f"pos={self.positive_count}, neg={self.negative_count}, uncertainty={self.uncertainty_count})"
        )


@dataclass
class ToneShift:
    """
    Quantified shift in tone between two financial periods or disclosure sections.
    """
    period_a_label: str
    period_b_label: str
    score_a: ToneScore
    score_b: ToneScore
    delta_polarity: float  # score_b.polarity - score_a.polarity
    delta_uncertainty: float
    shift_category: str  # STRONG_POSITIVE_SHIFT, MODERATE_POSITIVE_SHIFT, STABLE, MODERATE_NEGATIVE_SHIFT, STRONG_NEGATIVE_SHIFT
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period_a_label": self.period_a_label,
            "period_b_label": self.period_b_label,
            "score_a": self.score_a.to_dict(),
            "score_b": self.score_b.to_dict(),
            "delta_polarity": round(self.delta_polarity, 4),
            "delta_uncertainty": round(self.delta_uncertainty, 4),
            "shift_category": self.shift_category,
            "interpretation": self.interpretation,
        }


@dataclass
class QuantitativeToneProxy:
    """
    Fundamental momentum proxy derived from SEC XBRL facts when narrative text is omitted.
    """
    company: str
    cik: str
    fiscal_year: int
    prior_year: int
    revenue_growth_pct: Optional[float]
    operating_margin_delta_pts: Optional[float]
    net_income_growth_pct: Optional[float]
    proxy_score: float  # [-1.0, +1.0]
    implied_tone: str   # OPTIMISTIC / EXPANSIONARY, STABLE / MODERATE, CAUTIOUS / CONTRACTING
    source_facts: List[Dict[str, Any]] = field(default_factory=list)
    data_limitation_notice: str = TONE_LIMITATION_NOTICE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ToneAnalyzer:
    """
    Loughran-McDonald Financial Sentiment and Tone Shift Analyzer.
    """

    def __init__(
        self,
        query_engine: Optional[FinancialQueryEngine] = None,
        registry: Optional[CompanyRegistry] = None,
    ):
        self.query_engine = query_engine or get_default_query_engine()
        self.registry = registry or get_registry()

    def _tokenize(self, text: str) -> List[str]:
        """Extracts alphabetic lowercase word tokens from financial text."""
        return re.findall(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b", text.lower())

    def analyze_tone(self, text: str) -> ToneScore:
        """
        Calculates Loughran-McDonald tone metrics for a financial text string.
        """
        words = self._tokenize(text)
        total_words = len(words)
        if total_words == 0:
            return ToneScore(
                total_words=0,
                positive_count=0,
                negative_count=0,
                uncertainty_count=0,
                litigious_count=0,
                constraining_count=0,
                polarity_score=0.0,
                subjectivity=0.0,
                uncertainty_ratio=0.0,
                dominant_sentiment="NEUTRAL",
            )

        pos_words: List[str] = []
        neg_words: List[str] = []
        unc_count = 0
        lit_count = 0
        con_count = 0

        for w in words:
            if w in LM_POSITIVE:
                pos_words.append(w)
            if w in LM_NEGATIVE:
                neg_words.append(w)
            if w in LM_UNCERTAINTY:
                unc_count += 1
            if w in LM_LITIGIOUS:
                lit_count += 1
            if w in LM_CONSTRAINING:
                con_count += 1

        pos_count = len(pos_words)
        neg_count = len(neg_words)

        denom = pos_count + neg_count
        if denom > 0:
            polarity = (pos_count - neg_count) / float(denom)
        else:
            polarity = 0.0

        subjectivity = (pos_count + neg_count) / float(total_words)
        unc_ratio = unc_count / float(total_words)

        if polarity >= 0.15:
            sentiment = "POSITIVE"
        elif polarity <= -0.15:
            sentiment = "NEGATIVE"
        else:
            sentiment = "NEUTRAL"

        # Unique top frequent words for audit
        from collections import Counter
        top_pos = [w for w, _ in Counter(pos_words).most_common(5)]
        top_neg = [w for w, _ in Counter(neg_words).most_common(5)]

        return ToneScore(
            total_words=total_words,
            positive_count=pos_count,
            negative_count=neg_count,
            uncertainty_count=unc_count,
            litigious_count=lit_count,
            constraining_count=con_count,
            polarity_score=round(polarity, 4),
            subjectivity=round(subjectivity, 4),
            uncertainty_ratio=round(unc_ratio, 4),
            dominant_sentiment=sentiment,
            top_positive_words=top_pos,
            top_negative_words=top_neg,
        )

    def compare_tone_shift(
        self,
        text_a: str,
        text_b: str,
        label_a: str = "Period A",
        label_b: str = "Period B",
    ) -> ToneShift:
        """
        Quantifies tone shift delta across two distinct passages.
        """
        score_a = self.analyze_tone(text_a)
        score_b = self.analyze_tone(text_b)

        delta_pol = score_b.polarity_score - score_a.polarity_score
        delta_unc = score_b.uncertainty_ratio - score_a.uncertainty_ratio

        if delta_pol >= 0.30:
            shift_category = "STRONG_POSITIVE_SHIFT"
            interp = f"Significant improvement in managerial tone (+{delta_pol:.3f} polarity) from {label_a} to {label_b}."
        elif delta_pol >= 0.10:
            shift_category = "MODERATE_POSITIVE_SHIFT"
            interp = f"Noticeable uptick in positive sentiment (+{delta_pol:.3f} polarity) from {label_a} to {label_b}."
        elif delta_pol <= -0.30:
            shift_category = "STRONG_NEGATIVE_SHIFT"
            interp = f"Severe deterioration in tone ({delta_pol:.3f} polarity) from {label_a} to {label_b}, signaling heightened distress."
        elif delta_pol <= -0.10:
            shift_category = "MODERATE_NEGATIVE_SHIFT"
            interp = f"Cautious contraction in sentiment ({delta_pol:.3f} polarity) from {label_a} to {label_b}."
        else:
            shift_category = "STABLE"
            interp = f"Tone remained broadly stable ({delta_pol:+.3f} polarity shift) between {label_a} and {label_b}."

        if delta_unc >= 0.02:
            interp += f" Uncertainty language increased noticeably (+{delta_unc*100:.1f} pts)."
        elif delta_unc <= -0.02:
            interp += f" Uncertainty language dropped by {abs(delta_unc)*100:.1f} pts."

        return ToneShift(
            period_a_label=label_a,
            period_b_label=label_b,
            score_a=score_a,
            score_b=score_b,
            delta_polarity=round(delta_pol, 4),
            delta_uncertainty=round(delta_unc, 4),
            shift_category=shift_category,
            interpretation=interp,
        )

    def derive_quantitative_tone_proxy(
        self,
        company: str,
        fiscal_year: int,
    ) -> QuantitativeToneProxy:
        """
        Derives an objective fundamental momentum proxy when qualitative narrative text is absent.
        """
        c_clean = str(company).strip()
        c_lower = c_clean.lower()
        meta = None
        if c_lower in ("amd", "advanced micro devices"):
            try:
                meta = self.registry.get_company("0000002488")
            except Exception:
                pass
        elif c_lower in ("abbott", "abbott laboratories"):
            try:
                meta = self.registry.get_company("0000001800")
            except Exception:
                pass
        elif c_lower in ("apple", "aapl"):
            try:
                meta = self.registry.get_company("0000320193")
            except Exception:
                pass

        if not meta:
            try:
                meta = self.registry.get_company(c_clean)
            except Exception:
                matches = self.registry.search_company_by_name(c_clean, limit=1)
                meta = matches[0] if matches else None

        if not meta:
            return QuantitativeToneProxy(
                company=company,
                cik="",
                fiscal_year=fiscal_year,
                prior_year=fiscal_year - 1,
                revenue_growth_pct=None,
                operating_margin_delta_pts=None,
                net_income_growth_pct=None,
                proxy_score=0.0,
                implied_tone="NEUTRAL / DATA_UNAVAILABLE",
            )

        prior_year = fiscal_year - 1
        cik = meta.cik

        # Retrieve Revenue
        rev_curr = self.query_engine.query_financial_fact(cik, "revenue", fiscal_year, "FY")
        rev_prior = self.query_engine.query_financial_fact(cik, "revenue", prior_year, "FY")

        # Retrieve Operating Income
        opinc_curr = self.query_engine.query_financial_fact(cik, "operating income", fiscal_year, "FY")
        opinc_prior = self.query_engine.query_financial_fact(cik, "operating income", prior_year, "FY")

        # Retrieve Net Income
        ni_curr = self.query_engine.query_financial_fact(cik, "net income", fiscal_year, "FY")
        ni_prior = self.query_engine.query_financial_fact(cik, "net income", prior_year, "FY")

        source_facts = [
            f.to_dict() for f in (rev_curr, rev_prior, opinc_curr, opinc_prior, ni_curr, ni_prior)
            if f is not None and f.value is not None
        ]

        # 1. Revenue Growth
        rev_growth = None
        rev_component = 0.0
        if (rev_curr is not None and rev_curr.value is not None and
            rev_prior is not None and rev_prior.value is not None and rev_prior.value != 0):
            rev_growth = ((float(rev_curr.value) - float(rev_prior.value)) / abs(float(rev_prior.value))) * 100.0
            if rev_growth >= 10.0:
                rev_component = 0.35
            elif rev_growth >= 0.0:
                rev_component = 0.15
            elif rev_growth >= -10.0:
                rev_component = -0.15
            else:
                rev_component = -0.35

        # 2. Operating Margin Shift
        om_delta = None
        om_component = 0.0
        if (rev_curr is not None and rev_curr.value and
            opinc_curr is not None and opinc_curr.value is not None and
            rev_prior is not None and rev_prior.value and
            opinc_prior is not None and opinc_prior.value is not None):
            om_curr = (float(opinc_curr.value) / float(rev_curr.value)) * 100.0
            om_prior = (float(opinc_prior.value) / float(rev_prior.value)) * 100.0
            om_delta = om_curr - om_prior
            if om_delta >= 1.5:
                om_component = 0.35
            elif om_delta >= 0.0:
                om_component = 0.15
            elif om_delta >= -1.5:
                om_component = -0.15
            else:
                om_component = -0.35

        # 3. Net Income Growth
        ni_growth = None
        ni_component = 0.0
        if (ni_curr is not None and ni_curr.value is not None and
            ni_prior is not None and ni_prior.value is not None and ni_prior.value != 0):
            ni_growth = ((float(ni_curr.value) - float(ni_prior.value)) / abs(float(ni_prior.value))) * 100.0
            if ni_growth >= 10.0:
                ni_component = 0.30
            elif ni_growth >= 0.0:
                ni_component = 0.10
            elif ni_growth >= -10.0:
                ni_component = -0.10
            else:
                ni_component = -0.30

        total_proxy = round(rev_component + om_component + ni_component, 3)
        # Bound between -1.0 and 1.0
        total_proxy = max(-1.0, min(1.0, total_proxy))

        if total_proxy >= 0.25:
            implied_tone = "EXPANSIONARY / OPTIMISTIC"
        elif total_proxy <= -0.25:
            implied_tone = "CONTRACTING / CAUTIOUS"
        else:
            implied_tone = "BALANCED / STABLE"

        return QuantitativeToneProxy(
            company=meta.entity_name,
            cik=meta.cik,
            fiscal_year=fiscal_year,
            prior_year=prior_year,
            revenue_growth_pct=round(rev_growth, 2) if rev_growth is not None else None,
            operating_margin_delta_pts=round(om_delta, 2) if om_delta is not None else None,
            net_income_growth_pct=round(ni_growth, 2) if ni_growth is not None else None,
            proxy_score=total_proxy,
            implied_tone=implied_tone,
            source_facts=source_facts,
        )


# Global singleton
_DEFAULT_TONE_ANALYZER: Optional[ToneAnalyzer] = None


def get_default_tone_analyzer() -> ToneAnalyzer:
    global _DEFAULT_TONE_ANALYZER
    if _DEFAULT_TONE_ANALYZER is None:
        _DEFAULT_TONE_ANALYZER = ToneAnalyzer()
    return _DEFAULT_TONE_ANALYZER
