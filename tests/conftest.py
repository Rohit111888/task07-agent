"""Configuration shared by the live ECS integration tests."""

import os

import pytest
import requests


def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        action="store",
        default=os.getenv("LIVE_BASE_URL", "https://testagent.cciplatform-ai.com"),
        help="Base URL of the deployed Task 08 API",
    )


@pytest.fixture(scope="session")
def base_url(request):
    return request.config.getoption("--base-url").rstrip("/")


@pytest.fixture(scope="session")
def request_timeout():
    return float(os.getenv("REQUEST_TIMEOUT_SECONDS", "120"))


@pytest.fixture(scope="session")
def max_response_seconds():
    return float(os.getenv("MAX_RESPONSE_SECONDS", "120"))


@pytest.fixture(scope="session")
def http_session():
    session = requests.Session()
    session.headers.update({"User-Agent": "task08-pytest-integration/1.0"})
    yield session
    session.close()
