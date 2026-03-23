"""Aggregate unmatched entities across all enriched tags and generate a discovery report.

Identifies new gazetteer candidates by frequency and context, producing a report
that can feed back into the bible-gazetteers-dataset pipeline.

Usage:
    python scripts/discovery_report.py
    python scripts/discovery_report.py --enriched data/enriched/ --output data/reports/
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import ENRICHED_DIR, REPORTS_DIR


def generate_report(enriched_dir: Path, output_dir: Path):
    """Scan all enriched tags and aggregate discovery data."""
    output_dir.mkdir(parents=True, exist_ok=True)

    enriched_files = sorted(enriched_dir.glob("*.json"))
    if not enriched_files:
        print("No enriched tags found.")
        return

    print(f"Scanning {len(enriched_files)} enriched tags...")

    # Aggregation structures
    discovered_counts: Counter = Counter()  # name → count
    discovered_types: dict[str, str] = {}  # name → suggested_type
    discovered_ids: dict[str, str] = {}  # name → suggested_canonical_id
    discovered_images: defaultdict[str, list[str]] = defaultdict(list)  # name → [image_keys]
    discovered_contexts: dict[str, str] = {}  # name → first context

    # Match statistics
    match_stats = {
        "exact": 0,
        "alias": 0,
        "translation": 0,
        "fuzzy": 0,
        "unmatched": 0,
    }
    total_character_mentions = 0
    total_symbol_mentions = 0
    total_event_mentions = 0
    total_images = 0

    top_characters: Counter = Counter()
    top_events: Counter = Counter()
    top_symbols: Counter = Counter()

    for ef in enriched_files:
        with open(ef, encoding="utf-8") as f:
            tag = json.load(f)

        total_images += 1
        image_key = tag.get("_meta", {}).get("key", ef.stem)

        # Characters
        for char in tag.get("characters", []):
            total_character_mentions += 1
            mc = char.get("match_confidence", "unmatched")
            match_stats[mc] = match_stats.get(mc, 0) + 1
            top_characters[char.get("name", "")] += 1

        # Event
        event = tag.get("event", {})
        if isinstance(event, dict) and event.get("name"):
            total_event_mentions += 1
            mc = event.get("match_confidence", "unmatched")
            match_stats[mc] = match_stats.get(mc, 0) + 1
            top_events[event["name"]] += 1

        # Symbols
        for sym in tag.get("symbols", []):
            total_symbol_mentions += 1
            mc = sym.get("match_confidence", "unmatched")
            match_stats[mc] = match_stats.get(mc, 0) + 1
            top_symbols[sym.get("name", "")] += 1

        # Discovered entities
        for disc in tag.get("entities_discovered", []):
            name = disc.get("name", "")
            if not name:
                continue
            discovered_counts[name] += 1
            discovered_types.setdefault(name, disc.get("suggested_type", "UNKNOWN"))
            discovered_ids.setdefault(name, disc.get("suggested_canonical_id", ""))
            discovered_images[name].append(image_key)
            discovered_contexts.setdefault(name, disc.get("context", ""))

    # Build candidates list sorted by frequency
    candidates = []
    for name, count in discovered_counts.most_common():
        candidates.append({
            "name": name,
            "suggested_type": discovered_types.get(name, "UNKNOWN"),
            "suggested_canonical_id": discovered_ids.get(name, ""),
            "occurrences": count,
            "found_in_images": discovered_images[name][:20],  # Cap at 20 for readability
            "context": discovered_contexts.get(name, ""),
            "recommendation": "ADD_TO_GAZETTEERS" if count >= 3 else "REVIEW",
        })

    total_mentions = sum(match_stats.values())
    matched = total_mentions - match_stats.get("unmatched", 0)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_images_analyzed": total_images,
        "total_mentions": total_mentions,
        "total_unique_discovered": len(candidates),
        "match_statistics": {
            "total_character_mentions": total_character_mentions,
            "total_symbol_mentions": total_symbol_mentions,
            "total_event_mentions": total_event_mentions,
            "exact_matches": match_stats.get("exact", 0),
            "alias_matches": match_stats.get("alias", 0),
            "translation_matches": match_stats.get("translation", 0),
            "fuzzy_matches": match_stats.get("fuzzy", 0),
            "unmatched": match_stats.get("unmatched", 0),
            "match_rate": matched / total_mentions if total_mentions else 0,
        },
        "top_characters": dict(top_characters.most_common(30)),
        "top_events": dict(top_events.most_common(30)),
        "top_symbols": dict(top_symbols.most_common(30)),
        "candidates": candidates,
    }

    # Save report
    report_path = output_dir / "discovery_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"  DISCOVERY REPORT — {total_images} images")
    print(f"{'='*60}")
    print(f"\n  Match rate: {matched}/{total_mentions} ({report['match_statistics']['match_rate']*100:.1f}%)")
    print(f"    Exact:       {match_stats.get('exact', 0)}")
    print(f"    Alias:       {match_stats.get('alias', 0)}")
    print(f"    Translation: {match_stats.get('translation', 0)}")
    print(f"    Fuzzy:       {match_stats.get('fuzzy', 0)}")
    print(f"    Unmatched:   {match_stats.get('unmatched', 0)}")


    print(f"\n  New entity candidates: {len(candidates)}")
    add_count = sum(1 for c in candidates if c["recommendation"] == "ADD_TO_GAZETTEERS")
    print(f"    Recommended to add (>=3 occurrences): {add_count}")
    print(f"    Needs review (<3 occurrences): {len(candidates) - add_count}")

    if candidates[:10]:
        print(f"\n  Top 10 discovered entities:")
        for c in candidates[:10]:
            print(f"    {c['occurrences']:>4}x  {c['name']:<30} → {c['suggested_canonical_id']}")

    print(f"\n  Report saved to: {report_path}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Generate discovery report from enriched tags")
    parser.add_argument("--enriched", type=Path, default=ENRICHED_DIR)
    parser.add_argument("--output", type=Path, default=REPORTS_DIR)
    args = parser.parse_args()

    generate_report(args.enriched, args.output)


if __name__ == "__main__":
    main()
