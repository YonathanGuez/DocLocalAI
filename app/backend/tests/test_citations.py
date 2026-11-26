from app.services.citations import (
    build_context_with_citations,
    extract_citations,
    format_citations_footer,
)


def test_build_context_with_citations_labels_each_chunk():
    rows = [
        ("pods.md", "Restart a pod with kubectl delete pod.", 0.9),
        ("network.md", "Check routes with oc get routes.", 0.7),
    ]
    context, chunk_map = build_context_with_citations(rows)

    assert "[1] [Source: pods.md]" in context
    assert "[2] [Source: network.md]" in context
    assert chunk_map["[1]"] == ("pods.md", "Restart a pod with kubectl delete pod.")
    assert chunk_map["[2]"] == ("network.md", "Check routes with oc get routes.")


def test_extract_citations_validates_against_chunk_map():
    chunk_map = {"[1]": ("pods.md", "Restart a pod.")}
    response = "To restart a pod [1], run the command. See also [2] for details."

    citations = extract_citations(response, chunk_map)

    assert citations["1"]["valid"] is True
    assert citations["1"]["source"] == "pods.md"
    assert citations["2"]["valid"] is False


def test_format_citations_footer_lists_only_valid_sources():
    citation_details = {
        "1": {"valid": True, "source": "pods.md"},
        "2": {"valid": False},
    }
    footer = format_citations_footer(citation_details)

    assert "[1] pods.md" in footer
    assert "[2]" not in footer


def test_format_citations_footer_empty_when_no_valid_citations():
    assert format_citations_footer({"1": {"valid": False}}) == ""
