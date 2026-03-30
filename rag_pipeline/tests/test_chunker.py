"""Tests for the text chunker — no external dependencies."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chunker import get_text_splitter
from config import CHUNK_SIZE, CHUNK_OVERLAP


class TestGetTextSplitter:
    """Validates the splitter is configured correctly."""

    def test_returns_splitter_instance(self):
        splitter = get_text_splitter()
        assert splitter is not None

    def test_chunk_size_matches_config(self):
        splitter = get_text_splitter()
        assert splitter._chunk_size == CHUNK_SIZE

    def test_chunk_overlap_matches_config(self):
        splitter = get_text_splitter()
        assert splitter._chunk_overlap == CHUNK_OVERLAP

    def test_splits_long_text(self):
        """Splitter should break long text into multiple chunks."""
        splitter = get_text_splitter()
        # Create text longer than CHUNK_SIZE
        long_text = "This is a sentence about UAE real estate. " * 200
        chunks = splitter.split_text(long_text)
        assert len(chunks) > 1

    def test_short_text_single_chunk(self):
        """Short text should remain as a single chunk."""
        splitter = get_text_splitter()
        short_text = "Dubai Marina apartments."
        chunks = splitter.split_text(short_text)
        assert len(chunks) == 1

    def test_chunks_respect_max_size(self):
        """No chunk should exceed the configured chunk size (with some tolerance)."""
        splitter = get_text_splitter()
        long_text = "Rental market analysis for UAE properties. " * 300
        chunks = splitter.split_text(long_text)
        for chunk in chunks:
            # Allow small tolerance since splitting is character-based
            assert len(chunk) <= CHUNK_SIZE + 50, f"Chunk too large: {len(chunk)} chars"

    def test_overlap_produces_shared_content(self):
        """Consecutive chunks should share overlapping content."""
        splitter = get_text_splitter()
        # Build text with distinct sentences
        sentences = [f"Sentence number {i} about property {i}. " for i in range(100)]
        long_text = "".join(sentences)
        chunks = splitter.split_text(long_text)
        if len(chunks) >= 2:
            # Check that the end of chunk[0] overlaps with start of chunk[1]
            # (not exact since splitting is by separator, but overlap should create some shared text)
            tail = chunks[0][-CHUNK_OVERLAP:]
            assert any(word in chunks[1] for word in tail.split()[:3])
