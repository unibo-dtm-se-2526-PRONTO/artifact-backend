"""Answering in the language the caller asked for.

Value objects only, like `pronto.enums`: `booking` and `faq` both store their
texts once per language, and both have to pick one at response time, but
neither may depend on the other.

The convention is a naming one — a translated field ``name`` is stored as
``name_it`` and ``name_en`` — so a model opts in simply by naming its columns
that way.
"""

from rest_framework import serializers

LANGUAGES = ("it", "en")
DEFAULT_LANGUAGE = "it"
LANGUAGE_PARAM = "lang"


def requested_language(request):
    """The language asked for in the query string, Italian when unspecified.

    An unsupported code is an error rather than a silent fallback: answering a
    question in a language the caller cannot read is worse than saying no.
    """
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
    """Serializes ``<name>_it`` or ``<name>_en`` under the neutral key ``name``.

    The per-language columns stay out of the payload entirely: the client asked
    a question in one language and gets one answer back, instead of having to
    know the naming convention and choose for itself.
    """

    def __init__(self, **kwargs):
        kwargs["read_only"] = True
        super().__init__(**kwargs)

    def get_attribute(self, instance):
        # The whole instance, not one attribute: which attribute to read is
        # only known once the request language is resolved, below.
        return instance

    def to_representation(self, instance):
        language = self.context.get("language", DEFAULT_LANGUAGE)
        return getattr(instance, f"{self.field_name}_{language}")


class LanguageAwareMixin:
    """Puts the requested language where `TranslatedField` can find it.

    Resolving it here also means an unsupported code is rejected once per
    request, before any row is serialized.
    """

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["language"] = requested_language(self.request)
        return context
