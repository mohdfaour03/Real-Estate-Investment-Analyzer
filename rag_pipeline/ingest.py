import os
import fitz  # PyMuPDF
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from uuid import uuid4

from rag_pipeline.config import (
    QUADRANT_HOST, QUADRANT_PORT, COLLECTION_NAME, DOCS_DIR, EMBEDDING_DIM
)
from rag_pipeline.chunker import get_text_splitter
from rag_pipeline.embedder import embed_texts
from shared.logging_config import get_logger

logger = get_logger("rag_pipeline.ingest")


# --- Initialize ---
qdrant = QdrantClient(host=QUADRANT_HOST, port=QUADRANT_PORT)
splitter = get_text_splitter()


def create_collection():
    """Create Qdrant collection if it doesn't exist."""
    collections = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION_NAME not in collections:
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        logger.info(f"Created collection: {COLLECTION_NAME}")
    else:
        logger.info(f"Collection '{COLLECTION_NAME}' already exists")


def ingest_pdfs():
    """Read PDFs, extract text, chunk, embed, store in Qdrant."""
    logger.info("Starting PDF ingestion...")

    all_chunks = []
    all_metas = []

    for filename in os.listdir(DOCS_DIR):
        if not filename.endswith(".pdf"):
            continue

        filepath = os.path.join(DOCS_DIR, filename)
        doc = fitz.open(filepath)

        # Extract text per page so we can track page numbers in metadata
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text()
            if not page_text.strip():
                continue

            page_chunks = splitter.split_text(page_text)
            for chunk in page_chunks:
                all_chunks.append(chunk)
                all_metas.append({"source": filename, "page": page_num})

        doc.close()
        logger.info(f"  {filename}: extracted (running total: {len(all_chunks)} chunks)")

    _embed_and_store(all_chunks, all_metas)
    logger.info(f"PDF ingestion complete: {len(all_chunks)} total chunks stored")


def _embed_and_store(chunks: list, metadatas: list, batch_size: int = 64):
    """Embed chunks in batches and upsert to Qdrant."""
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i : i + batch_size]
        batch_metas = metadatas[i : i + batch_size]
        embeddings = embed_texts(batch_chunks)

        points = [
            PointStruct(
                id=str(uuid4()),
                vector=embedding,
                payload={"text": chunk, **meta},
            )
            for chunk, embedding, meta in zip(batch_chunks, embeddings, batch_metas)
        ]

        qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
        logger.debug(f"  Batch {i // batch_size + 1}: {len(batch_chunks)} vectors upserted")

    logger.info(f"  Stored {len(chunks)} vectors in Qdrant")


if __name__ == "__main__":
    create_collection()
    ingest_pdfs()
    logger.info("Ingestion complete!")
