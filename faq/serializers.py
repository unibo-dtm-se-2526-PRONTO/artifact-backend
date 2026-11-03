from rest_framework import serializers

from offices.models import Office
from pronto.enums import OfficeCode
from pronto.i18n import TranslatedField

from .models import Faq, Inquiry


class FaqSerializer(serializers.ModelSerializer):
    """One published question and answer, in the language the caller asked for."""

    office_code = serializers.CharField(source="office.code", read_only=True)
    question = TranslatedField()
    answer = TranslatedField()

    class Meta:
        model = Faq
        fields = ["id", "office_code", "question", "answer"]
        read_only_fields = fields


QUESTION_MAX_LENGTH = 1000


class QuestionSerializer(serializers.Serializer):
    """A free-text question and, optionally, an office code."""

    office = serializers.ChoiceField(choices=OfficeCode.choices, required=False)
    question = serializers.CharField(max_length=QUESTION_MAX_LENGTH)

    def validate_office(self, code):
        office = Office.objects.filter(code=code).first()
        if office is None:
            self.fields["office"].fail("invalid_choice", input=code)
        return office


class SuggestedFaqSerializer(serializers.ModelSerializer):
    """The suggested FAQ, in the language of the question."""

    question = TranslatedField()
    answer = TranslatedField()

    class Meta:
        model = Faq
        fields = ["id", "question", "answer"]
        read_only_fields = fields


class InquirySerializer(serializers.ModelSerializer):
    """A question and the FAQ found for it; ``match`` is null if none.

    ``office_reassigned`` says the answer belongs to another office.
    """

    office = serializers.CharField(
        source="office.code", read_only=True, allow_null=True
    )
    match = serializers.SerializerMethodField()
    office_reassigned = serializers.SerializerMethodField()

    class Meta:
        model = Inquiry
        fields = ["id", "office", "language", "match", "office_reassigned", "resolved"]
        read_only_fields = fields

    def get_match(self, inquiry):
        faq = inquiry.matched_faq
        if faq is None:
            return None
        return {
            "faq": SuggestedFaqSerializer(
                faq, context={"language": inquiry.language}
            ).data,
            "office": faq.office.code,
            "score": inquiry.score,
        }

    def get_office_reassigned(self, inquiry):
        faq = inquiry.matched_faq
        return faq is not None and faq.office_id != inquiry.office_id
