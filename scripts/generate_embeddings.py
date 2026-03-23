"""Gerar embeddings multimodais com Gemini Embedding 2.

Usa gemini-embedding-2-preview para colocar imagens e texto no MESMO
espaço vetorial (768 dims). Permite busca cross-modal: texto → imagem.

Estratégias:
  - Image-only: embedding puro da imagem (para busca por texto)
  - Enriched: imagem + metadata (título, artista, tags) fundidos em 1 vetor
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types
from huggingface_hub import HfFileSystem

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIMS,
    EMBEDDINGS_DIR,
    GEMINI_EMBEDDING_MODEL,
    HF_DATASET_ID,
    RETRY_ATTEMPTS,
    RETRY_DELAY,
)

load_dotenv()

HF_IMAGES_PREFIX = f"datasets/{HF_DATASET_ID}/images"
HF_METADATA_PREFIX = f"datasets/{HF_DATASET_ID}/metadata/per_image"


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

def embed_images_batch(
    client: genai.Client,
    image_bytes_list: list[bytes],
) -> list[list[float]]:
    """Embed a batch of images (max 6) in a single API call."""
    contents = [
        types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
        for img_bytes in image_bytes_list
    ]

    result = client.models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=contents,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBEDDING_DIMS,
        ),
    )
    return [emb.values for emb in result.embeddings]


def embed_enriched_batch(
    client: genai.Client,
    items: list[tuple[bytes, str]],  # (image_bytes, metadata_text)
) -> list[list[float]]:
    """Embed image+text fused pairs. One Content per item → one embedding each."""
    contents = []
    for img_bytes, text in items:
        contents.append(
            types.Content(parts=[
                types.Part(text=text),
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
            ])
        )

    result = client.models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=contents,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBEDDING_DIMS,
        ),
    )
    return [emb.values for emb in result.embeddings]


def embed_text_query(
    client: genai.Client,
    query: str,
) -> list[float]:
    """Embed a text query for searching against image embeddings."""
    result = client.models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=[query],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=EMBEDDING_DIMS,
        ),
    )
    return result.embeddings[0].values


def metadata_to_text(meta: dict) -> str:
    """Convert image metadata to text for enriched embedding."""
    parts = []
    if meta.get("title"):
        parts.append(f"Title: {meta['title']}")
    if meta.get("artist"):
        parts.append(f"Artist: {meta['artist']}")
    if meta.get("completion"):
        parts.append(f"Year: {meta['completion']}")
    if meta.get("tags"):
        parts.append(f"Tags: {', '.join(meta['tags'])}")
    if meta.get("styles"):
        parts.append(f"Style: {', '.join(meta['styles'])}")
    return ". ".join(parts)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_hf(
    output_dir: Path,
    mode: str = "image",  # "image" or "enriched"
    limit: int | None = None,
    skip_existing: bool = True,
):
    """Generate embeddings from HuggingFace dataset."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fs = HfFileSystem()

    print("Listing metadata on HuggingFace...")
    meta_files = sorted(fs.glob(f"{HF_METADATA_PREFIX}/**/*.json"))
    if limit:
        meta_files = meta_files[:limit]

    # Check existing
    checkpoint_path = output_dir / "checkpoint.json"
    processed = set()
    if skip_existing and checkpoint_path.exists():
        with open(checkpoint_path) as f:
            processed = set(json.load(f))
        print(f"  Resuming: {len(processed)} already done")

    meta_files = [m for m in meta_files if Path(m).stem not in processed]
    if not meta_files:
        print("All embeddings already generated.")
        return

    print(f"Generating {mode} embeddings for {len(meta_files)} images...")
    print(f"  Model: {GEMINI_EMBEDDING_MODEL} | Dims: {EMBEDDING_DIMS}")

    # Build image index
    print("Building image index...")
    image_index: dict[str, str] = {}
    for subdir in fs.ls(HF_IMAGES_PREFIX, detail=False):
        for img_path in fs.ls(subdir, detail=False):
            image_index[Path(img_path).stem] = img_path
    print(f"  Indexed {len(image_index)} images")

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    all_embeddings = {}
    all_keys = []
    success = 0
    failed = 0

    # Load existing embeddings
    npy_path = output_dir / f"embeddings_{mode}.npy"
    keys_path = output_dir / f"keys_{mode}.json"
    if npy_path.exists() and keys_path.exists():
        all_embeddings_array = np.load(npy_path)
        with open(keys_path) as f:
            existing_keys = json.load(f)
        for k, emb in zip(existing_keys, all_embeddings_array):
            all_embeddings[k] = emb.tolist()
        all_keys = existing_keys

    # Process in batches of EMBEDDING_BATCH_SIZE
    for i in range(0, len(meta_files), EMBEDDING_BATCH_SIZE):
        batch_metas = meta_files[i : i + EMBEDDING_BATCH_SIZE]
        batch_bytes = []
        batch_texts = []
        batch_keys = []

        for meta_path in batch_metas:
            key = Path(meta_path).stem
            try:
                with fs.open(meta_path, "r") as f:
                    meta = json.load(f)

                img_hf_path = image_index.get(key) or image_index.get(meta.get("key", ""))
                if not img_hf_path:
                    failed += 1
                    continue

                with fs.open(img_hf_path, "rb") as f:
                    img_bytes = f.read()

                batch_bytes.append(img_bytes)
                batch_texts.append(metadata_to_text(meta))
                batch_keys.append(key)
            except Exception as e:
                print(f"  SKIP {key}: {e}")
                failed += 1

        if not batch_bytes:
            continue

        # Generate embeddings with retry
        for attempt in range(RETRY_ATTEMPTS):
            try:
                if mode == "enriched":
                    vectors = embed_enriched_batch(
                        client, list(zip(batch_bytes, batch_texts))
                    )
                else:
                    vectors = embed_images_batch(client, batch_bytes)

                for key, vec in zip(batch_keys, vectors):
                    all_embeddings[key] = vec
                    if key not in all_keys:
                        all_keys.append(key)
                    processed.add(key)
                success += len(vectors)
                break

            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    wait = RETRY_DELAY * (2 ** attempt)
                    print(f"  Rate limited, waiting {wait:.0f}s...")
                    time.sleep(wait)
                elif attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"  FAIL batch at {i}: {e}")
                    failed += len(batch_keys)

        # Checkpoint every 10 batches
        batch_num = i // EMBEDDING_BATCH_SIZE
        if batch_num % 10 == 0 or i + EMBEDDING_BATCH_SIZE >= len(meta_files):
            matrix = np.array([all_embeddings[k] for k in all_keys], dtype=np.float32)
            np.save(npy_path, matrix)
            with open(keys_path, "w") as f:
                json.dump(all_keys, f)
            with open(checkpoint_path, "w") as f:
                json.dump(list(processed), f)

            total = success + failed
            print(f"  Checkpoint: {total}/{len(meta_files) + len(processed) - total} | OK: {success} | FAIL: {failed}")

        time.sleep(0.5)  # Rate limit buffer

    # Final save
    if all_keys:
        matrix = np.array([all_embeddings[k] for k in all_keys], dtype=np.float32)
        np.save(npy_path, matrix)
        with open(keys_path, "w") as f:
            json.dump(all_keys, f)
        with open(checkpoint_path, "w") as f:
            json.dump(list(processed), f)

    print(f"\nDone! {success} embeddings generated ({EMBEDDING_DIMS} dims)")
    print(f"  Matrix: {npy_path} ({matrix.shape})")
    print(f"  Keys: {keys_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate multimodal embeddings with Gemini Embedding 2"
    )
    parser.add_argument("--source", choices=["hf", "local"], default="hf")
    parser.add_argument("--mode", choices=["image", "enriched"], default="image",
                        help="'image': image-only embedding. 'enriched': image+metadata fused")
    parser.add_argument("--output", type=Path, default=EMBEDDINGS_DIR)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-skip", action="store_true")
    args = parser.parse_args()

    run_hf(args.output, args.mode, args.limit, not args.no_skip)


if __name__ == "__main__":
    main()
