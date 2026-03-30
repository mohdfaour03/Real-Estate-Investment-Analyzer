"""Tests for the embedder — requires mocking the OpenAI API call."""
import pytest
import sys, os
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from embedder import embed_texts
from config import EMBEDDING_DIM


class TestEmbedTexts:
    """Validates embedding function with mocked OpenAI API."""

    @patch("embedder.client")
    def test_returns_list_of_vectors(self, mock_client):
        """Should return a list of embedding vectors."""
        # Mock the OpenAI embeddings response
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * EMBEDDING_DIM
        mock_response = MagicMock()
        mock_response.data = [mock_embedding]
        mock_client.embeddings.create.return_value = mock_response

        result = embed_texts(["Dubai Marina apartments"])
        assert isinstance(result, list)
        assert len(result) == 1
        assert len(result[0]) == EMBEDDING_DIM

    @patch("embedder.client")
    def test_multiple_texts(self, mock_client):
        """Should return one vector per input text."""
        mock_embeddings = []
        for _ in range(3):
            emb = MagicMock()
            emb.embedding = [0.5] * EMBEDDING_DIM
            mock_embeddings.append(emb)
        mock_response = MagicMock()
        mock_response.data = mock_embeddings
        mock_client.embeddings.create.return_value = mock_response

        result = embed_texts(["text1", "text2", "text3"])
        assert len(result) == 3

    @patch("embedder.client")
    def test_calls_api_with_correct_model(self, mock_client):
        """Should call the embeddings API with the configured model."""
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * EMBEDDING_DIM
        mock_response = MagicMock()
        mock_response.data = [mock_embedding]
        mock_client.embeddings.create.return_value = mock_response

        embed_texts(["test"])
        mock_client.embeddings.create.assert_called_once()
        call_kwargs = mock_client.embeddings.create.call_args
        assert "text-embedding-3-small" in str(call_kwargs)
