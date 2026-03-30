from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag_pipeline.config import CHUNK_SIZE, CHUNK_OVERLAP


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    """
    Initializes and returns a RecursiveCharacterTextSplitter with specified chunk size and overlap.

    Returns:
        RecursiveCharacterTextSplitter: An instance of the text splitter configured with the defined chunk size and overlap.
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, 
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],
        )



