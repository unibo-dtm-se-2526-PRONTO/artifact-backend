from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response


@api_view(["GET"])
def health(request: Request) -> Response:
    """Report that the service is up. Used by monitoring and deployment checks."""
    return Response({"status": "ok"}, status=status.HTTP_200_OK)
