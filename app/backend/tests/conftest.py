import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("LLM_ENDPOINT_URL", "http://localhost:11434/v1")
os.environ.setdefault("LLM_MODEL_NAME", "test-model")
