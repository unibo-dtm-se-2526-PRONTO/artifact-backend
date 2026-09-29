from rest_framework import serializers

from pronto.enums import OfficeCode
from pronto.i18n import TranslatedField

from .models import Faq, Inquiry


class FaqSerializer(serializers.ModelSerializer):
    """One published question and answer, in the language the caller asked for."""

    question = TranslatedField()
    answer = TranslatedField()

    class Meta:
        model = Faq
        fields = ["id", "office_code", "question", "answer"]
        read_only_fields = fields


# Longer than any question a student types into a form, short enough that the
# search never has to rank an essay.
QUESTION_MAX_LENGTH = 1000


class QuestionSerializer(serializers.Serializer):
    """What a student sends to ask: an office and a free-text question.

    The office is checked against `OfficeCode`, as the FAQ list does, rather
    than against the offices taking bookings: the FAQ slice does not know about
    those, and a question can be answered even where no one can be booked.
    """

    office = serializers.ChoiceField(choices=OfficeCode.choices)
    question = serializers.CharField(max_length=QUESTION_MAX_LENGTH)


class SuggestedFaqSerializer(serializers.ModelSerializer):
    """The suggested FAQ, in the language of the question."""

    question = TranslatedField()
    answer = TranslatedField()

    class Meta:
        model = Faq
        fields = ["id", "question", "answer"]
        read_only_fields = fields


class InquirySerializer(serializers.ModelSerializer):
    """A question as the student sees it: what was asked, and what was found.

    ``match`` is null when no FAQ was relevant enough; otherwise its ``office``
    is the office the answer belongs to, and ``office_reassigned`` flags that
    it is not the one the student chose, so the client can offer to book with
    the right office. Texts are in the language the question was asked in,
    whatever the request that reads it back.
    """

    office = serializers.CharField(source="office_code", read_only=True)
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
            "office": faq.office_code,
            "score": inquiry.score,
        }

    def get_office_reassigned(self, inquiry):
        faq = inquiry.matched_faq
        return faq is not None and faq.office_code != inquiry.office_code
