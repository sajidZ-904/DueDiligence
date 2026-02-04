from __future__ import annotations

import os
from dataclasses import dataclass
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from src.models.enums import ScopeType
from src.storage.memory_store import ChunkRecord, DocumentRecord, STORE


@dataclass(frozen=True)
class RagAnswer:
    answer_text: str
    answerable: bool
    confidence: float
    citations: List[Dict[str, Any]]


_lock = RLock()
_embedder = None
_llm = None


def rag_enabled() -> bool:
    return os.getenv("QA_AI_MODE", "").strip().lower() in {"rag", "transformers", "langchain"}


def _lazy_embedder():
    global _embedder
    with _lock:
        if _embedder is not None:
            return _embedder
        import torch
        from transformers import AutoModel, AutoTokenizer
        from transformers.utils import logging as hf_logging

        model_name = os.getenv("QA_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2").strip()
        hf_logging.set_verbosity_error()
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)
        model.eval()

        def embed_texts(texts: List[str]) -> "torch.Tensor":
            tokens = tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            )
            with torch.no_grad():
                out = model(**tokens)
            hidden = out.last_hidden_state
            mask = tokens["attention_mask"].unsqueeze(-1).expand(hidden.size()).float()
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
            pooled = pooled.detach().cpu().float()
            pooled = pooled / pooled.norm(dim=1, keepdim=True).clamp(min=1e-12)
            return pooled

        _embedder = embed_texts
        return _embedder


def _lazy_llm():
    global _llm
    with _lock:
        if _llm is not None:
            return _llm

        from transformers import pipeline
        from transformers.utils import logging as hf_logging

        gen_model = os.getenv("QA_GEN_MODEL", "google/flan-t5-small").strip()
        if gen_model.lower().startswith("gpt-"):
            raise ValueError(
                "QA_GEN_MODEL must be a local Hugging Face Transformers model id (e.g. google/flan-t5-small). "
                "OpenAI-style model names like 'gpt-*' are not supported by this Transformers pipeline."
            )
        hf_logging.set_verbosity_error()
        gen = pipeline(
            "text2text-generation",
            model=gen_model,
            max_new_tokens=int(os.getenv("QA_MAX_NEW_TOKENS", "256")),
            do_sample=False,
        )

        try:
            from langchain_community.llms import HuggingFacePipeline
        except Exception:
            from langchain.llms import HuggingFacePipeline

        _llm = HuggingFacePipeline(pipeline=gen)
        return _llm


def _build_context(docs: List[DocumentRecord], top_chunks: List[Tuple[float, DocumentRecord, ChunkRecord]]) -> str:
    parts = []
    for score, doc, chunk in top_chunks:
        text = chunk.text.replace("\r\n", "\n").strip()
        if not text:
            continue
        parts.append(f"[doc={doc.filename} page={chunk.page_number} score={score:.3f}]\n{text}")
    return "\n\n".join(parts)


def _select_top_chunks(docs: List[DocumentRecord], question: str, *, k: int = 5) -> List[Tuple[float, DocumentRecord, ChunkRecord]]:
    import torch

    embed = _lazy_embedder()
    chunk_rows: List[Tuple[DocumentRecord, ChunkRecord]] = []
    texts: List[str] = []
    for doc in docs:
        for chunk in doc.chunks:
            t = chunk.text.strip()
            if not t:
                continue
            chunk_rows.append((doc, chunk))
            texts.append(t[:1200])

    if not texts:
        return []

    q_vec = embed([question])[0]
    m = embed(texts)
    sims = m @ q_vec
    top_k = min(k, int(sims.shape[0]))
    scores, indices = torch.topk(sims, k=top_k, largest=True, sorted=True)
    out: List[Tuple[float, DocumentRecord, ChunkRecord]] = []
    for score, i in zip(scores.tolist(), indices.tolist()):
        doc, chunk = chunk_rows[int(i)]
        out.append((float(score), doc, chunk))
    return out


def answer_with_rag(*, project_id: UUID, question_id: UUID) -> RagAnswer:
    project = STORE.get_project(project_id)
    if project is None:
        raise KeyError("project_not_found")
    question = project.questions.get(question_id)
    if question is None:
        raise KeyError("question_not_found")

    if project.scope_type == ScopeType.ALL_DOCS:
        docs = STORE.iter_indexed_docs_for_all_docs()
    else:
        docs = STORE.iter_indexed_docs_for_subset(project.scope_document_ids)

    top = _select_top_chunks(docs, question.prompt, k=int(os.getenv("QA_TOP_K", "5")))
    citations = [
        {
            "document_id": str(doc.document_id),
            "chunk_id": str(chunk.chunk_id),
            "page_number": chunk.page_number,
            "bbox": chunk.bbox,
            "excerpt": chunk.text[:240],
        }
        for _, doc, chunk in top
    ]
    if not top:
        return RagAnswer(
            answer_text="Not answerable from the currently indexed documents for this project scope.",
            answerable=False,
            confidence=0.1,
            citations=[],
        )

    ctx = _build_context(docs, top)
    prompt = (
        "You are a due diligence analyst.\n"
        "Answer the QUESTION using only the CONTEXT. If the context does not contain enough information, say it is not answerable.\n\n"
        "QUESTION:\n{question}\n\n"
        "CONTEXT:\n{context}\n\n"
        "ANSWER:"
    )

    llm = _lazy_llm()
    try:
        from langchain.prompts import PromptTemplate
        from langchain.chains import LLMChain
    except Exception:
        from langchain_core.prompts import PromptTemplate
        from langchain.chains import LLMChain

    chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template(prompt))
    raw = chain.predict(question=question.prompt, context=ctx).strip()

    scores = [s for s, _, _ in top]
    confidence = min(0.95, 0.35 + (max(scores) * 0.6))

    return RagAnswer(
        answer_text=raw,
        answerable=True,
        confidence=float(confidence),
        citations=citations,
    )

