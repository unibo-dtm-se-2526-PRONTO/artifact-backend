"""The project's routes: the admin, and each app's API under ``api/``."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("booking.urls")),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("faq.urls")),
]
