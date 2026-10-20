from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
import logging
import os

from .index import VectorIndex
from .generator import generate_grounded_answer
from .sources import stale_message

INDEX_DIR = os.getenv("RAG_INDEX_DIR", "outputs/index")
index: VectorIndex | None = None
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global index
    index = VectorIndex.load(INDEX_DIR)
    stale = stale_message(INDEX_DIR)
    if stale:
        logger.warning(stale)
    yield
    index = None  # optional cleanup


app = FastAPI(
    title="PDF RAG (Dataset-Only)",
    lifespan=lifespan,
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3)
    top_k: int = Field(8, ge=1, le=20)


class AskResponse(BaseModel):
    answer: str
    citations: list[str]
    used_chunks: list[str]


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    if index is None:
        raise HTTPException(status_code=503, detail="Index not loaded")

    retrieved = index.search(req.question, top_k=req.top_k)
    ans = generate_grounded_answer(req.question, retrieved)

    return AskResponse(
        answer=ans.answer,
        citations=ans.citations,
        used_chunks=ans.used_chunks,
    )
