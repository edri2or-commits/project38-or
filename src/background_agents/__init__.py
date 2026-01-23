"""Background Agents - Autonomous LLM-powered agents for system optimization.

This module implements 3 autonomous agents that run on schedule and use
SmartLLMClient for cost-optimized model selection:

1. CostOptAgent - Analyzes Railway costs and generates savings recommendations
2. HealthSynthAgent - Synthesizes system health metrics into readable summaries
3. LearnInsightAgent - Generates strategic insights from action history

ADR-013 Phase 3: Background Autonomous Jobs
"""

from src.background_agents.cost_opt_agent import CostOptAgent
from src.background_agents.health_synth_agent import HealthSynthAgent
from src.background_agents.learn_insight_agent import LearnInsightAgent
from src.background_agents.metrics import AgentMetrics, MetricsCollector

__all__ = [
    "CostOptAgent",
    "HealthSynthAgent",
    "LearnInsightAgent",
    "AgentMetrics",
    "MetricsCollector",
]
