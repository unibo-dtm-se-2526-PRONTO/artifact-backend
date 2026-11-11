"""The FAQs bundled with PRONTO, used by ``seed_faqs``.

``data/faqs.json`` holds the helpdesk spreadsheet as ``import_faqs`` reads it,
already anonymised: one entry per FAQ, with its office code and both languages.
"""

import json
from pathlib import Path

FAQS_FILE = Path(__file__).parent / "data" / "faqs.json"


def load_faqs():
    return json.loads(FAQS_FILE.read_text(encoding="utf-8"))
