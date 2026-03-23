"""Build a fast lookup index from the bible-gazetteers-dataset.

Loads all entity and symbol files, builds name→canonical_id dictionaries
with alias expansion and priority scores for disambiguation.

Usage:
    python scripts/build_lookup.py
    python scripts/build_lookup.py --gazetteers /path/to/bible-gazetteers-dataset
    python scripts/build_lookup.py --output data/lookup/gazetteer_index.json
"""

import argparse
import json
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import GAZETTEERS_PATH, GAZETTEER_VERSION, LOOKUP_DIR
from config.translations import (
    CHARACTER_EN_TO_PT,
    EVENT_EN_TO_PT,
    SYMBOL_EN_TO_PT,
)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    """Normalize text for matching: lowercase, strip accents, strip whitespace."""
    text = text.lower().strip()
    # Remove accents: é→e, ã→a, etc.
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Gazetteer loading
# ---------------------------------------------------------------------------

def load_entities(gazetteers_path: Path) -> list[dict]:
    """Load all entity entries from all entity type files."""
    entities_dir = gazetteers_path / "data" / "pt" / "entities"
    all_entities = []

    if not entities_dir.exists():
        print(f"  WARNING: entities dir not found: {entities_dir}")
        return all_entities

    for json_file in sorted(entities_dir.glob("*.json")):
        with open(json_file, encoding="utf-8") as f:
            entries = json.load(f)
        for entry in entries:
            entry["_source_file"] = json_file.stem
        all_entities.extend(entries)

    return all_entities


def load_symbols(gazetteers_path: Path) -> list[dict]:
    """Load all symbol entries from all symbol type files."""
    symbols_dir = gazetteers_path / "data" / "pt" / "symbols"
    all_symbols = []

    if not symbols_dir.exists():
        print(f"  WARNING: symbols dir not found: {symbols_dir}")
        return all_symbols

    for json_file in sorted(symbols_dir.glob("*.json")):
        with open(json_file, encoding="utf-8") as f:
            entries = json.load(f)
        for entry in entries:
            entry["_source_file"] = json_file.stem
        all_symbols.extend(entries)

    return all_symbols


def load_scores(gazetteers_path: Path) -> dict[str, float]:
    """Load priority scores from metrics files."""
    scores = {}
    metrics_dir = gazetteers_path / "data" / "pt" / "metrics"

    for filename in ["entity_scores.json", "symbol_scores.json"]:
        scores_file = metrics_dir / filename
        if scores_file.exists():
            with open(scores_file, encoding="utf-8") as f:
                data = json.load(f)
            # Format: {canonical_id: {boost, priority, total_score, ...}}
            if isinstance(data, dict):
                for cid, metrics in data.items():
                    if isinstance(metrics, dict):
                        scores[cid] = metrics.get("total_score", metrics.get("priority", 0))
                    else:
                        scores[cid] = float(metrics)
            elif isinstance(data, list):
                for entry in data:
                    cid = entry.get("canonical_id", "")
                    if cid:
                        scores[cid] = entry.get("total_score", 0)

    return scores


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------

# Map entity namespace prefix to type hint keywords
PREFIX_TO_HINT = {
    "PER": "PERSON",
    "PLC": "PLACE",
    "PLA": "PLACE",
    "CPT": "CONCEPT",
    "OBJ": "OBJECT",
    "GRP": "GROUP",
    "EVT": "EVENT",
    "CRE": "CREATURE",
    "RIT": "RITUAL",
    "PLT": "PLANT",
    "LIT": "LITERARY_WORK",
    "LFM": "LITERARY_FORM",
    "DIV": "DEITY",
    "ANG": "ANGEL",
    # Symbol prefixes
    "NAT": "NATURAL",
    "ACT": "ACTION",
    "COL": "COLOR",
    "TYP": "PERSON_TYPE",
    "NUM": "NUMBER",
    "MAT": "MATERIAL",
    "FOO": "FOOD",
    "CEL": "CELESTIAL",
    "SYM": "SYMBOL",
}

HINT_TO_PREFIXES = {}
for prefix, hint in PREFIX_TO_HINT.items():
    HINT_TO_PREFIXES.setdefault(hint, []).append(prefix)


