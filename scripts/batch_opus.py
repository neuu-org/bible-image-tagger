"""Batch processing helper for Claude Opus 4.6 agents.

Prepares batches of images with their metadata (WikiArt + HuggingFace),
downloads images to local cache, and generates the agent prompts.

Usage (from Claude Code):
    1. Run this script to prepare a batch
    2. Copy the generated prompts to launch agents
    3. After agents finish, run enrich_tags.py

    python scripts/batch_opus.py --start 0 --count 20
    python scripts/batch_opus.py --start 20 --count 20
    python scripts/batch_opus.py --keys 0000004,0000010,0000021
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import OUTPUT_DIR

# Paths
WIKIART_METADATA = Path("E:/bible-images-dataset/data/00_raw/wikiart/metadata")
HF_CACHE_BASE = Path.home() / ".cache/huggingface/hub/datasets--Iuryeng--bible-images-dataset/snapshots"

AGENT_PROMPT_TEMPLATE = """\
You are a biblical art expert and theologian with deep knowledge of Scripture, \
patristics, typology, and Christian iconography.

Read each image below using the Read tool, then generate a JSON tag file and \
write it using the Write tool.

{image_blocks}

## Output JSON Schema (write EXACTLY this format for each image):

```json
{{
  "characters": [
    {{"name": "Character Name", "type": "PERSON|GROUP|ANGEL|DEITY|OTHER"}}
  ],
  "event": "Biblical event or scene name",
  "tags": ["tag1", "tag2", ...],
  "symbols": ["symbol — its theological meaning"],
  "description": "Visual-only description, max 600 chars. What you SEE. No art style/artist/technique.",
  "theological_description": "What a theologian, mystic, or deeply scripturally-literate person would read into this image. Include typological connections, patristic readings, scriptural allusions. Can be empty string if not applicable.",
  "scripture_refs": [
    {{"ref": "BOOK.CH.VS", "relevance": "primary|typological|allusion", "reason": "Why this connects"}}
  ],
  "scene_type": "narrative|portrait|allegory|symbolic|liturgical|landscape",
  "mood": ["emotion1", "emotion2"],
  "period": "Creation|Antediluvian|Patriarchal|Exodus|Conquest|Monarchy|Exile|Prophetic|Intertestamental|Gospel|Apostolic|Eschatological|Liturgical|Non-biblical",
  "_meta": {{
    "key": "IMAGE_KEY",
    "title": "...",
    "artist": "...",
    "model": "claude-opus-4-6"
  }}
}}
```

## Field rules:

**tags**: Include BOTH visual AND deep theological/symbolic tags. \
Capture typology, prefigurations, scriptural allusions, symbolic meanings, \
patristic interpretations. A dove = Holy Spirit. A cross = redemption. \
An apple with Christ = new Adam redeeming the fall. Water = baptism/judgment. \
Fish = ICHTHYS. Lamb = Agnus Dei. Bread/wine = Eucharist.

**symbols**: Format "name — meaning". List objects with biblical symbolic meaning. \
Include subtle ones: colors, gestures, natural elements, architectural elements.

**description**: ONLY what you see. Max 600 chars. No art history. \
Describe as if for someone who cannot see the image.

**theological_description**: The DEEP theological reading. What would a Church Father, \
a mystic, or a biblical scholar see in this image that a casual viewer would miss? \
Typological connections (OT→NT), patristic interpretations, symbolic layers.

**scripture_refs**: Use OSIS abbreviations (GEN, EXO, 1KI, MAT, JHN, REV, etc). \
Relevance: "primary" = direct narrative source, "typological" = OT/NT type connection, \
"allusion" = thematic echo. Include reason for each.

**scene_type**: narrative (story scene), portrait (single figure), allegory (abstract concept), \
symbolic (symbolic composition), liturgical (worship/sacrament), landscape (setting-focused).

**mood**: 2-4 emotional tones of the scene.

**period**: Biblical time period of the depicted scene.

