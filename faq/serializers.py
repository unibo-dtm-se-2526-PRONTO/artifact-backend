from rest_framework import serializers

from offices.models import Office
from pronto.enums import OfficeCode
from pronto.i18n import TranslatedField

from .models import Faq, Inquiry


class FaqSerializer(serializers.ModelSerializer):
    """One published question and answer, in the language the caller asked for."""

    # The office by its code, under the name the API has always used for it.
    office_code = serializers.CharField(source="office.code", read_only=True)
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
    """What a student sends to ask: a free-text question and, optionally, an
    office, by its code. Without one, every office is searched.

    Any office will do, not only those taking bookings: a question can be
    answered even where no one can be booked. The code is checked against
    `OfficeCode` first, so an unknown one is refused with the error a choice
    field gives; a valid code whose office does not exist in this database
    gets the same answer, as there is nothing to file the question under.
    """

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
    """A question as the student sees it: what was asked, and what was found.

    ``match`` is null when no FAQ was relevant enough; otherwise its ``office``
    is the office the answer belongs to, and ``office_reassigned`` flags that
    it is not the one the student chose, so the client can offer to book with
    the right office. Texts are in the language the question was asked in,
    whatever the request that reads it back.
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
