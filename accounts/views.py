from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, RegisterSerializer, UserSerializer
from .verification import activate, send_verification_email


class RegisterView(generics.CreateAPIView):
    """Create an account. Public: the caller has no token yet."""

    serializer_class = RegisterSerializer  # delega tutta la logica al serializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        # The account is created inactive; the link in this email activates it.
        send_verification_email(serializer.save())


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
        token, _ = Token.objects.get_or_create(user=serializer.validated_data["user"])
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
