"""
The new assistant (step 3c, the walking skeleton): tools, a registry, a piece ledger, agents read from
mappings/agents.yaml, a model interface and the loop that ties them together. See docs/learn/step-3c.md.
"""

from .tools import Registry
from .tools_wardrobe import LIST_WARDROBE


def default_registry():
    """Every tool the assistant has. Step 3d adds the others here."""
    registry = Registry()
    registry.register(LIST_WARDROBE)
    return registry
