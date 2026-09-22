from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("offices/", views.OfficeListView.as_view(), name="office-list"),
    path(
        "offices/<str:code>/availability/",
        views.OfficeAvailabilityView.as_view(),
        name="office-availability",
    ),
    path(
        "appointments/",
        views.AppointmentListCreateView.as_view(),
        name="appointment-list",
    ),
    path(
        "appointments/<int:pk>/cancel/",
        views.AppointmentCancelView.as_view(),
        name="appointment-cancel",
    ),
]
