"""Conftest for Agent System A tests.
Patches heavy external clients (Qdrant, OpenAI) before any agent modules get imported,
preventing connection errors during test collection."""
import sys, os
import pandas as pd
from unittest.mock import MagicMock

# Ensure agent_system_a is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Pre-patch Qdrant and OpenAI before rag_tool.py gets imported by the agent chain.
# When pytest collects test_supervisor_helpers.py, it imports supervisor.py →
# property_analyst.py → rag_tool.py, which tries to connect to Qdrant at module level.
import qdrant_client
_original_qdrant_init = qdrant_client.QdrantClient.__init__

def _mock_qdrant_init(self, *args, **kwargs):
    """Replace QdrantClient init with a no-op to avoid connection attempts."""
    self._client = MagicMock()

qdrant_client.QdrantClient.__init__ = _mock_qdrant_init
qdrant_client.QdrantClient.query_points = MagicMock(return_value=MagicMock(points=[]))
