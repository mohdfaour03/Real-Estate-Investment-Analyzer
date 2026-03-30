from openai import OpenAI
from typing import List
from rag_pipeline.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, EMBEDDING_MODEL, EMBEDDING_DIM

client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Embeds a list of texts using the OpenRouter API.

    Args:
        texts (List[str]): A list of strings to be embedded.

    Returns:
        List[List[float]]: A list of embeddings, where each embedding is a list of floats.
    """
    response = client.embeddings.create(
        input=texts,
        model=EMBEDDING_MODEL,
    )
    return [item.embedding for item in response.data]