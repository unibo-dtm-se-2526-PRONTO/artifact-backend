from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    """Create an account. Public: the caller has no token yet."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


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
