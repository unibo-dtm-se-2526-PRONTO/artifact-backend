"""Tests for the health-check endpoint.

This is the reference example for API tests: use DRF's APIClient, hit the URL
the frontend would hit, and assert on status code and response body.
"""

import re

from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient


def test_health_endpoint_returns_ok():
    client = APIClient()

    response = client.get("/api/health/")

    assert (
        response.status_code == status.HTTP_200_OK
    )  # assert controlla il risultato dopo aver eseguito il test
    assert response.json() == {"status": "ok", "version": settings.VERSION}


def test_the_version_is_a_semantic_version():
    # semantic-release writes it there; a semantic version, never a placeholder
    assert re.fullmatch(r"\d+\.\d+\.\d+(-[\w.]+)?", settings.VERSION)
