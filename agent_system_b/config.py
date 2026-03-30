import os
from dotenv import load_dotenv

load_dotenv()

# --- API ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Google ADK agent uses litellm's "openai/" provider → routes to OpenRouter
# litellm reads OPENAI_API_KEY + OPENAI_API_BASE from env for this provider
LLM_MODEL = "openai/qwen/qwen3-coder:free"
LLM_MODEL_OPENAI = "qwen/qwen3-coder:free"     # For direct OpenAI SDK client calls
EMBEDDING_MODEL = "text-embedding-3-small"

# Set env vars so litellm's "openai/" provider routes through OpenRouter
os.environ.setdefault("OPENAI_API_KEY", OPENROUTER_API_KEY or "")
os.environ.setdefault("OPENAI_API_BASE", OPENROUTER_BASE_URL)

# --- Qdrant (for comp finder — PDF market reports) ---
QDRANT_HOST = os.getenv("QDRANT_HOST", os.getenv("QUADRANT_HOST", "localhost"))
QDRANT_PORT = int(os.getenv("QDRANT_PORT", os.getenv("QUADRANT_PORT", 6333)))
COLLECTION_NAME = "uae_properties"

# --- CSV (for structured property queries via pandas) ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "dubai_properties.csv")

# --- Server ---
HOST = "0.0.0.0"
PORT = 8001
