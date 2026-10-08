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
    path(
        "appointments/<int:pk>/complete/",
        views.AppointmentCompleteView.as_view(),
        name="appointment-complete",
    ),
    path(
        "employee-profile/",
        views.EmployeeProfileView.as_view(),
        name="employee-profile",
    ),
    path("shifts/", views.ShiftListCreateView.as_view(), name="shift-list"),
    path("shifts/<int:pk>/", views.ShiftDetailView.as_view(), name="shift-detail"),
]
