"""Validação cruzada de tags geradas contra gazetteers e topics."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import VALIDATION_DIR


def load_gazetteers(gazetteers_path: Path) -> dict[str, dict]:
    """Load gazetteer entities into a lookup by name/alias."""
    lookup = {}
    entities_dir = gazetteers_path / "data" / "pt" / "entities"

    if not entities_dir.exists():
        print(f"Gazetteers not found: {entities_dir}")
        return lookup

    for json_file in entities_dir.glob("*.json"):
        with open(json_file, encoding="utf-8") as f:
            entities = json.load(f)
        for entity in entities:
            name = entity.get("name", "").lower()
            if name:
                lookup[name] = entity
            for alias in entity.get("aliases", []):
                lookup[alias.lower()] = entity

    return lookup


def load_topics(topics_path: Path) -> dict[str, dict]:
    """Load topics into a lookup by topic name."""
    lookup = {}
    for letter_dir in topics_path.glob("*"):
        if not letter_dir.is_dir():
            continue
        for json_file in letter_dir.glob("*.json"):
            with open(json_file, encoding="utf-8") as f:
                topic = json.load(f)
            name = topic.get("topic", "").lower()
            if name:
                lookup[name] = topic

    return lookup


def validate_tags(tags_dir: Path, gazetteers: dict, topics: dict) -> dict:
    """Validate generated tags against reference datasets."""
    stats = {
        "total": 0,
        "with_osis_refs": 0,
        "characters_matched": 0,
        "characters_unmatched": 0,
        "themes_matched": 0,
        "high_confidence": 0,
        "low_confidence": 0,
        "testament_dist": Counter(),
        "top_characters": Counter(),
        "top_events": Counter(),
        "top_themes": Counter(),
        "unmatched_characters": Counter(),
    }

    for tag_file in tags_dir.glob("*.json"):
        with open(tag_file, encoding="utf-8") as f:
            tag = json.load(f)

        stats["total"] += 1

        if tag.get("osis_refs"):
            stats["with_osis_refs"] += 1

        confidence = tag.get("confidence", 0)
        if confidence >= 0.7:
            stats["high_confidence"] += 1
        elif confidence < 0.3:
            stats["low_confidence"] += 1

        testament = tag.get("testament", "UNKNOWN")
        stats["testament_dist"][testament] += 1

        for char in tag.get("characters", []):
            stats["top_characters"][char] += 1
            if char.lower() in gazetteers:
                stats["characters_matched"] += 1
            else:
                stats["characters_unmatched"] += 1
                stats["unmatched_characters"][char] += 1

        for theme in tag.get("themes", []):
            stats["top_themes"][theme] += 1
            if theme.lower() in topics:
                stats["themes_matched"] += 1

        event = tag.get("event", "")
        if event:
            stats["top_events"][event] += 1

    return stats


def print_report(stats: dict):
    """Print validation report."""
    total = stats["total"]
    if total == 0:
        print("No tags found to validate.")
        return

    print(f"\n{'='*60}")
    print(f"  VALIDATION REPORT — {total} images")
    print(f"{'='*60}")

    print(f"\n  Coverage:")
    print(f"    With OSIS refs:    {stats['with_osis_refs']:>6} ({stats['with_osis_refs']/total*100:.1f}%)")
    print(f"    High confidence:   {stats['high_confidence']:>6} ({stats['high_confidence']/total*100:.1f}%)")
    print(f"    Low confidence:    {stats['low_confidence']:>6} ({stats['low_confidence']/total*100:.1f}%)")

    print(f"\n  Character validation (vs gazetteers):")
    matched = stats["characters_matched"]
    unmatched = stats["characters_unmatched"]
    char_total = matched + unmatched
    if char_total:
        print(f"    Matched:   {matched:>6} ({matched/char_total*100:.1f}%)")
        print(f"    Unmatched: {unmatched:>6} ({unmatched/char_total*100:.1f}%)")

    print(f"\n  Testament distribution:")
    for testament, count in stats["testament_dist"].most_common():
        print(f"    {testament:<10} {count:>6} ({count/total*100:.1f}%)")

    print(f"\n  Top 15 characters:")
    for char, count in stats["top_characters"].most_common(15):
        marker = "+" if char.lower() in {} else " "
        print(f"    {marker} {char:<30} {count:>5}")

    print(f"\n  Top 15 events:")
    for event, count in stats["top_events"].most_common(15):
        print(f"    {event:<40} {count:>5}")

    print(f"\n  Top 15 themes:")
    for theme, count in stats["top_themes"].most_common(15):
        print(f"    {theme:<30} {count:>5}")

    if stats["unmatched_characters"]:
        print(f"\n  Top unmatched characters (not in gazetteers):")
        for char, count in stats["unmatched_characters"].most_common(10):
            print(f"    {char:<30} {count:>5}")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Validate generated tags against gazetteers and topics")
    parser.add_argument("--tags", type=Path, required=True, help="Directory with generated tag JSONs")
    parser.add_argument(
        "--gazetteers",
        type=Path,
        default=Path("C:/Users/Iury Coelho/Desktop/bible-gazetteers-dataset"),
    )
    parser.add_argument(
        "--topics",
        type=Path,
        default=Path("C:/Users/Iury Coelho/Desktop/bible-topics-dataset/data/02_unified"),
    )
    parser.add_argument("--save", action="store_true", help="Save report to validation dir")
    args = parser.parse_args()

    print("Loading gazetteers...")
    gazetteers = load_gazetteers(args.gazetteers)
    print(f"  {len(gazetteers)} entity entries loaded")

    print("Loading topics...")
    topics = load_topics(args.topics)
    print(f"  {len(topics)} topic entries loaded")

    print("Validating tags...")
    stats = validate_tags(args.tags, gazetteers, topics)

    print_report(stats)

    if args.save:
        VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
        report_path = VALIDATION_DIR / "validation_report.json"
        serializable = {
            k: dict(v) if isinstance(v, Counter) else v
            for k, v in stats.items()
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        print(f"Report saved to {report_path}")


if __name__ == "__main__":
    main()
