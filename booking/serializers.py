from rest_framework import serializers

from pronto.i18n import TranslatedField

from .models import Appointment, EmployeeProfile, Office, Shift
from .services import BookingError, book_appointment


class OfficeSerializer(serializers.ModelSerializer):
    """An office a student can book with, named in the caller's language."""

    name = TranslatedField()

    class Meta:
        model = Office
        fields = ["code", "name", "contact_email", "slot_duration_minutes"]
        read_only_fields = fields


class AvailabilitySerializer(serializers.Serializer):
    """The free slots of one office on one day.

    Used in both directions: it validates the ``date`` query parameter on the
    way in — a missing or malformed date is a 400, not a silent fallback to
    today — and renders the answer on the way out.
    """

    office = serializers.CharField(read_only=True)
    date = serializers.DateField()
    slots = serializers.ListField(child=serializers.DateTimeField(), read_only=True)


class AppointmentSerializer(serializers.ModelSerializer):
    """How an appointment is read back.

    Related rows are flattened to the identifiers the frontend already works
    with — an office code and an email address — rather than nested objects it
    would have to unwrap.
    """

    office = serializers.SlugRelatedField(slug_field="code", read_only=True)
    student = serializers.EmailField(source="student.email", read_only=True)
    employee = serializers.EmailField(source="employee.user.email", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "office",
            "student",
            "employee",
            "slot",
            "status",
            "question_text",
            "question_lang",
            "created_at",
        ]
        read_only_fields = fields


class AppointmentCreateSerializer(serializers.ModelSerializer):
    """What a student sends to book.

    Neither the employee nor the status is accepted from the client: who takes
    the appointment is the service's decision, made from the office's own
    staff. Restricting the queryset to active offices also makes a closed or
    unknown office a field error rather than a booking that reaches the
    service only to be refused.
    """

    office = serializers.SlugRelatedField(
        slug_field="code", queryset=Office.objects.filter(is_active=True)
    )

    class Meta:
        model = Appointment
        fields = ["office", "slot", "question_text", "question_lang"]

    def create(self, validated_data):
        try:
            return book_appointment(
                student=self.context["request"].user, **validated_data
            )
        except BookingError as error:
            # A refused booking is a problem with the slot that was asked for,
            # so it is reported on that field and not as a bare detail string.
            raise serializers.ValidationError({"slot": str(error)}) from error


class EmployeeProfileSerializer(serializers.ModelSerializer):
    """The office an employee works for, named by its code.

    Only active offices can be chosen, so a closed or unknown one is a field
    error, as it is when a student books.
    """

    office = serializers.SlugRelatedField(
        slug_field="code", queryset=Office.objects.filter(is_active=True)
    )

    class Meta:
        model = EmployeeProfile
        fields = ["office"]


class ShiftSerializer(serializers.ModelSerializer):
    """A weekly shift, read back and declared in the same shape.

    It only checks the fields one by one; whether the shift fits the grid and
    the rest of the employee's week is `declare_shift`'s call, which the view
    makes.
    """

    class Meta:
        model = Shift
        fields = ["id", "weekday", "start_time", "end_time"]
        read_only_fields = ["id"]
