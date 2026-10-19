from __future__ import annotations

import argparse
import sys

from .index import VectorIndex
from .generator import generate_grounded_answer
from .sources import stale_message


def main():
    p = argparse.ArgumentParser(description="Ask a question using the dataset-only RAG index.")
    p.add_argument("--index_dir", type=str, default="outputs/index", help="Path to index directory.")
    p.add_argument("--question", type=str, required=True)
    p.add_argument("--top_k", type=int, default=8)
    p.add_argument("--show_context", action="store_true", help="Print retrieved chunks (debug).")
    args = p.parse_args()

    index = VectorIndex.load(args.index_dir)
    stale = stale_message(args.index_dir)
    if stale:
        print(f"WARNING: {stale}", file=sys.stderr)

    retrieved = index.search(args.question, top_k=args.top_k)
    ans = generate_grounded_answer(args.question, retrieved)

    print("\nQUESTION:")
    print(args.question)
    print("\nANSWER:")
    print(ans.answer)

    if ans.citations:
        print("\nCITATIONS:")
        for c in ans.citations:
            print(f"- {c}")

    if args.show_context:
        print("\nRETRIEVED CHUNKS:")
        for ch, score in retrieved:
            print(f"\n--- {ch.chunk_id} (score={score:.3f}) ---")
            print(ch.text[:1200])


if __name__ == "__main__":
    main()
