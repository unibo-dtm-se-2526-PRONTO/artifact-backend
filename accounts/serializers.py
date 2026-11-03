from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import MATRICOLA_TAKEN, StudentProfile, matricola_validator

User = get_user_model()

# Stored in the student's `StudentProfile`.
STUDENT_FIELDS = ("matricola", "degree_programme")

# Institutional email domains, and the role each one grants.
ROLE_BY_EMAIL_DOMAIN = {
    "studio.unibo.it": User.Role.STUDENT,
    "unibo.it": User.Role.EMPLOYEE,
}


class LowercaseEmailField(serializers.EmailField):
    """Lowercases the email before the uniqueness validator runs."""

    def to_internal_value(self, data):
        return super().to_internal_value(data).lower()


class RegisterSerializer(serializers.ModelSerializer):
    """Creates a user whose role is derived from the email domain."""

    email = LowercaseEmailField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(write_only=True)
    # Required or refused depending on the role, checked in validate().
    matricola = serializers.CharField(
        max_length=10,
        required=False,
        allow_blank=True,
        validators=[
            matricola_validator,
            UniqueValidator(
                queryset=StudentProfile.objects.all(), message=MATRICOLA_TAKEN
            ),
        ],
        help_text="Solo per gli studenti: il numero di matricola Unibo, da 6 a 10 cifre.",
    )
    degree_programme = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        label="Corso di studi",
        help_text="Solo per gli studenti: il corso di laurea a cui sono iscritti.",
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "password",
            "role",
            "first_name",
            "last_name",
            "matricola",
            "degree_programme",
        ]
        read_only_fields = ["id", "role"]

    def validate_email(self, value):
        domain = value.rsplit("@", 1)[-1]
        if domain not in ROLE_BY_EMAIL_DOMAIN:
            raise serializers.ValidationError(
                "Registration is restricted to institutional email addresses."
            )
        return value

    def validate(self, attrs):
        attrs["role"] = ROLE_BY_EMAIL_DOMAIN[attrs["email"].rsplit("@", 1)[-1]]
        account = {
            key: value
            for key, value in attrs.items()
            if key != "password" and key not in STUDENT_FIELDS
        }
        candidate = User(**account)
        errors = self.student_data_errors(attrs)
        # Here, because the similarity check needs the user's email and names.
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as error:
            errors["password"] = list(error.messages)
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    @staticmethod
    def student_data_errors(attrs):
        """Student fields are required of a student and refused from anyone else."""
        errors = {}
        for field in STUDENT_FIELDS:
            given = bool(attrs.get(field, "").strip())
            if attrs["role"] == User.Role.STUDENT and not given:
                errors[field] = ["This field is required."]
            elif attrs["role"] != User.Role.STUDENT and given:
                errors[field] = ["Only students have this field."]
        return errors

    def create(self, validated_data):
        student = {field: validated_data.pop(field, "") for field in STUDENT_FIELDS}
        with transaction.atomic():
            user = User.objects.create_user(**validated_data)
            if user.role == User.Role.STUDENT:
                StudentProfile.objects.create(user=user, **student)
        return user

    def to_representation(self, instance):
        # The same shape as GET /api/auth/me/, student data included.
        return UserSerializer(instance, context=self.context).data


class LoginSerializer(serializers.Serializer):
    """Validates credentials and exposes the authenticated user."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        # Generic error on purpose, also for inactive users: it does not reveal
        # who is registered.
        user = authenticate(username=attrs["email"].lower(), password=attrs["password"])
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")
        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """Read-only user; non-students get ``""`` for the student fields."""

    matricola = serializers.SerializerMethodField()
    degree_programme = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "role",
            "first_name",
            "last_name",
            "matricola",
            "degree_programme",
        ]
        read_only_fields = fields

    def get_matricola(self, user) -> str:
        profile = student_profile_of(user)
        return profile.matricola if profile else ""

    def get_degree_programme(self, user) -> str:
        profile = student_profile_of(user)
        return profile.degree_programme if profile else ""


def student_profile_of(user):
    """The user's student profile, or None if they have none."""
    try:
        return user.student_profile
    except StudentProfile.DoesNotExist:
        return None
