import os 
from dotenv import load_dotenv

load_dotenv()

# Qdrant configuration — accepts both QDRANT_* (correct) and QUADRANT_* (legacy) env vars
QDRANT_HOST = os.getenv("QDRANT_HOST", os.getenv("QUADRANT_HOST", "localhost"))

QDRANT_PORT = int(os.getenv("QDRANT_PORT", os.getenv("QUADRANT_PORT", 6333)))

# Backwards-compatible aliases (some modules may still import the old names)
QUADRANT_HOST = QDRANT_HOST
QUADRANT_PORT = QDRANT_PORT

COLLECTION_NAME = "uae_properties"

#- Embedding Configuration -
EMBEDDING_MODEL = "text-embedding-3-small"

EMBEDDING_DIM = 1536

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

#- Chunking Configuration -
# RecursiveCharacterTextSplitter uses CHARACTERS, not tokens.
# ~512 tokens ≈ ~2000 characters (1 token ≈ 4 chars for English).
# Previous: 512 chars (~128 tokens) — too small, split paragraphs mid-sentence.
CHUNK_SIZE = 2000

CHUNK_OVERLAP = 200  # ~10% overlap to preserve context at boundaries

#- Data Path Configuration -
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_PATH = os.path.join(DATA_DIR, "dubai_properties.csv")
DOCS_DIR = os.path.join(DATA_DIR, "Documents")