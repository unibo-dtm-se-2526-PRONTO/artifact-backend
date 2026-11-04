"""Answer in the language the caller asked for.

A translated field ``name`` is stored as ``name_it`` and ``name_en``.
"""

from rest_framework import serializers

from pronto.enums import Language

LANGUAGES = tuple(Language.values)
DEFAULT_LANGUAGE = "it"
LANGUAGE_PARAM = "lang"


def requested_language(request):
    """The ``lang`` query parameter, Italian by default; unknown codes are a 400."""
    language = request.query_params.get(LANGUAGE_PARAM, DEFAULT_LANGUAGE)
    if language not in LANGUAGES:
        raise serializers.ValidationError(
            {
                LANGUAGE_PARAM: (
                    f"Unsupported language. Available: {', '.join(LANGUAGES)}."
                )
            }
        )
    return language


class TranslatedField(serializers.Field):
    """Serializes ``<name>_it`` or ``<name>_en`` under the key ``name``."""

    def __init__(self, **kwargs):
        kwargs["read_only"] = True
        super().__init__(**kwargs)

    def get_attribute(self, instance):
        return instance

    def to_representation(self, instance):
        language = self.context.get("language", DEFAULT_LANGUAGE)
        return getattr(instance, f"{self.field_name}_{language}")


class LanguageAwareMixin:
    """Puts the requested language in the serializer context."""

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["language"] = requested_language(self.request)
        return context
