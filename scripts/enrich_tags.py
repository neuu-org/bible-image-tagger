"""Enrich raw Gemini tags with gazetteer canonical IDs and symbolic meanings.

Takes raw output from tag_images.py, matches against bible-gazetteers-dataset,
and produces enriched JSON with canonical_ids, symbolic_meaning, and discovered entities.

Supports both v1 (characters as strings) and v2 (characters as objects) input.

Usage:
    python scripts/enrich_tags.py
    python scripts/enrich_tags.py --tags data/output/ --output data/enriched/
    python scripts/enrich_tags.py --tags data/output/ --gazetteers /path/to/gazetteers
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import (
    DESCRIPTION_MAX_CHARS,
    ENRICHED_DIR,
    GAZETTEERS_PATH,
    GAZETTEER_VERSION,
    LOOKUP_DIR,
    OUTPUT_DIR,
    SCHEMA_VERSION,
)
from scripts.build_lookup import GazetteerMatcher, build_and_save, load_index


def normalize_character(raw: str | dict) -> dict:
    """Normalize a character entry from v1 (string) or v2 (object) format."""
    if isinstance(raw, str):
        return {"name": raw, "type": "UNKNOWN"}
    return {"name": raw.get("name", ""), "type": raw.get("type", "UNKNOWN")}


def truncate_description(text: str, max_chars: int = DESCRIPTION_MAX_CHARS) -> str:
    """Truncate description at the last complete sentence within max_chars."""
    if not text or len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    # Find last sentence boundary
    for sep in [". ", "! ", "? "]:
        last_idx = truncated.rfind(sep)
        if last_idx > max_chars * 0.5:  # Only if we keep at least 50%
            return truncated[: last_idx + 1].strip()

    # Fallback: cut at last space
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.5:
        return truncated[:last_space].strip() + "..."

    return truncated.strip() + "..."


def suggest_canonical_id(name: str, entity_type: str) -> str:
    """Generate a suggested canonical_id following naming conventions."""
    type_to_prefix = {
        "PERSON": "PER",
        "GROUP": "GRP",
        "ANGEL": "ANG",
        "DEITY": "DIV",
        "PLACE": "PLC",
        "EVENT": "EVT",
        "OBJECT": "OBJ",
        "OTHER": "ENT",
        "UNKNOWN": "ENT",
    }
    prefix = type_to_prefix.get(entity_type, "ENT")

    # Generate slug: lowercase, replace spaces with _, remove non-alphanum
    slug = name.lower().strip()
    slug = re.sub(r"[''`]", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")

    return f"{prefix}:{slug}"


def enrich_single_tag(tag: dict, matcher: GazetteerMatcher) -> dict:
    """Enrich a single tag file with gazetteer data."""
    enriched = {}
    entities_discovered = []

    # --- Characters ---
    enriched_characters = []
    for raw_char in tag.get("characters", []):
        char = normalize_character(raw_char)
        name = char["name"]
        char_type = char["type"]

        if not name:
            continue

        match = matcher.match_entity(name, type_hint=char_type)
        entry = {
            "name": name,
            "canonical_id": match.get("canonical_id"),
            "type": match.get("type") or char_type,
            "match_confidence": match.get("match_confidence", "unmatched"),
        }
        enriched_characters.append(entry)

        if not match.get("canonical_id"):
            entities_discovered.append({
                "name": name,
                "suggested_type": char_type,
                "suggested_canonical_id": suggest_canonical_id(name, char_type),
                "context": f"Character in: {tag.get('event', '')}",
            })

    enriched["characters"] = enriched_characters

    # --- Event ---
    event_str = tag.get("event", "")
    if event_str:
        event_match = matcher.match_entity(event_str, type_hint="EVENT")
        enriched["event"] = {
            "name": event_str,
            "canonical_id": event_match.get("canonical_id"),
            "type": event_match.get("type"),
            "match_confidence": event_match.get("match_confidence", "unmatched"),
        }
        if not event_match.get("canonical_id") and event_str.lower() not in (
            "not a biblical scene", "unknown", ""
        ):
            entities_discovered.append({
                "name": event_str,
                "suggested_type": "EVENT",
                "suggested_canonical_id": suggest_canonical_id(event_str, "EVENT"),
                "context": f"Event depicted in image {tag.get('_meta', {}).get('key', '?')}",
            })
    else:
        enriched["event"] = {"name": "", "canonical_id": None, "type": None, "match_confidence": "unmatched"}

    # --- OSIS refs (pass through) ---
    enriched["osis_refs"] = tag.get("osis_refs", [])

    # --- Testament (pass through) ---
    enriched["testament"] = tag.get("testament", "UNKNOWN")

    # --- Themes (pass through) ---
    enriched["themes"] = tag.get("themes", [])

    # --- Symbols ---
    enriched_symbols = []
    for sym_name in tag.get("symbols", []):
        if not sym_name:
            continue

        match = matcher.match_symbol(sym_name)
        entry = {
            "name": sym_name,
            "canonical_id": match.get("canonical_id"),
            "type": match.get("type"),
            "symbolic_meaning": match.get("symbolic_meaning"),
            "match_confidence": match.get("match_confidence", "unmatched"),
        }
        enriched_symbols.append(entry)

        if not match.get("canonical_id"):
            entities_discovered.append({
                "name": sym_name,
                "suggested_type": "SYMBOL",
                "suggested_canonical_id": suggest_canonical_id(sym_name, "OBJECT"),
                "context": f"Symbol in: {tag.get('event', '')}",
            })

    enriched["symbols"] = enriched_symbols

    # --- Description (truncate if needed) ---
    description = tag.get("description", "")
    enriched["description"] = truncate_description(description)

    # --- Confidence (pass through) ---
    enriched["confidence"] = tag.get("confidence", 0.0)

    # --- Discovered entities ---
    enriched["entities_discovered"] = entities_discovered

    # --- Meta ---
    original_meta = tag.get("_meta", {})
    enriched["_meta"] = {
        **original_meta,
        "schema_version": SCHEMA_VERSION,
        "gazetteer_version": GAZETTEER_VERSION,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }

    return enriched


def run_enrichment(
    tags_dir: Path,
    output_dir: Path,
    index_path: Path | None = None,
    gazetteers_path: Path | None = None,
    skip_existing: bool = True,
):
    """Enrich all tag files in a directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load or build index
    default_index = LOOKUP_DIR / "gazetteer_index.json"
    if index_path and index_path.exists():
        print(f"Loading index from: {index_path}")
        index = load_index(index_path)
    elif default_index.exists():
        print(f"Loading index from: {default_index}")
        index = load_index(default_index)
    else:
        gaz_path = gazetteers_path or GAZETTEERS_PATH
        print(f"Index not found, building from: {gaz_path}")
        build_and_save(gaz_path, LOOKUP_DIR)
        index = load_index(default_index)

    matcher = GazetteerMatcher(index)

    # Process tags
    tag_files = sorted(tags_dir.glob("*.json"))

    if skip_existing:
        existing = {p.stem for p in output_dir.glob("*.json")}
        tag_files = [t for t in tag_files if t.stem not in existing]

    if not tag_files:
        print("Nothing to enrich.")
        return

    print(f"Enriching {len(tag_files)} tags...")

    stats = {"total": 0, "matched": 0, "unmatched": 0, "discovered": 0}

    for tag_file in tag_files:
        with open(tag_file, encoding="utf-8") as f:
            tag = json.load(f)

        enriched = enrich_single_tag(tag, matcher)

        # Update stats
        stats["total"] += 1
        for char in enriched["characters"]:
            if char["canonical_id"]:
                stats["matched"] += 1
            else:
                stats["unmatched"] += 1
        for sym in enriched["symbols"]:
            if sym["canonical_id"]:
                stats["matched"] += 1
            else:
                stats["unmatched"] += 1
        if enriched["event"]["canonical_id"]:
            stats["matched"] += 1
        elif enriched["event"]["name"]:
            stats["unmatched"] += 1
        stats["discovered"] += len(enriched["entities_discovered"])

        # Save
        out_path = output_dir / f"{tag_file.stem}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)

    total_mentions = stats["matched"] + stats["unmatched"]
    match_rate = stats["matched"] / total_mentions * 100 if total_mentions else 0

    print(f"\nDone! {stats['total']} tags enriched")
    print(f"  Matched: {stats['matched']}/{total_mentions} ({match_rate:.1f}%)")
    print(f"  Unmatched: {stats['unmatched']}")
    print(f"  New entities discovered: {stats['discovered']}")
    print(f"  Output: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Enrich tags with gazetteer canonical IDs")
    parser.add_argument("--tags", type=Path, default=OUTPUT_DIR, help="Input tags directory")
    parser.add_argument("--output", type=Path, default=ENRICHED_DIR, help="Output enriched directory")
    parser.add_argument("--gazetteers", type=Path, default=GAZETTEERS_PATH)
    parser.add_argument("--index", type=Path, default=None, help="Pre-built index path")
    parser.add_argument("--no-skip", action="store_true")
    args = parser.parse_args()

    run_enrichment(args.tags, args.output, args.index, args.gazetteers, not args.no_skip)


if __name__ == "__main__":
    main()
