from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny

from pronto.enums import OfficeCode
from pronto.i18n import LanguageAwareMixin

from .models import Faq
from .serializers import FaqSerializer


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
    queryset = Faq.objects.filter(is_active=True)


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
        return queryset.filter(office_code=office_code)


class FaqDetailView(PublishedFaqMixin, generics.RetrieveAPIView):
    """A single published FAQ."""
