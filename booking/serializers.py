from rest_framework import serializers

from faq.models import Faq
from offices.models import Office
from pronto.i18n import TranslatedField

from .models import Appointment, EmployeeProfile, Shift
from .services import BookingError, book_appointment


class OfficeSerializer(serializers.ModelSerializer):
    """An office a student can book with, named in the caller's language."""

    name = TranslatedField()

    class Meta:
        model = Office
        fields = ["code", "name", "contact_email", "slot_duration_minutes"]
        read_only_fields = fields


class AvailabilitySerializer(serializers.Serializer):
    """Validates the ``date`` query parameter and renders the free slots."""

    office = serializers.CharField(read_only=True)
    date = serializers.DateField()
    slots = serializers.ListField(child=serializers.DateTimeField(), read_only=True)


class AppointmentSerializer(serializers.ModelSerializer):
    """An appointment, with the office as a code and people as e-mails."""

    office = serializers.SlugRelatedField(slug_field="code", read_only=True)
    student = serializers.EmailField(source="student.email", read_only=True)
    employee = serializers.EmailField(source="employee.user.email", read_only=True)
    faq_id = serializers.IntegerField(
        source="suggested_faq_id", read_only=True, allow_null=True
    )

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
            "faq_id",
            "created_at",
        ]
        read_only_fields = fields


class AppointmentCreateSerializer(serializers.ModelSerializer):
    """What a student sends to book; the service assigns the employee."""

    office = serializers.SlugRelatedField(
        slug_field="code", queryset=Office.objects.filter(is_active=True)
    )
    faq_id = serializers.PrimaryKeyRelatedField(
        source="suggested_faq",
        queryset=Faq.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Appointment
        fields = ["office", "slot", "question_text", "question_lang", "faq_id"]

    def create(self, validated_data):
        try:
            return book_appointment(
                student=self.context["request"].user, **validated_data
            )
        except BookingError as error:
            raise serializers.ValidationError({"slot": str(error)}) from error


class EmployeeProfileSerializer(serializers.ModelSerializer):
    """The office an employee works for, by code; only active offices."""

    office = serializers.SlugRelatedField(
        slug_field="code", queryset=Office.objects.filter(is_active=True)
    )

    class Meta:
        model = EmployeeProfile
        fields = ["office"]


class ShiftSerializer(serializers.ModelSerializer):
    """A weekly shift. The rules are checked by `declare_shift`."""

    class Meta:
        model = Shift
        fields = ["id", "weekday", "start_time", "end_time"]
        read_only_fields = ["id"]
