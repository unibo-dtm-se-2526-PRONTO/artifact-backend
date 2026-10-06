from django.contrib.auth.signals import user_logged_in
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, RegisterSerializer, UserSerializer
from .verification import activate


class RegisterView(generics.CreateAPIView):
    """Create an account. Public: the caller has no token yet."""

    serializer_class = RegisterSerializer  # delega tutta la logica al serializer
    permission_classes = [AllowAny]


class VerifyEmailView(APIView):
    """Activate the account the verification link points to."""

    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        if activate(uidb64, token) is None:
            return Response(
                {"detail": "This verification link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": "Account verified."}, status=status.HTTP_200_OK)


class LoginView(APIView):
    """Exchange email and password for an authentication token."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        # Sent by django.contrib.auth.login() for a session login, which this
        # view does not open. Sending it here runs the same receivers, among
        # them Django's own update_last_login, so last_login records token
        # logins too: NULL means the user has never logged in.
        user_logged_in.send(sender=user.__class__, request=request, user=user)
        return Response({"token": token.key}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """Delete the authenticated user's token, invalidating it."""

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveAPIView):
    """Return the authenticated user's own data."""

    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
