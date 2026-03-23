"""Gerar embeddings multimodais para busca semântica imagem ↔ versículo."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import EMBEDDINGS_DIR, GEMINI_EMBEDDING_MODEL, MAX_CONCURRENT_REQUESTS

load_dotenv()


async def embed_image(
    client: genai.Client,
    image_path: Path,
    semaphore: asyncio.Semaphore,
) -> list[float] | None:
    """Generate embedding for a single image."""
    async with semaphore:
        try:
            img = Image.open(image_path)
            response = await client.aio.models.embed_content(
                model=GEMINI_EMBEDDING_MODEL,
                contents=img,
            )
            return response.embeddings[0].values
        except Exception as e:
            print(f"  FAIL {image_path.stem}: {e}")
            return None


async def embed_text(
    client: genai.Client,
    text: str,
    semaphore: asyncio.Semaphore,
) -> list[float] | None:
    """Generate embedding for text (verse/description)."""
    async with semaphore:
        try:
            response = await client.aio.models.embed_content(
                model=GEMINI_EMBEDDING_MODEL,
                contents=text,
            )
            return response.embeddings[0].values
        except Exception as e:
            print(f"  FAIL text embedding: {e}")
            return None


async def run_image_embeddings(
    images_dir: Path,
    tags_dir: Path,
    output_dir: Path,
    limit: int | None = None,
):
    """Generate embeddings for all tagged images."""
    output_dir.mkdir(parents=True, exist_ok=True)

    tag_files = sorted(tags_dir.glob("*.json"))
    if limit:
        tag_files = tag_files[:limit]

    # Skip already processed
    existing = {p.stem for p in output_dir.glob("*.npy")}
    tag_files = [t for t in tag_files if t.stem not in existing]

    if not tag_files:
        print("All images already have embeddings.")
        return

    print(f"Generating embeddings for {len(tag_files)} images...")

    client = genai.Client()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    success = 0
    chunk_size = 20
    for i in range(0, len(tag_files), chunk_size):
        chunk = tag_files[i : i + chunk_size]
        tasks = []

        for tag_file in chunk:
            image_path = images_dir / f"{tag_file.stem}.jpg"
            if image_path.exists():
                tasks.append(embed_image(client, image_path, semaphore))
            else:
                tasks.append(asyncio.coroutine(lambda: None)())

        results = await asyncio.gather(*tasks)

        for tag_file, embedding in zip(chunk, results):
            if embedding:
                out_path = output_dir / f"{tag_file.stem}.npy"
                np.save(out_path, np.array(embedding, dtype=np.float32))
                success += 1

        print(f"  Progress: {min(i + chunk_size, len(tag_files))}/{len(tag_files)} | OK: {success}")

    # Save index mapping key → embedding file
    index = {t.stem: str(output_dir / f"{t.stem}.npy") for t in tag_files}
    index_path = output_dir / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"\nDone! {success} embeddings generated")
    print(f"Output: {output_dir}")
    print(f"Index: {index_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate multimodal embeddings for tagged images")
    parser.add_argument(
        "--images",
        type=Path,
        default=Path("E:/bible-images-dataset/data/00_raw/wikiart/images"),
        help="Path to images directory",
    )
    parser.add_argument(
        "--tags",
        type=Path,
        required=True,
        help="Directory with generated tag JSONs",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=EMBEDDINGS_DIR,
        help="Output directory for embeddings",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of images (for testing)",
    )
    args = parser.parse_args()

    asyncio.run(
        run_image_embeddings(
            images_dir=args.images,
            tags_dir=args.tags,
            output_dir=args.output,
            limit=args.limit,
        )
    )


if __name__ == "__main__":
    main()
