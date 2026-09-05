from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()

# Institutional email domains, and the role each one grants.
ROLE_BY_EMAIL_DOMAIN = {
    "studio.unibo.it": User.Role.STUDENT,
    "unibo.it": User.Role.EMPLOYEE,
}


class RegisterSerializer(serializers.ModelSerializer):
    """Creates a user whose role is derived from the email domain."""

    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "email", "password", "role"]
        read_only_fields = ["id", "role"]

    def validate_email(self, value):
        domain = value.rsplit("@", 1)[-1].lower()
        if domain not in ROLE_BY_EMAIL_DOMAIN:
            raise serializers.ValidationError(
                "Registration is restricted to institutional email addresses."
            )
        return value

    def create(self, validated_data):
        domain = validated_data["email"].rsplit("@", 1)[-1].lower()
        return User.objects.create_user(
            role=ROLE_BY_EMAIL_DOMAIN[domain], **validated_data
        )


class LoginSerializer(serializers.Serializer):
    """Validates credentials and exposes the authenticated user."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs["email"], password=attrs["password"])
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")
        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """Read-only representation of a user."""

    class Meta:
        model = User
        fields = ["id", "email", "role"]
        read_only_fields = fields
