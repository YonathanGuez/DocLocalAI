import re

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def build_context_with_citations(rows: list[tuple[str, str, float]]) -> tuple[str, dict[str, tuple[str, str]]]:
    """Build a context string with [N] markers per chunk and a chunk_id -> (source, content) map."""
    context_parts = []
    chunk_map: dict[str, tuple[str, str]] = {}

    for idx, (source, content, _score) in enumerate(rows, 1):
        chunk_id = f"[{idx}]"
        context_parts.append(f"{chunk_id} [Source: {source}]\n{content}")
        chunk_map[chunk_id] = (source, content)

    return "\n\n".join(context_parts), chunk_map


def extract_citations(response: str, chunk_map: dict[str, tuple[str, str]]) -> dict[str, dict]:
    """Extract [N] citations from a response and validate them against chunk_map."""
    cited_ids = _CITATION_PATTERN.findall(response)

    citation_details: dict[str, dict] = {}
    for cite_id in sorted(set(cited_ids), key=int):
        chunk_id = f"[{cite_id}]"
        if chunk_id in chunk_map:
            source, content = chunk_map[chunk_id]
            citation_details[cite_id] = {
                "source": source,
                "content_preview": content[:100] + ("..." if len(content) > 100 else ""),
                "valid": True,
            }
        else:
            citation_details[cite_id] = {"valid": False}

    return citation_details


def format_citations_footer(citation_details: dict[str, dict]) -> str:
    """Format a references footer listing only valid, cited sources."""
    valid_entries = [
        (cite_id, details["source"])
        for cite_id, details in sorted(citation_details.items(), key=lambda kv: int(kv[0]))
        if details.get("valid")
    ]

    if not valid_entries:
        return ""

    footer = "\n\n---\n**References:**\n"
    footer += "\n".join(f"[{cite_id}] {source}" for cite_id, source in valid_entries)
    return footer
