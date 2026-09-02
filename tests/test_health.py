"""Tests for the health-check endpoint.

This is the reference example for API tests: use DRF's APIClient, hit the URL
the frontend would hit, and assert on status code and response body.
"""

from rest_framework import status
from rest_framework.test import APIClient


def test_health_endpoint_returns_ok():
    client = APIClient()

    response = client.get("/api/health/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