Process ALL images and write ALL output files."""


def find_hf_cache_snapshot() -> Path | None:
    """Find the HuggingFace cache snapshot directory."""
    if not HF_CACHE_BASE.exists():
        return None
    snapshots = list(HF_CACHE_BASE.iterdir())
    if snapshots:
        return snapshots[0]
    return None


def find_image_in_cache(key: str, snapshot: Path) -> Path | None:
    """Find an image in the HF cache by key."""
    images_dir = snapshot / "images"
    if not images_dir.exists():
        return None
    for subdir in images_dir.iterdir():
        img_path = subdir / f"{key}.jpg"
        if img_path.exists():
            return img_path
    return None


def load_wikiart_metadata(key: str) -> dict | None:
    """Load WikiArt metadata from local dataset."""
    meta_path = WIKIART_METADATA / f"{key}.json"
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    return None


def prepare_batch(
    keys: list[str] | None = None,
    start: int = 0,
    count: int = 10,
    skip_existing: bool = True,
) -> list[dict]:
    """Prepare a batch of images for processing."""
    snapshot = find_hf_cache_snapshot()

    # Get keys from WikiArt metadata if not specified
    if keys is None:
        meta_files = sorted(WIKIART_METADATA.glob("*.json"))
        all_keys = [f.stem for f in meta_files]
        keys = all_keys[start : start + count]

    # Filter already processed
    if skip_existing:
        existing = {p.stem for p in OUTPUT_DIR.glob("*.json")}
        keys = [k for k in keys if k not in existing]

    batch = []
    for key in keys:
        meta = load_wikiart_metadata(key)
        if not meta:
            continue

        img_path = find_image_in_cache(key, snapshot) if snapshot else None

        batch.append({
            "key": key,
            "title": meta.get("title", "Unknown"),
            "artist": meta.get("artist", "Unknown"),
            "year": meta.get("completion"),
            "styles": meta.get("styles", []),
            "genres": meta.get("genres", []),
            "wikiart_tags": meta.get("tags", []),
            "media": meta.get("media", []),
            "image_path": str(img_path) if img_path else None,
            "needs_download": img_path is None,
        })

    return batch


def generate_agent_prompts(
    batch: list[dict],
    images_per_agent: int = 2,
) -> list[dict]:
    """Generate agent prompts for a batch, grouped by images_per_agent."""
    agents = []

    for i in range(0, len(batch), images_per_agent):
        group = batch[i : i + images_per_agent]

        image_blocks = []
        for item in group:
            context_parts = [f"- Title: \"{item['title']}\""]
            context_parts.append(f"- Artist: {item['artist']}")
            if item["year"]:
                context_parts.append(f"- Year: {item['year']}")
            if item["styles"]:
                context_parts.append(f"- Style: {', '.join(item['styles'])}")
            if item["wikiart_tags"]:
                context_parts.append(f"- WikiArt tags: {', '.join(item['wikiart_tags'])}")

            block = f"""## Image: {item['key']}
- Image path: {item['image_path']}
{chr(10).join(context_parts)}
- Write output to: {OUTPUT_DIR / f"{item['key']}.json"}"""
            image_blocks.append(block)

        prompt = AGENT_PROMPT_TEMPLATE.format(
            image_blocks="\n\n".join(image_blocks)
        )

        agents.append({
            "keys": [item["key"] for item in group],
            "prompt": prompt,
            "description": f"Tag images {', '.join(item['key'] for item in group)}",
        })

    return agents


def print_batch_summary(batch: list[dict], agents: list[dict]):
    """Print batch summary."""
    print(f"\n{'='*60}")
    print(f"  BATCH PREPARED — {len(batch)} images → {len(agents)} agents")
    print(f"{'='*60}")

    for item in batch:
        status = "CACHED" if item["image_path"] else "NEEDS DOWNLOAD"
        print(f"  {item['key']} | {status} | {item['title'][:50]}")

    need_download = [item for item in batch if item["needs_download"]]
    if need_download:
        print(f"\n  ⚠ {len(need_download)} images need to be downloaded first:")
        print(f"  Run: python -c \"from huggingface_hub import hf_hub_download; ...\"")

    print(f"\n  Agents to launch: {len(agents)}")
    for ag in agents:
        print(f"    → {ag['description']}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Prepare batch for Opus agents")
    parser.add_argument("--start", type=int, default=0, help="Start index in metadata list")
    parser.add_argument("--count", type=int, default=10, help="Number of images")
    parser.add_argument("--keys", type=str, default=None, help="Comma-separated image keys")
    parser.add_argument("--images-per-agent", type=int, default=2)
    parser.add_argument("--no-skip", action="store_true")
    parser.add_argument("--print-prompts", action="store_true", help="Print full agent prompts")
    args = parser.parse_args()

    keys = args.keys.split(",") if args.keys else None

    batch = prepare_batch(keys, args.start, args.count, not args.no_skip)

    if not batch:
        print("Nothing to process (all images already tagged or no metadata found).")
        return

    agents = generate_agent_prompts(batch, args.images_per_agent)
    print_batch_summary(batch, agents)

    if args.print_prompts:
        for ag in agents:
            print(f"\n--- PROMPT for {ag['description']} ---")
            print(ag["prompt"])
            print("--- END ---\n")

    # Save prompts for easy copy-paste
    prompts_dir = OUTPUT_DIR.parent / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for i, ag in enumerate(agents):
        prompt_path = prompts_dir / f"agent_{i:03d}.txt"
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(ag["prompt"])

    print(f"  Prompts saved to: {prompts_dir}/")


if __name__ == "__main__":
    main()