def build_index(
    entities: list[dict],
    symbols: list[dict],
    scores: dict[str, float],
) -> dict:
    """Build the complete lookup index."""
    # name_normalized → list of {canonical_id, name, type, score, kind}
    entity_by_name: dict[str, list[dict]] = {}
    symbol_by_name: dict[str, list[dict]] = {}
    entity_by_id: dict[str, dict] = {}
    symbol_by_id: dict[str, dict] = {}

    def add_to_lookup(
        lookup: dict[str, list[dict]],
        key: str,
        record: dict,
    ):
        norm = normalize(key)
        if norm:
            lookup.setdefault(norm, []).append(record)

    # Index entities
    for ent in entities:
        cid = ent.get("canonical_id", "")
        name = ent.get("name", "")
        etype = ent.get("type", "")
        score = scores.get(cid, 0)

        record = {
            "canonical_id": cid,
            "name": name,
            "type": etype,
            "score": score,
            "kind": "entity",
        }

        entity_by_id[cid] = ent

        # Index by name
        add_to_lookup(entity_by_name, name, record)

        # Index by aliases
        for alias in ent.get("aliases", []):
            add_to_lookup(entity_by_name, alias, record)

    # Index symbols
    for sym in symbols:
        cid = sym.get("canonical_id", "")
        name = sym.get("name", "")
        stype = sym.get("type", "")
        score = scores.get(cid, 0)

        record = {
            "canonical_id": cid,
            "name": name,
            "type": stype,
            "score": score,
            "kind": "symbol",
            "symbolic_meaning": sym.get("symbolic_meaning", []),
        }

        symbol_by_id[cid] = sym

        # Index by name
        add_to_lookup(symbol_by_name, name, record)

        # Index by aliases
        for alias in sym.get("aliases", []):
            add_to_lookup(symbol_by_name, alias, record)

    return {
        "entity_by_name": entity_by_name,
        "symbol_by_name": symbol_by_name,
        "entity_by_id": {k: _serialize_entry(v) for k, v in entity_by_id.items()},
        "symbol_by_id": {k: _serialize_entry(v) for k, v in symbol_by_id.items()},
        "translation_tables": {
            "symbols": SYMBOL_EN_TO_PT,
            "events": EVENT_EN_TO_PT,
            "characters": CHARACTER_EN_TO_PT,
        },
        "meta": {
            "total_entities": len(entities),
            "total_symbols": len(symbols),
            "total_entity_names": sum(len(v) for v in entity_by_name.values()),
            "total_symbol_names": sum(len(v) for v in symbol_by_name.values()),
            "gazetteer_version": GAZETTEER_VERSION,
        },
    }


