from __future__ import annotations

import argparse
from pathlib import Path
from datetime import datetime

from .index import VectorIndex
from .generator import generate_grounded_answer


DEFAULT_QUESTIONS = [
    "What is MITRE ATT&CK, and what is its primary purpose?",
    "What are the use cases for the MITRE ATT&CK model?",
    "What is the OWASP Top 10, and what is its purpose for developers and web application security?",
    "What types of vulnerabilities are associated with “Broken Access Control” in the OWASP Top 10: 2021?",
    "มาตรฐานการรักษาความมั่นคงปลอดภัยสำหรับเว็บไซต์คืออะไร?",
    "ใครมีอำนาจออกประกาศ คำสั่ง หลักเกณฑ์ และวิธีการเพื่อปฏิบัติตามประกาศนี้?",
]

def main():
    p = argparse.ArgumentParser(description="Run a small evaluation set and save a markdown report.")
    p.add_argument("--index_dir", type=str, default="outputs/index")
    p.add_argument("--out", type=str, default="outputs/eval_report.md")
    p.add_argument("--top_k", type=int, default=8)
    args = p.parse_args()

    index = VectorIndex.load(args.index_dir)

    lines = []
    lines.append(f"# RAG Evaluation Report\n")
    lines.append(f"- Generated: {datetime.now().isoformat(timespec='seconds')}\n")
    lines.append(f"- Index: `{Path(args.index_dir).as_posix()}`\n")

    for q in DEFAULT_QUESTIONS:
        retrieved = index.search(q, top_k=args.top_k)
        ans = generate_grounded_answer(q, retrieved)

        lines.append("\n---\n")
        lines.append(f"Q: {q}\n")
        lines.append(f"A: {ans.answer}\n")
        if ans.citations:
            lines.append("\n**Citations:**\n")
            for c in ans.citations:
                lines.append(f"- `{c}`\n")
        else:
            lines.append("\n**Citations:** (none — refused due to insufficient evidence)\n")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"Wrote evaluation report to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
