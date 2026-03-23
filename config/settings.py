"""Configurações e prompts para o pipeline de tagging."""

from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
ENRICHED_DIR = DATA_DIR / "enriched"
VALIDATION_DIR = DATA_DIR / "validation"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"
INDEX_DIR = DATA_DIR / "index"
REPORTS_DIR = DATA_DIR / "reports"
LOOKUP_DIR = DATA_DIR / "lookup"

# Gemini models
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_EMBEDDING_MODEL = "gemini-embedding-2-preview"  # Multimodal: text + image in same space

# Rate limiting
MAX_CONCURRENT_REQUESTS = 5  # Free tier: 10 RPM, keep conservative
EMBEDDING_BATCH_SIZE = 6  # Max images per embedding request
MAX_OUTPUT_TOKENS = 2048  # Increased for description field
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2.0  # seconds

# Embedding config
EMBEDDING_DIMS = 768  # MRL: 128-3072. 768 = good quality/storage tradeoff for 16K images

# Description config
DESCRIPTION_MAX_CHARS = 600

# HuggingFace dataset
HF_DATASET_ID = "Iuryeng/bible-images-dataset"

# Gazetteers dataset path (default, can be overridden via CLI)
GAZETTEERS_PATH = Path("C:/Users/Iury Coelho/Desktop/bible-gazetteers-dataset")

# Schema version
SCHEMA_VERSION = "2.0"
GAZETTEER_VERSION = "3.0.0"

# ---------------------------------------------------------------------------
# Tagging prompt — v2 with visual description + character types
# ---------------------------------------------------------------------------

TAGGING_SYSTEM_INSTRUCTION = """\
You are a biblical art expert specializing in identifying biblical scenes, \
characters, and symbolism in Western religious paintings. You have deep knowledge \
of both Old and New Testament iconography across all artistic periods."""

TAGGING_PROMPT = """\
Analyze this painting and identify the biblical content.

Context:
- Title: {title}
- Artist: {artist}
- Year: {year}
- Existing tags: {tags}

Rules:
1. Use OSIS book abbreviations: GEN, EXO, LEV, NUM, DEU, JOS, JDG, RUT, 1SA, 2SA, \
1KI, 2KI, 1CH, 2CH, EZR, NEH, EST, JOB, PSA, PRO, ECC, SNG, ISA, JER, LAM, EZK, \
DAN, HOS, JOL, AMO, OBA, JON, MIC, NAM, HAB, ZEP, HAG, ZEC, MAL, MAT, MRK, LUK, \
JHN, ACT, ROM, 1CO, 2CO, GAL, EPH, PHP, COL, 1TH, 2TH, 1TI, 2TI, TIT, PHM, HEB, \
JAS, 1PE, 2PE, 1JN, 2JN, 3JN, JUD, REV
2. If the painting is not clearly biblical, set confidence below 0.3.
3. Prefer specific verse ranges over entire chapters.
4. List ALL identifiable characters, not just the main one.
5. Use English canonical names for characters.
6. For each character, classify as PERSON, GROUP, ANGEL, or DEITY.
7. For the description: describe ONLY what you see in the image in plain language \
(max 600 characters). Describe people, objects, actions, setting, colors, and atmosphere. \
Do NOT mention art style, artist, technique, or period. Write as if describing the scene \
to someone who cannot see it."""

# ---------------------------------------------------------------------------
# Structured output schema v2 — enforced via Gemini response_schema
# ---------------------------------------------------------------------------

TAG_SCHEMA = {
    "type": "object",
    "properties": {
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Character name in English (e.g. 'Moses', 'Jesus', 'Mary')",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["PERSON", "GROUP", "ANGEL", "DEITY", "OTHER"],
                        "description": "Character classification",
                    },
                },
                "required": ["name", "type"],
            },
            "description": "Biblical figures depicted with type classification",
        },
        "event": {
            "type": "string",
            "description": "Biblical event or scene (e.g. 'Binding of Isaac', 'Last Supper')",
        },
        "osis_refs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Scripture references in OSIS format (e.g. 'GEN.22.1-19')",
        },
        "testament": {
            "type": "string",
            "enum": ["OT", "NT", "BOTH", "UNKNOWN"],
        },
        "themes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Theological themes (e.g. 'faith', 'sacrifice', 'redemption')",
        },
        "symbols": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Visual biblical symbols (e.g. 'lamb', 'cross', 'dove')",
        },
        "description": {
            "type": "string",
            "description": "Visual description of what is seen in the image (max 600 chars). "
            "Describe people, objects, actions, setting. No art style or artist mentions.",
        },
        "confidence": {
            "type": "number",
            "description": "Confidence in biblical identification (0.0 to 1.0)",
        },
    },
    "required": [
        "characters", "event", "osis_refs", "testament",
        "themes", "symbols", "description", "confidence",
    ],
}
