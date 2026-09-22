from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from pronto.enums import Role
from pronto.i18n import LanguageAwareMixin

from .models import Appointment, Office
from .permissions import IsStudent
from .serializers import (
    AppointmentCreateSerializer,
    AppointmentSerializer,
    AvailabilitySerializer,
    OfficeSerializer,
)
from .services import BookingError, available_slots, cancel_appointment


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    """Report that the service is up. Used by monitoring and deployment checks."""
    return Response({"status": "ok"}, status=status.HTTP_200_OK)


class OfficeListView(LanguageAwareMixin, generics.ListAPIView):
    """The offices currently taking bookings."""

    serializer_class = OfficeSerializer
    queryset = Office.objects.filter(is_active=True)


class OfficeAvailabilityView(APIView):
    """The slots of one day a student can still book at one office."""

    def get(self, request, code):
        # Inactive offices are hidden rather than returned empty: an office
        # that is not taking bookings has no availability to talk about.
        office = get_object_or_404(Office, code=code, is_active=True)

        query = AvailabilitySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        day = query.validated_data["date"]

        answer = AvailabilitySerializer(
            {
                "office": office.code,
                "date": day,
                "slots": available_slots(office, day),
            }
        )
        return Response(answer.data, status=status.HTTP_200_OK)


class AppointmentQuerysetMixin:
    """Scopes every appointment view to what the caller is allowed to see.

    Scoping the queryset instead of checking ownership object by object means
    someone else's appointment answers 404: whether it exists at all is not
    the caller's business.
    """

    def get_queryset(self):
        appointments = Appointment.objects.select_related(
            "office", "student", "employee__user"
        )
        user = self.request.user
        if user.role == Role.STUDENT:
            return appointments.filter(student=user)
        if user.role == Role.EMPLOYEE:
            return appointments.filter(employee__user=user)
        return appointments  # an admin oversees the whole helpdesk


class AppointmentListCreateView(AppointmentQuerysetMixin, generics.ListCreateAPIView):
    """List the caller's appointments, or book a new one."""

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AppointmentCreateSerializer
        return AppointmentSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsStudent()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment = serializer.save()
        # Answered with the read serializer: the caller needs the id and the
        # employee the service assigned, neither of which the write serializer
        # carries.
        return Response(
            AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED
        )


class AppointmentCancelView(AppointmentQuerysetMixin, generics.GenericAPIView):
    """Cancel one of the caller's appointments, freeing its slot."""

    serializer_class = AppointmentSerializer

    def post(self, request, *args, **kwargs):
        try:
            cancel_appointment(self.get_object())
        except BookingError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)
