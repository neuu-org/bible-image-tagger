"""Pipeline de tagging de imagens bíblicas com Gemini 2.5 Flash Vision.

Usa response_schema para JSON estruturado garantido (constrained decoding).
Suporta HuggingFace dataset ou diretório local como fonte de imagens.
"""

import argparse
import asyncio
import json
import os
import sys
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from huggingface_hub import HfFileSystem
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import (
    GEMINI_MODEL,
    HF_DATASET_ID,
    MAX_CONCURRENT_REQUESTS,
    MAX_OUTPUT_TOKENS,
    OUTPUT_DIR,
    RETRY_ATTEMPTS,
    RETRY_DELAY,
    SCHEMA_VERSION,
    TAG_SCHEMA,
    TAGGING_PROMPT,
    TAGGING_SYSTEM_INSTRUCTION,
)

load_dotenv()

HF_IMAGES_PREFIX = f"datasets/{HF_DATASET_ID}/images"
HF_METADATA_PREFIX = f"datasets/{HF_DATASET_ID}/metadata/per_image"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_metadata_local(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_prompt(metadata: dict) -> str:
    return TAGGING_PROMPT.format(
        title=metadata.get("title", "Unknown"),
        artist=metadata.get("artist", "Unknown"),
        year=metadata.get("completion", "Unknown"),
        tags=", ".join(metadata.get("tags", [])) or "None",
    )


# ---------------------------------------------------------------------------
# Tagging with structured output
# ---------------------------------------------------------------------------

async def tag_single_image(
    client: genai.Client,
    img: Image.Image,
    metadata: dict,
    semaphore: asyncio.Semaphore,
) -> dict | None:
    """Tag a single image using Gemini Vision with response_schema."""
    async with semaphore:
        prompt = build_prompt(metadata)

        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = await client.aio.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[prompt, img],
                    config=types.GenerateContentConfig(
                        system_instruction=TAGGING_SYSTEM_INSTRUCTION,
                        temperature=0.1,
                        max_output_tokens=MAX_OUTPUT_TOKENS,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                        response_mime_type="application/json",
                        response_schema=TAG_SCHEMA,
                    ),
                )
                text = response.text.strip()
                # Handle markdown fences if model wraps output
                if text.startswith("```"):
                    text = "\n".join(text.split("\n")[1:])
                    if text.endswith("```"):
                        text = text[:-3].strip()
                result = json.loads(text)
                result["_meta"] = {
                    "key": metadata.get("key", "unknown"),
                    "title": metadata.get("title"),
                    "artist": metadata.get("artist"),
                    "model": GEMINI_MODEL,
                    "schema_version": SCHEMA_VERSION,
                }
                return result
            except json.JSONDecodeError:
                print(f"  JSON parse error for {metadata.get('key', '?')}, attempt {attempt + 1}")
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait = RETRY_DELAY * (2 ** attempt)
                    print(f"  Rate limited, waiting {wait:.0f}s...")
                    await asyncio.sleep(wait)
                elif attempt < RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    print(f"  FAIL {metadata.get('key', '?')}: {e}")
                    return None
    return None


# ---------------------------------------------------------------------------
# HuggingFace source
# ---------------------------------------------------------------------------

async def run_batch_hf(
    output_dir: Path,
    limit: int | None = None,
    skip_existing: bool = True,
):
    """Run tagging on images from HuggingFace dataset."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fs = HfFileSystem()

    print("Listing metadata files on HuggingFace...")
    meta_files = sorted(fs.glob(f"{HF_METADATA_PREFIX}/**/*.json"))
    print(f"  Found {len(meta_files)} metadata files")

    if limit:
        meta_files = meta_files[:limit]

    if skip_existing:
        existing = {p.stem for p in output_dir.glob("*.json")}
        meta_files = [m for m in meta_files if Path(m).stem not in existing]

    if not meta_files:
        print("Nothing to process.")
        return

    print(f"Processing {len(meta_files)} images from HuggingFace...")

    # Build image index
    print("Building image index...")
    image_index: dict[str, str] = {}
    for subdir in fs.ls(HF_IMAGES_PREFIX, detail=False):
        for img_path in fs.ls(subdir, detail=False):
            image_index[Path(img_path).stem] = img_path
    print(f"  Indexed {len(image_index)} images")

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    success = 0
    failed = 0

    for i, meta_path in enumerate(meta_files):
        key = Path(meta_path).stem
        try:
            with fs.open(meta_path, "r") as f:
                metadata = json.load(f)

            img_hf_path = image_index.get(key) or image_index.get(metadata.get("key", ""))
            if not img_hf_path:
                print(f"  SKIP {key}: image not found")
                failed += 1
                continue

            with fs.open(img_hf_path, "rb") as f:
                img = Image.open(BytesIO(f.read()))

            result = await tag_single_image(client, img, metadata, semaphore)

            if result:
                out_path = output_dir / f"{key}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                success += 1
            else:
                failed += 1

        except Exception as e:
            print(f"  ERROR {key}: {e}")
            failed += 1

        if (i + 1) % 10 == 0 or i == len(meta_files) - 1:
            print(f"  Progress: {i + 1}/{len(meta_files)} | OK: {success} | FAIL: {failed}")

    print(f"\nDone! Success: {success}, Failed: {failed}")
    print(f"Output: {output_dir}")


# ---------------------------------------------------------------------------
# Local source
# ---------------------------------------------------------------------------

async def run_batch_local(
    images_dir: Path,
    metadata_dir: Path,
    output_dir: Path,
    limit: int | None = None,
    skip_existing: bool = True,
):
    """Run tagging on local images."""
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_files = sorted(metadata_dir.glob("*.json"))
    if limit:
        metadata_files = metadata_files[:limit]

    if skip_existing:
        existing = {p.stem for p in output_dir.glob("*.json")}
        metadata_files = [m for m in metadata_files if m.stem not in existing]

    if not metadata_files:
        print("Nothing to process.")
        return

    print(f"Processing {len(metadata_files)} images (local)...")

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    success = 0
    failed = 0

    for i, meta_file in enumerate(metadata_files):
        metadata = load_metadata_local(meta_file)
        image_path = images_dir / f"{metadata['key']}.jpg"

        if not image_path.exists():
            failed += 1
            continue

        img = Image.open(image_path)
        result = await tag_single_image(client, img, metadata, semaphore)

        if result:
            out_path = output_dir / f"{meta_file.stem}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            success += 1
        else:
            failed += 1

        if (i + 1) % 10 == 0 or i == len(metadata_files) - 1:
            print(f"  Progress: {i + 1}/{len(metadata_files)} | OK: {success} | FAIL: {failed}")

    print(f"\nDone! Success: {success}, Failed: {failed}")
    print(f"Output: {output_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Tag biblical images with Gemini 2.5 Flash Vision")
    parser.add_argument("--source", choices=["hf", "local"], default="hf",
                        help="Image source: 'hf' (HuggingFace) or 'local'")
    parser.add_argument("--input", type=Path,
                        default=Path("E:/bible-images-dataset/data/00_raw/wikiart"))
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit images to process (for testing)")
    parser.add_argument("--no-skip", action="store_true",
                        help="Re-process already tagged images")
    args = parser.parse_args()

    if args.source == "hf":
        asyncio.run(run_batch_hf(args.output, args.limit, not args.no_skip))
    else:
        asyncio.run(run_batch_local(
            args.input / "images", args.input / "metadata",
            args.output, args.limit, not args.no_skip,
        ))


if __name__ == "__main__":
    main()
