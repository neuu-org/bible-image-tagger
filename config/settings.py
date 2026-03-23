"""Configurações e prompts para o pipeline de tagging."""

from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
VALIDATION_DIR = DATA_DIR / "validation"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"
INDEX_DIR = DATA_DIR / "index"

# Gemini models
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_EMBEDDING_MODEL = "gemini-embedding-2-preview"  # Multimodal: text + image in same space

# Rate limiting
MAX_CONCURRENT_REQUESTS = 5  # Free tier: 10 RPM, keep conservative
EMBEDDING_BATCH_SIZE = 6  # Max images per embedding request
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2.0  # seconds

# Embedding config
EMBEDDING_DIMS = 768  # MRL: 128-3072. 768 = good quality/storage tradeoff for 16K images

# HuggingFace dataset
HF_DATASET_ID = "Iuryeng/bible-images-dataset"

# Tagging prompt — used as system instruction + user prompt
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
5. Use English canonical names for characters."""

# Structured output schema — enforced via Gemini response_schema (constrained decoding)
TAG_SCHEMA = {
    "type": "object",
    "properties": {
        "characters": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Biblical figures depicted (e.g. 'Abraham', 'Moses', 'Jesus', 'Mary')",
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
        "confidence": {
            "type": "number",
            "description": "Confidence in identification (0.0 to 1.0)",
        },
    },
    "required": ["characters", "event", "osis_refs", "testament", "themes", "symbols", "confidence"],
}
