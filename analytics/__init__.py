"""Analytics engine for GARVIS — Governance-Aware Reflective Virtual Intelligence System.

The analytics engine provides PURELY OBSERVATIONAL analysis of cognition data.
It computes trends, metrics, and pressure indicators to help operators understand
system behavior. Analytics NEVER influence runtime behavior.

Modules:
    metrics: Core metrics computation (CognitionMetrics, GovernancePressureMetrics)
    trends: Time-series trend analysis (TrendAnalyzer)
    continuity: Long-term continuity analysis (ContinuityAnalyzer)
    ecosystem: Cognition ecosystem mapping (EcosystemMapper)
    overview: High-level overview generation (AnalyticsOverview)
"""

from __future__ import annotations

from analytics.continuity import ContinuityAnalyzer
from analytics.ecosystem import EcosystemMapper
from analytics.metrics import CognitionMetrics, GovernancePressureMetrics
from analytics.overview import AnalyticsOverview
from analytics.trends import TrendAnalyzer

__all__ = [
    # Core metrics
    "CognitionMetrics",
    "GovernancePressureMetrics",
    # Trend analysis
    "TrendAnalyzer",
    # Continuity analysis
    "ContinuityAnalyzer",
    # Ecosystem mapping
    "EcosystemMapper",
    # Overview generation
    "AnalyticsOverview",
]
