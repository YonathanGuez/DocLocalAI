import re

_AMBIGUOUS_PATTERNS = (
    re.compile(r"^(how|what|why|when)\s*\??\s*$", re.IGNORECASE),
    re.compile(r"^(it|that|this|the)\b", re.IGNORECASE),
)

_PRONOUN_WORDS = ("it", "that", "this", "above")

_EXPANSION_MAP = {
    "pod": ["container", "deployment", "workload"],
    "network": ["networking", "connectivity", "route"],
    "error": ["failure", "issue", "problem"],
}


def is_ambiguous(query: str) -> bool:
    """Detect queries too vague to retrieve against without clarification."""
    stripped = query.strip()
    return any(p.search(stripped) for p in _AMBIGUOUS_PATTERNS)


def needs_history_rewrite(query: str, history: list[dict]) -> bool:
    """Whether the query references prior turns and should be rewritten standalone."""
    if not history:
        return False
    q_lower = query.lower()
    return any(word in q_lower for word in _PRONOUN_WORDS)


def expand_query(query: str, limit: int = 3) -> list[str]:
    """Generate simple synonym-based query variations for broader recall."""
    expansions = [query]
    q_lower = query.lower()

    for key, synonyms in _EXPANSION_MAP.items():
        if key in q_lower:
            for syn in synonyms:
                expansions.append(re.sub(key, syn, query, flags=re.IGNORECASE))

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for e in expansions:
        if e not in seen:
            seen.add(e)
            unique.append(e)

    return unique[:limit]


def build_rewrite_prompt(query: str, history: list[dict]) -> str:
    """Build the LLM prompt used to resolve pronouns into a standalone query."""
    recent = history[-3:]
    conversation = "\n".join(f"{m['role']}: {m['content'][:100]}" for m in recent)
    return (
        "Rewrite this query as a standalone question by resolving pronouns.\n\n"
        f"Recent conversation:\n{conversation}\n\n"
        f"User query: {query}\n\n"
        "Standalone query:"
    )
