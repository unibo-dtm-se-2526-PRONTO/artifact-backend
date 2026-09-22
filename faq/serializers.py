from rest_framework import serializers

from pronto.i18n import TranslatedField

from .models import Faq


class FaqSerializer(serializers.ModelSerializer):
    """One published question and answer, in the language the caller asked for."""

    question = TranslatedField()
    answer = TranslatedField()

    class Meta:
        model = Faq
        fields = ["id", "office_code", "question", "answer"]
        read_only_fields = fields
