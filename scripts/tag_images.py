"""Pipeline de tagging de imagens bíblicas com Gemini 2 Flash Vision."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import (
    GEMINI_MODEL,
    MAX_CONCURRENT_REQUESTS,
    OUTPUT_DIR,
    RETRY_ATTEMPTS,
    RETRY_DELAY,
    TAGGING_PROMPT,
)

load_dotenv()


def load_metadata(metadata_path: Path) -> dict:
    """Load image metadata JSON."""
    with open(metadata_path, encoding="utf-8") as f:
        return json.load(f)


def build_prompt(metadata: dict) -> str:
    """Build the tagging prompt with metadata context."""
    return TAGGING_PROMPT.format(
        title=metadata.get("title", "Unknown"),
        artist=metadata.get("artist", "Unknown"),
        year=metadata.get("completion", "Unknown"),
        tags=", ".join(metadata.get("tags", [])) or "None",
    )


def parse_response(text: str) -> dict | None:
    """Parse Gemini response as JSON, handling markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def tag_single_image(
    client: genai.Client,
    image_path: Path,
    metadata: dict,
    semaphore: asyncio.Semaphore,
) -> dict | None:
    """Tag a single image using Gemini Vision."""
    async with semaphore:
        prompt = build_prompt(metadata)
        img = Image.open(image_path)

        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = await client.aio.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[prompt, img],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=1024,
                    ),
                )
                result = parse_response(response.text)
                if result:
                    result["_meta"] = {
                        "key": metadata["key"],
                        "title": metadata.get("title"),
                        "artist": metadata.get("artist"),
                        "model": GEMINI_MODEL,
                    }
                    return result
            except Exception as e:
                if attempt < RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    print(f"  FAIL {metadata['key']}: {e}")
                    return None
    return None


async def run_batch(
    images_dir: Path,
    metadata_dir: Path,
    output_dir: Path,
    limit: int | None = None,
    skip_existing: bool = True,
):
    """Run tagging on a batch of images."""
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_files = sorted(metadata_dir.glob("*.json"))
    if limit:
        metadata_files = metadata_files[:limit]

    # Filter already processed
    if skip_existing:
        existing = {p.stem for p in output_dir.glob("*.json")}
        metadata_files = [m for m in metadata_files if m.stem not in existing]

    if not metadata_files:
        print("Nothing to process (all images already tagged or no metadata found).")
        return

    print(f"Processing {len(metadata_files)} images...")

    client = genai.Client()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    success = 0
    failed = 0

    # Process in chunks for progress tracking
    chunk_size = 50
    for i in range(0, len(metadata_files), chunk_size):
        chunk = metadata_files[i : i + chunk_size]
        tasks = []

        for meta_file in chunk:
            metadata = load_metadata(meta_file)
            image_path = images_dir / f"{metadata['key']}.jpg"

            if not image_path.exists():
                failed += 1
                continue

            tasks.append(tag_single_image(client, image_path, metadata, semaphore))

        results = await asyncio.gather(*tasks)

        for meta_file, result in zip(chunk, results):
            if result:
                out_path = output_dir / f"{meta_file.stem}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                success += 1
            else:
                failed += 1

        print(f"  Progress: {min(i + chunk_size, len(metadata_files))}/{len(metadata_files)} | OK: {success} | FAIL: {failed}")

    print(f"\nDone! Success: {success}, Failed: {failed}")
    print(f"Output: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Tag biblical images with Gemini 2 Flash Vision")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("E:/bible-images-dataset/data/00_raw/wikiart"),
        help="Path to wikiart directory (with images/ and metadata/ subdirs)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help="Output directory for generated tags",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of images to process (for testing)",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Re-process images that already have tags",
    )
    args = parser.parse_args()

    images_dir = args.input / "images"
    metadata_dir = args.input / "metadata"

    if not images_dir.exists():
        print(f"Images directory not found: {images_dir}")
        sys.exit(1)
    if not metadata_dir.exists():
        print(f"Metadata directory not found: {metadata_dir}")
        sys.exit(1)

    asyncio.run(
        run_batch(
            images_dir=images_dir,
            metadata_dir=metadata_dir,
            output_dir=args.output,
            limit=args.limit,
            skip_existing=not args.no_skip,
        )
    )


if __name__ == "__main__":
    main()
