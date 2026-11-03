from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from offices.models import Office
from pronto.enums import Role
from pronto.i18n import LanguageAwareMixin
from pronto.permissions import IsEmployee, IsStudent

from .models import Appointment, EmployeeProfile, Shift
from .serializers import (
    AppointmentCreateSerializer,
    AppointmentSerializer,
    AvailabilitySerializer,
    EmployeeProfileSerializer,
    OfficeSerializer,
    ShiftSerializer,
)
from .services import (
    BookingError,
    ShiftInUseError,
    available_slots,
    cancel_appointment,
    complete_appointment,
    declare_shift,
    withdraw_shift,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    """Report that the service is up, and which release is running."""
    return Response(
        {"status": "ok", "version": settings.VERSION}, status=status.HTTP_200_OK
    )


class OfficeListView(LanguageAwareMixin, generics.ListAPIView):
    """The offices currently taking bookings."""

    serializer_class = OfficeSerializer
    queryset = Office.objects.filter(is_active=True)


class OfficeAvailabilityView(APIView):
    """The slots of one day a student can still book at one office."""

    def get(self, request, code):
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
    """Limits appointments to the caller's, so anyone else's answers 404."""

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
        # The read serializer includes the id and the assigned employee.
        return Response(
            AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED
        )


class AppointmentCancelView(AppointmentQuerysetMixin, generics.GenericAPIView):
    """Cancel one of the caller's appointments, freeing its slot."""

    serializer_class = AppointmentSerializer

    def post(self, request, *args, **kwargs):
        try:
            cancel_appointment(self.get_object(), by=request.user)
        except BookingError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AppointmentCompleteView(AppointmentQuerysetMixin, generics.GenericAPIView):
    """Record that an appointment assigned to the caller has taken place."""

    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated, IsEmployee]

    def post(self, request, *args, **kwargs):
        try:
            complete_appointment(self.get_object())
        except BookingError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmployeeProfileView(APIView):
    """The calling employee's office, chosen once; then only an admin changes it."""

    permission_classes = [IsAuthenticated, IsEmployee]

    def get(self, request):
        profile = get_object_or_404(EmployeeProfile, user=request.user)
        return Response(EmployeeProfileSerializer(profile).data)

    def post(self, request):
        if EmployeeProfile.objects.filter(user=request.user).exists():
            return Response(
                {
                    "detail": "Your office is already set; ask an administrator to change it."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = EmployeeProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ShiftListCreateView(APIView):
    """The calling employee's weekly shifts, or a new one. No update."""

    permission_classes = [IsAuthenticated, IsEmployee]

    def get(self, request):
        shifts = Shift.objects.filter(employee__user=request.user)
        return Response(ShiftSerializer(shifts, many=True).data)

    def post(self, request):
        profile = EmployeeProfile.objects.filter(user=request.user).first()
        if profile is None:
            return Response(
                {"detail": "Choose your office before declaring shifts."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ShiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            shift = declare_shift(employee=profile, **serializer.validated_data)
        except BookingError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ShiftSerializer(shift).data, status=status.HTTP_201_CREATED)


class ShiftDetailView(APIView):
    """Withdraw one of the calling employee's shifts."""

    permission_classes = [IsAuthenticated, IsEmployee]

    def delete(self, request, pk):
        shift = get_object_or_404(Shift, pk=pk, employee__user=request.user)
        try:
            withdraw_shift(shift)
        except ShiftInUseError as error:
            return Response(
                {
                    "detail": str(error),
                    "appointments": [held.pk for held in error.appointments],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
