from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Tuple

from openai import OpenAI
from pydantic import BaseModel

from .chunking import Chunk

OPENAI_MODEL = "gpt-4o-mini"
TEMPERATURE = 0.0
REFUSAL = "Insufficient information in dataset."

SYSTEM_PROMPT = (
    "You are a constrained question-answering system. "
    "You MUST answer using ONLY the numbered context blocks provided. "
    "Do NOT use prior knowledge. "
    "Answer in the same language as the question. "
    "List the numbers of the context blocks your answer is based on in source_ids. "
    "If the answer is not stated in the context, "
    f"set answer to exactly '{REFUSAL}' and leave source_ids empty."
)


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    return OpenAI()  # uses OPENAI_API_KEY env var; created on first use so imports work without it


@dataclass(frozen=True)
class Answer:
    answer: str
    citations: List[str]
    used_chunks: List[str]


class GroundedResponse(BaseModel):
    answer: str
    source_ids: List[int]


def _build_citation(chunk: Chunk) -> str:
    # dataset/file.txt::page_3  →  dataset/file.txt#page_3
    if "::" in chunk.chunk_id:
        return chunk.chunk_id.replace("::", "#")
    return chunk.chunk_id


def _is_refusal(text: str) -> bool:
    cleaned = text.strip().strip("'\"“”‘’").strip().lower()
    return cleaned.startswith(REFUSAL.lower().rstrip("."))


def _ask_model(question: str, chunks: List[str]) -> Optional[GroundedResponse]:
    """Returns None if the model declines to answer at all."""
    context = "\n---\n".join(f"[{i}]\n{text}" for i, text in enumerate(chunks, start=1))

    completion = get_client().chat.completions.parse(
        model=OPENAI_MODEL,
        temperature=TEMPERATURE,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n<<<\n{context}\n>>>\n\nQuestion:\n{question}"},
        ],
        response_format=GroundedResponse,
    )
    return completion.choices[0].message.parsed


def generate_grounded_answer(
    question: str,
    retrieved: List[Tuple[Chunk, float]],) -> Answer:
    """
    Generate answer using OpenAI only.
    Grounding decision is delegated to the model; citations are the pages it says it used.
    """
    refusal = Answer(answer=REFUSAL, citations=[], used_chunks=[])
    if not retrieved:
        return refusal

    response = _ask_model(question, [chunk.text for chunk, _ in retrieved])
    if response is None or _is_refusal(response.answer):
        return refusal

    cited_ids = {i for i in response.source_ids if 1 <= i <= len(retrieved)}
    cited = [chunk for i, (chunk, _) in enumerate(retrieved, start=1) if i in cited_ids]
    if not cited:  # answered without naming sources: fall back to everything it was shown
        cited = [chunk for chunk, _ in retrieved]

    citations = []
    used_chunks = []
    for chunk in cited:
        citation = _build_citation(chunk)
        if citation not in citations:
            citations.append(citation)
        if chunk.chunk_id not in used_chunks:
            used_chunks.append(chunk.chunk_id)

    return Answer(
        answer=response.answer.strip(),
        citations=citations,
        used_chunks=used_chunks,
    )
