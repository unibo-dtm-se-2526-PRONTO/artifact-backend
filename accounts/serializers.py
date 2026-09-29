from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

User = get_user_model()

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
        # Blank-able on the model, for the accounts that predate them, but
        # mandatory for anyone signing up. The student data stays optional
        # here: whether it is required or refused depends on the role, which
        # validate() derives and checks through the model's clean().
        extra_kwargs = {
            "first_name": {"required": True, "allow_blank": False},
            "last_name": {"required": True, "allow_blank": False},
        }

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
        profile = {key: value for key, value in attrs.items() if key != "password"}
        candidate = User(**profile)
        errors = {}
        try:
            candidate.clean()
        except DjangoValidationError as error:
            errors.update(error.message_dict)
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

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    """Validates credentials and exposes the authenticated user."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        # authenticate() rejects inactive users too, so an unverified account
        # cannot log in. The error stays generic on purpose: telling the caller
        # that the account exists but is unverified would leak who is registered.
        user = authenticate(username=attrs["email"].lower(), password=attrs["password"])
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")
        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """Read-only representation of a user."""

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
