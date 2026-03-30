import os
from dotenv import load_dotenv

load_dotenv()

# --- API ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = os.getenv("LLM_MODEL", "google/gemma-3-27b-it:free")

# --- Qdrant (for RAG tool — PDF market reports) ---
QDRANT_HOST = os.getenv("QDRANT_HOST", os.getenv("QUADRANT_HOST", "localhost"))
QDRANT_PORT = int(os.getenv("QDRANT_PORT", os.getenv("QUADRANT_PORT", 6333)))
COLLECTION_NAME = "uae_properties"
EMBEDDING_MODEL = "text-embedding-3-small"

# --- CSV (for structured property queries) ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "dubai_properties.csv")

# --- Agent System B (external microservice) ---
AGENT_B_URL = os.getenv("AGENT_B_URL", "http://localhost:8001")

# --- MCP Server ---
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8002")

# --- Groq (Whisper speech-to-text) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# --- Server ---
HOST = "0.0.0.0"
PORT = 8000
