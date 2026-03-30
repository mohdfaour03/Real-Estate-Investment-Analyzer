"""Tests for supervisor helper functions — pure functions, no LLM calls."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langchain_core.messages import HumanMessage, AIMessage
from agents.supervisor import _messages_to_chat_history, _extract_final_content


class TestMessagesToChatHistory:
    """Tests conversion from LangChain messages to OpenAI-format dicts."""

    def test_human_message(self):
        messages = [HumanMessage(content="Hello")]
        result = _messages_to_chat_history(messages)
        assert result == [{"role": "user", "content": "Hello"}]

    def test_ai_message(self):
        messages = [AIMessage(content="Hi there")]
        result = _messages_to_chat_history(messages)
        assert result == [{"role": "assistant", "content": "Hi there"}]

    def test_mixed_messages(self):
        messages = [
            HumanMessage(content="Find apartments"),
            AIMessage(content="Here are some options..."),
            HumanMessage(content="Show me cheaper ones"),
        ]
        result = _messages_to_chat_history(messages)
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[2]["role"] == "user"

    def test_empty_messages(self):
        result = _messages_to_chat_history([])
        assert result == []


class TestExtractFinalContent:
    """Tests extraction of the last AI message content."""

    def test_extracts_last_ai_message(self):
        messages = [
            HumanMessage(content="query"),
            AIMessage(content="First response"),
            AIMessage(content="Final response"),
        ]
        result = _extract_final_content(messages)
        assert result == "Final response"

    def test_single_ai_message(self):
        messages = [AIMessage(content="Only response")]
        result = _extract_final_content(messages)
        assert result == "Only response"

    def test_no_ai_message_returns_default(self):
        """When there are no AI messages, should return a default message."""
        messages = [HumanMessage(content="query")]
        result = _extract_final_content(messages)
        assert isinstance(result, str)
        assert len(result) > 0  # should be a fallback, not empty
