"""Tests for the health-check endpoint."""

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
    # Written by semantic-release: a semantic version.
    assert re.fullmatch(r"\d+\.\d+\.\d+(-[\w.]+)?", settings.VERSION)