def _serialize_entry(entry: dict) -> dict:
    """Serialize a gazetteer entry for the index (drop _source_file)."""
    return {k: v for k, v in entry.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Matching functions (used by enrich_tags.py)
# ---------------------------------------------------------------------------

class GazetteerMatcher:
    """Match free-text names to gazetteer canonical IDs."""

    def __init__(self, index: dict):
        self.entity_by_name = index["entity_by_name"]
        self.symbol_by_name = index["symbol_by_name"]
        self.entity_by_id = index["entity_by_id"]
        self.symbol_by_id = index["symbol_by_id"]
        self.translations = index["translation_tables"]

    def match_entity(
        self,
        name: str,
        type_hint: str | None = None,
    ) -> dict:
        """Match a character/event name to a gazetteer entity.

        Returns: {canonical_id, name, type, score, match_confidence}
        """
        norm = normalize(name)

        # 1. Exact match on name/alias
        candidates = self.entity_by_name.get(norm, [])
        if candidates:
            best = self._pick_best(candidates, type_hint)
            return {**best, "match_confidence": "exact"}

        # 2. Translation table → re-match
        translated = self.translations["characters"].get(norm)
        if not translated:
            translated = self.translations["events"].get(norm)
        if translated:
            candidates = self.entity_by_name.get(normalize(translated), [])
            if candidates:
                best = self._pick_best(candidates, type_hint)
                return {**best, "match_confidence": "translation"}

        # 3. Fuzzy match
        best_ratio = 0.0
        best_match = None
        for key, entries in self.entity_by_name.items():
            ratio = SequenceMatcher(None, norm, key).ratio()
            if ratio > best_ratio and ratio >= 0.85:
                best_ratio = ratio
                best_match = self._pick_best(entries, type_hint)

        if best_match:
            return {**best_match, "match_confidence": "fuzzy"}

        # 4. No match
        return {
            "canonical_id": None,
            "name": name,
            "type": None,
            "score": 0,
            "match_confidence": "unmatched",
        }

    def match_symbol(self, name: str) -> dict:
        """Match a symbol name to a gazetteer symbol.

        Returns: {canonical_id, name, type, symbolic_meaning, score, match_confidence}
        """
        norm = normalize(name)

        # 1. Exact match
        candidates = self.symbol_by_name.get(norm, [])
        if candidates:
            best = self._pick_best(candidates)
            return {**best, "match_confidence": "exact"}

        # 2. Translation table → re-match
        translated = self.translations["symbols"].get(norm)
        if translated:
            candidates = self.symbol_by_name.get(normalize(translated), [])
            if candidates:
                best = self._pick_best(candidates)
                return {**best, "match_confidence": "translation"}

        # 3. Fuzzy match
        best_ratio = 0.0
        best_match = None
        for key, entries in self.symbol_by_name.items():
            ratio = SequenceMatcher(None, norm, key).ratio()
            if ratio > best_ratio and ratio >= 0.85:
                best_ratio = ratio
                best_match = self._pick_best(entries)

        if best_match:
            return {**best_match, "match_confidence": "fuzzy"}

        # 4. Also check entity index (some symbols are also entities, e.g. "ark")
        entity_match = self.match_entity(name)
        if entity_match["canonical_id"]:
            return {
                **entity_match,
                "symbolic_meaning": [],
                "kind": "entity_as_symbol",
            }

        # 5. No match
        return {
            "canonical_id": None,
            "name": name,
            "type": None,
            "symbolic_meaning": None,
            "score": 0,
            "match_confidence": "unmatched",
        }

    def _pick_best(
        self,
        candidates: list[dict],
        type_hint: str | None = None,
    ) -> dict:
        """Pick the best candidate, preferring type_hint match and highest score."""
        if not candidates:
            return {}

        if type_hint and len(candidates) > 1:
            # Filter by type hint
            hint_prefixes = HINT_TO_PREFIXES.get(type_hint, [])
            type_filtered = [
                c for c in candidates
                if any(c.get("canonical_id", "").startswith(p + ":") for p in hint_prefixes)
            ]
            if type_filtered:
                candidates = type_filtered

        # Sort by score descending
        return max(candidates, key=lambda c: c.get("score", 0))


# ---------------------------------------------------------------------------
# CLI: build and save index
# ---------------------------------------------------------------------------

def build_and_save(gazetteers_path: Path, output_dir: Path):
    """Build the lookup index and save to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading gazetteers from: {gazetteers_path}")
    entities = load_entities(gazetteers_path)
    print(f"  Entities: {len(entities)}")

    symbols = load_symbols(gazetteers_path)
    print(f"  Symbols: {len(symbols)}")

    scores = load_scores(gazetteers_path)
    print(f"  Scores: {len(scores)}")

    print("Building index...")
    index = build_index(entities, symbols, scores)

    output_path = output_dir / "gazetteer_index.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    meta = index["meta"]
    print(f"\nIndex built:")
    print(f"  Entities: {meta['total_entities']} ({meta['total_entity_names']} name entries)")
    print(f"  Symbols: {meta['total_symbols']} ({meta['total_symbol_names']} name entries)")
    print(f"  Saved to: {output_path}")


def load_index(index_path: Path | None = None) -> dict:
    """Load a pre-built index from disk."""
    if index_path is None:
        index_path = LOOKUP_DIR / "gazetteer_index.json"
    with open(index_path, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Build gazetteer lookup index")
    parser.add_argument(
        "--gazetteers", type=Path, default=GAZETTEERS_PATH,
        help="Path to bible-gazetteers-dataset",
    )
    parser.add_argument(
        "--output", type=Path, default=LOOKUP_DIR,
        help="Output directory for the index",
    )
    args = parser.parse_args()

    build_and_save(args.gazetteers, args.output)


if __name__ == "__main__":
    main()
