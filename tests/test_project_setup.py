from django.apps import apps


def test_booking_app_is_installed():
    assert apps.is_installed("booking")


def test_rest_framework_is_installed():
    assert apps.is_installed("rest_framework")
