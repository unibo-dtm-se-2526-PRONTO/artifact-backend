from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import MATRICOLA_TAKEN, StudentProfile, matricola_validator

User = get_user_model()

# Sent and returned alongside the user's own fields, but stored in the
# student's `StudentProfile`.
STUDENT_FIELDS = ("matricola", "degree_programme")

# Institutional email domains, and the role each one grants.
ROLE_BY_EMAIL_DOMAIN = {
    "studio.unibo.it": User.Role.STUDENT,
    "unibo.it": User.Role.EMPLOYEE,
}


class LowercaseEmailField(serializers.EmailField):
    """An email field that lowercases before anything else looks at the value.

    Lowercasing in ``validate_email`` would come too late: DRF runs the field
    validators, uniqueness included, first, so the same address in a different
    case would slip past the unique constraint.
    """

    def to_internal_value(self, data):
        return super().to_internal_value(data).lower()


class RegisterSerializer(serializers.ModelSerializer):
    """Creates a user whose role is derived from the email domain."""

    # Declared explicitly, so the uniqueness check ModelSerializer would have
    # added on its own has to be spelled out here too.
    email = LowercaseEmailField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(write_only=True)
    # Not columns of User, so declared here. Optional, and blank-able, for
    # everybody: whether they are required or refused depends on the role,
    # which validate() derives. The validators are the ones a field generated
    # from the user's old columns had, in the same order, so the errors read
    # the same.
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
        # Only reached once every field is valid, so the email is known to be
        # institutional and the role can be derived here, where the checks
        # that depend on it run.
        attrs["role"] = ROLE_BY_EMAIL_DOMAIN[attrs["email"].rsplit("@", 1)[-1]]
        account = {
            key: value
            for key, value in attrs.items()
            if key != "password" and key not in STUDENT_FIELDS
        }
        candidate = User(**account)
        errors = self.student_data_errors(attrs)
        # Validated here rather than as a field validator: the similarity check
        # needs the user the password belongs to — their email and names —
        # which a field validator lacks.
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as error:
            errors["password"] = list(error.messages)
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    @staticmethod
    def student_data_errors(attrs):
        """Required of a student, refused from anyone else.

        Refused rather than dropped: an employee sending a matricola has most
        likely typed the wrong address, and ignoring it would hide that.
        """
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
        # One transaction: a student whose profile cannot be written must not
        # be left behind as an account without one.
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
        # authenticate() rejects inactive users too, so an account an admin has
        # deactivated cannot log in. The error stays generic on purpose: telling
        # the caller that the account exists but is deactivated would leak who
        # is registered.
        user = authenticate(username=attrs["email"].lower(), password=attrs["password"])
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")
        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """Read-only representation of a user.

    The student data comes from the student profile. Everybody else has none,
    and gets ``""`` for it, so the shape is the same for every role.
    """

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
