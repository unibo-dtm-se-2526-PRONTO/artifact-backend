from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from pronto.enums import OfficeCode
from pronto.i18n import LanguageAwareMixin, requested_language
from pronto.permissions import IsStudent

from .models import Faq, Inquiry
from .serializers import FaqSerializer, InquirySerializer, QuestionSerializer
from .services import InquiryError, ask_question, resolve_inquiry


class PublishedFaqMixin(LanguageAwareMixin):
    """What both FAQ views share: the published rows, readable by anyone.

    Public on purpose, unlike the rest of the API: these answers exist to spare
    a phone call, and a student should not need an account to read them.
    Inactive rows are filtered out here rather than in the views, so an
    archived FAQ is a 404 on the detail endpoint and not merely hidden from
    the list.
    """

    serializer_class = FaqSerializer
    permission_classes = [AllowAny]
    # Each FAQ is answered with its office's code: one join, not a query per row.
    queryset = Faq.objects.filter(is_active=True).select_related("office")


class FaqListView(PublishedFaqMixin, generics.ListAPIView):
    """The published FAQs, optionally narrowed to a single office."""

    def get_queryset(self):
        queryset = super().get_queryset()
        office_code = self.request.query_params.get("office")
        if office_code is None:
            return queryset
        if office_code not in OfficeCode.values:
            raise serializers.ValidationError(
                {
                    "office": f"Unknown office. Available: {', '.join(OfficeCode.values)}."
                }
            )
        return queryset.filter(office__code=office_code)


class FaqDetailView(PublishedFaqMixin, generics.RetrieveAPIView):
    """A single published FAQ."""


class QuestionCreateView(APIView):
    """Ask a question about an office and get the best-matching FAQ (US2a, US2b).

    Students only, unlike reading the FAQs: a question is recorded, and the
    records are there to show what students need that the FAQs do not cover.
    The ``lang`` parameter is the language of the question, so it also picks
    the stemming the search uses.
    """

    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request):
        language = requested_language(request)
        serializer = QuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inquiry = ask_question(
            office=serializer.validated_data["office"],
            text=serializer.validated_data["question"],
            language=language,
        )
        return Response(InquirySerializer(inquiry).data, status=status.HTTP_201_CREATED)


class QuestionResolveView(APIView):
    """Say that the suggested answer resolved the question (US2c).

    Not scoped to the caller, since an inquiry records no user: the UUID the
    student was given when asking is what lets them close it.
    """

    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, pk):
        inquiry = get_object_or_404(
            Inquiry.objects.select_related("office", "matched_faq__office"), pk=pk
        )
        try:
            resolve_inquiry(inquiry)
        except InquiryError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InquirySerializer(inquiry).data, status=status.HTTP_200_OK)
