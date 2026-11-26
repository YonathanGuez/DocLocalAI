from app.services.query_router import QueryType, extract_metadata_filter, route_query


def test_route_query_detects_list_sources():
    assert route_query("What runbooks do you have?") == QueryType.LIST_SOURCES
    assert route_query("show me all available documents") == QueryType.LIST_SOURCES


def test_route_query_detects_metadata_filter():
    assert route_query('What does it say in the "networking.md" runbook?') == QueryType.METADATA_FILTER


def test_route_query_defaults_to_vector_search():
    assert route_query("How do I restart a pod?") == QueryType.VECTOR_SEARCH


def test_extract_metadata_filter_returns_quoted_source():
    assert extract_metadata_filter('from the "networking.md" guide') == "networking.md"


def test_extract_metadata_filter_returns_none_when_absent():
    assert extract_metadata_filter("How do I restart a pod?") is None
