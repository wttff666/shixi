from __future__ import annotations

import json
import sys


def main():
    from sentence_transformers import SentenceTransformer

    model = None
    model_path = None
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        requested_path = payload["model_path"]
        if model is None or requested_path != model_path:
            model = SentenceTransformer(requested_path, device="cpu")
            model_path = requested_path
        texts = payload.get("texts") or []
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        print(
            json.dumps(
                {
                    "model": model_path,
                    "dimension": int(vectors.shape[1]),
                    "vectors": vectors.tolist(),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
