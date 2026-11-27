import re
from enum import Enum


class QueryType(Enum):
    VECTOR_SEARCH = "vector"      # Semantic search in runbooks
    LIST_SOURCES = "list"         # "What runbooks do you have?"
    METADATA_FILTER = "metadata"  # Structured query (filter by source)


_LIST_PHRASES = (
    "what runbooks", "list runbooks", "show me all", "which runbooks do you have",
    "what do you have", "available documents", "available runbooks",
)

_METADATA_PATTERN = re.compile(
    r"""(?:in|from)\s+(?:the\s+)?["'](?P<source>.*?)["']""",
    re.IGNORECASE,
)


def route_query(query: str) -> QueryType:
    """Classify a user query to choose a retrieval strategy."""
    q_lower = query.lower()

    if any(phrase in q_lower for phrase in _LIST_PHRASES):
        return QueryType.LIST_SOURCES

    if _METADATA_PATTERN.search(query):
        return QueryType.METADATA_FILTER

    return QueryType.VECTOR_SEARCH


def extract_metadata_filter(query: str) -> str | None:
    """Pull a quoted source-document filter out of a metadata-style query."""
    match = _METADATA_PATTERN.search(query)
    return match.group("source") if match else None
