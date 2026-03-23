"""Configurações e prompts para o pipeline de tagging."""

from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
VALIDATION_DIR = DATA_DIR / "validation"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"

# Gemini
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_EMBEDDING_MODEL = "gemini-embedding-exp-03-07"
MAX_CONCURRENT_REQUESTS = 10
RETRY_ATTEMPTS = 3
RETRY_DELAY = 1.0  # seconds

# Tagging prompt
TAGGING_PROMPT = """\
You are a biblical art expert. Analyze this painting and return a JSON object with:

{
  "characters": [],
  "event": "",
  "osis_refs": [],
  "testament": "",
  "themes": [],
  "symbols": [],
  "confidence": 0.0
}

Field definitions:
- characters: Biblical figures depicted (English canonical names, e.g. "Abraham", "Moses", "Jesus", "Mary")
- event: The biblical event or scene shown (e.g. "Binding of Isaac", "Last Supper", "Annunciation")
- osis_refs: Scripture references in OSIS format (e.g. ["GEN.22.1-19", "HEB.11.17-19"])
- testament: "OT" for Old Testament, "NT" for New Testament, "BOTH" if mixed, "UNKNOWN" if unclear
- themes: Theological themes (e.g. ["faith", "sacrifice", "obedience", "covenant"])
- symbols: Visual biblical symbols present (e.g. ["lamb", "cross", "dove", "crown of thorns"])
- confidence: Your confidence in the identification (0.0 to 1.0)

Additional context about this painting:
- Title: {title}
- Artist: {artist}
- Year: {year}
- Existing tags: {tags}

Rules:
1. Return ONLY valid JSON, no markdown or explanation.
2. Use OSIS book abbreviations: GEN, EXO, LEV, NUM, DEU, JOS, JDG, RUT, 1SA, 2SA, 1KI, 2KI, 1CH, 2CH, EZR, NEH, EST, JOB, PSA, PRO, ECC, SNG, ISA, JER, LAM, EZK, DAN, HOS, JOL, AMO, OBA, JON, MIC, NAM, HAB, ZEP, HAG, ZEC, MAL, MAT, MRK, LUK, JHN, ACT, ROM, 1CO, 2CO, GAL, EPH, PHP, COL, 1TH, 2TH, 1TI, 2TI, TIT, PHM, HEB, JAS, 1PE, 2PE, 1JN, 2JN, 3JN, JUD, REV
3. If the painting is not clearly biblical, set confidence below 0.3 and fill what you can.
4. Prefer specific verse ranges over entire chapters.
5. List ALL identifiable characters, not just the main one.
"""

# Output schema for validation
TAG_SCHEMA = {
    "type": "object",
    "properties": {
        "characters": {"type": "array", "items": {"type": "string"}},
        "event": {"type": "string"},
        "osis_refs": {"type": "array", "items": {"type": "string"}},
        "testament": {"type": "string", "enum": ["OT", "NT", "BOTH", "UNKNOWN"]},
        "themes": {"type": "array", "items": {"type": "string"}},
        "symbols": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": ["characters", "event", "osis_refs", "testament", "themes", "symbols", "confidence"],
}
