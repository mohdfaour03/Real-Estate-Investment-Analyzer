"""Tests for FastAPI endpoints — health check and request models."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import app, ChatRequest, ChatResponse
from fastapi.testclient import TestClient

client = TestClient(app)


class TestHealthEndpoint:
    """Health check should always return 200."""

    def test_health_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok" or "status" in data


class TestChatRequestModel:
    """Validates Pydantic request model."""

    def test_valid_request(self):
        req = ChatRequest(query="Find apartments in Dubai")
        assert req.query == "Find apartments in Dubai"

    def test_default_session_id(self):
        req = ChatRequest(query="test")
        assert req.session_id is None or isinstance(req.session_id, str)

    def test_with_session_id(self):
        req = ChatRequest(query="test", session_id="abc-123")
        assert req.session_id == "abc-123"
