"""Ten integration tests that run against the live ECS HTTPS endpoint."""

import json

import pytest


pytestmark = pytest.mark.integration


def assert_query_response(response, question, max_response_seconds):
    """Validate the structure of a successful query response."""
    assert response.status_code == 200, response.text
    assert response.elapsed.total_seconds() < max_response_seconds
    assert response.headers.get("X-Request-ID")

    body = response.json()
    assert body["question"] == question
    assert isinstance(body["answer"], str) and body["answer"].strip()
    assert isinstance(body["request_id"], str) and body["request_id"]
    assert body["request_id"] == response.headers["X-Request-ID"]
    return body


def test_01_health_endpoint(http_session, base_url, request_timeout):
    """Verify that the live health endpoint reports a healthy status."""
    response = http_session.get(f"{base_url}/health", timeout=request_timeout)
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    assert response.headers.get("X-Request-ID")


def test_02_root_endpoint(http_session, base_url, request_timeout):
    """Verify that the root endpoint returns basic API information."""
    response = http_session.get(base_url, timeout=request_timeout)
    assert response.status_code == 200
    body = response.json()
    assert "message" in body
    assert body["docs"] == "/docs"


def test_03_ferrari_happy_path(
    http_session, base_url, request_timeout, max_response_seconds
):
    """Verify that a valid Ferrari query returns a successful response."""
    question = "Which Ferrari cars have more than 700 horsepower?"
    response = http_session.post(
        f"{base_url}/query", json={"question": question}, timeout=request_timeout
    )
    body = assert_query_response(response, question, max_response_seconds)
    assert "ferrari" in body["answer"].lower()


def test_04_graph_ranked_domain_query(
    http_session, base_url, request_timeout, max_response_seconds
):
    """Verify that a graph-ranked automotive query succeeds."""
    question = "What are the five most important Porsche cars in the graph?"
    response = http_session.post(
        f"{base_url}/query", json={"question": question}, timeout=request_timeout
    )
    body = assert_query_response(response, question, max_response_seconds)
    assert "pagerank" in body["answer"].lower()


def test_05_electric_vehicle_edge_case(
    http_session, base_url, request_timeout, max_response_seconds
):
    """Verify that an electric-vehicle edge-case query is handled."""
    question = "List up to three electric vehicles in the dataset."
    response = http_session.post(
        f"{base_url}/query", json={"question": question}, timeout=request_timeout
    )
    assert_query_response(response, question, max_response_seconds)


def test_06_no_matching_brand_edge_case(
    http_session, base_url, request_timeout, max_response_seconds
):
    """Verify that a query with no matching brand is handled."""
    question = "List Dacia vehicles with at least 900 horsepower."
    response = http_session.post(
        f"{base_url}/query", json={"question": question}, timeout=request_timeout
    )
    assert_query_response(response, question, max_response_seconds)


def test_07_empty_question(http_session, base_url, request_timeout):
    """Verify that an empty question is rejected by validation."""
    response = http_session.post(
        f"{base_url}/query", json={"question": ""}, timeout=request_timeout
    )
    assert response.status_code == 422
    assert response.json()["detail"]


def test_08_whitespace_only_question(http_session, base_url, request_timeout):
    """Verify that a whitespace-only question is rejected as blank."""
    response = http_session.post(
        f"{base_url}/query", json={"question": "   "}, timeout=request_timeout
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Question must not be blank"


def test_09_very_long_question(http_session, base_url, request_timeout):
    """Verify that an excessively long question is rejected."""
    response = http_session.post(
        f"{base_url}/query", json={"question": "x" * 4001}, timeout=request_timeout
    )
    assert response.status_code == 422
    assert response.json()["detail"]


def test_10_malformed_json(http_session, base_url, request_timeout):
    """Verify that malformed JSON is rejected by the query endpoint."""
    response = http_session.post(
        f"{base_url}/query",
        data=json.dumps({"question": "broken"})[:-1],
        headers={"Content-Type": "application/json"},
        timeout=request_timeout,
    )
    assert response.status_code == 422
    assert response.json()["detail"]
