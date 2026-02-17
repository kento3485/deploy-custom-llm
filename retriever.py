from __future__ import annotations

import asyncio
import functools
from collections.abc import AsyncGenerator
from typing import Any

from elasticsearch import Elasticsearch
from openai import AsyncOpenAI, OpenAI

from settings import settings

EMBEDDING_MODEL = "text-embedding-ada-002"
CHAT_MODEL = "gpt-4o"
ES_INDEX = "geriatric_medicine_and_gerontology"

# 最後に取得された文書数を追跡するためのグローバル変数
_last_retrieved_count = 0

ES_USER = settings.ELASTIC_USER
ES_PASSWORD = settings.ELASTIC_PASSWORD
ES_HOST = settings.ELASTIC_IP
ES_PORT = settings.ELASTIC_PORT
ES_URL = f"https://{ES_HOST}:{ES_PORT}"

# NOTE: verify_certs=False is fine for local/dev over self-signed certs.
# For production, provide a CA bundle and set verify_certs=True.
es = Elasticsearch([ES_URL], basic_auth=(ES_USER, ES_PASSWORD), verify_certs=False)

oa = OpenAI(api_key=settings.OPENAI_API_KEY)
oa_async = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def get_real_data_path(filename: str) -> str:
    """Return the full path to a data file given its filename."""

    # base_dir = "/"

    # return os.path.join(base_dir, filename[44:])
    return "No path info(future work)"


def embed_text(text: str) -> list[float]:
    """Return a vector embedding for the given text.

    The embedding model is configured via EMBEDDING_MODEL.
    """
    resp = oa.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return resp.data[0].embedding


def index_text(content: str, *, metadata: dict[str, Any] | None = None) -> None:
    """Index a single text document with its embedding vector.

    Fields:
      - text: raw content
      - vector: dense embedding for ANN search
      - metadata: optional arbitrary metadata (e.g., source)
    """
    vector = embed_text(content)
    doc: dict[str, Any] = {"text": content, "vector": vector}
    if metadata:
        doc["metadata"] = metadata

    # ES Python client v8+: prefer 'document=' over 'body=' where possible.
    es.index(index=ES_INDEX, document=doc)


def semantic_search(query: str, *, top_k: int = 3) -> list[dict[str, Any]]:
    """Retrieve top_k most similar documents via cosine similarity on 'vector' field.

    Returns a list of _source dicts with at least {'text': str, ...}.
    """
    query_vec = embed_text(query)

    # script_score w/ cosineSimilarity over dense_vector field 'vector'
    body = {
        "query": {
            "script_score": {
                "query": {"match_all": {}},
                "script": {
                    "source": "cosineSimilarity(params.qvec, 'vector') + 1.0",
                    "params": {"qvec": query_vec},
                },
            },
        },
        "size": top_k,
        "_source": ["text", "metadata.source", "metadata"],  # keep flexible
    }

    try:
        res = es.search(index=ES_INDEX, body=body)
        hits = res.get("hits", {}).get("hits", [])
        results = [h.get("_source", {}) for h in hits]

        # 取得文書数を記録
        global _last_retrieved_count
        _last_retrieved_count = len(results)

        return results
    except Exception as exc:  # pragma: no cover (log/monitor in production)
        print(f"[semantic_search] error: {exc!s}")
        # エラー時は取得文書数を0にリセット
        _last_retrieved_count = 0
        return []


def generate_answer(
    query: str,
    context_snippets: list[str],
    sources: list[str] | None = None,
    generate_sources: bool = False,
) -> str:
    """Produce an answer using CHAT_MODEL, grounded on the provided context snippets."""
    context_section = ""
    context_instruction = ""
    if context_snippets:
        context_block = "\n\n".join(context_snippets)
        context_section = f"""
CONTEXT:
{context_block}
"""
        context_instruction = "- Prefer facts supported by the CONTEXT.\n"
    prompt = f"""
You are a precise assistant. Use the CONTEXT when possible; if missing, say so.
{context_section}
QUESTION:
{query}

INSTRUCTIONS:
{context_instruction}- Be concise and directly answer the question.

ANSWER:
"""

    resp = oa.responses.create(
        model=CHAT_MODEL,
        input=[
            {"role": "system", "content": "You are a helpful and accurate assistant."},
            {"role": "user", "content": prompt},
        ],
    )

    if generate_sources and sources is not None and len(sources) > 0:
        result = ""
        result += resp.output_text
        result += "\n\n## SOURCES\n"
        unique_sources = list(set(sources))
        for src in unique_sources:
            result += f"- {get_real_data_path(src)}\n"

        return result
    return resp.output_text


async def generate_answer_stream(
    query: str,
    context_snippets: list[str],
    sources: list[str] | None = None,
    generate_sources: bool = False,
) -> AsyncGenerator[str, None]:
    """Streaming version of generate_answer. Yields text chunks as they arrive."""
    context_section = ""
    context_instruction = ""
    if context_snippets:
        context_block = "\n\n".join(context_snippets)
        context_section = f"""
CONTEXT:
{context_block}
"""
        context_instruction = "- Prefer facts supported by the CONTEXT.\n"
    prompt = f"""
You are a precise assistant. Use the CONTEXT when possible; if missing, say so.
{context_section}
QUESTION:
{query}

INSTRUCTIONS:
{context_instruction}- Be concise and directly answer the question.

ANSWER:
"""

    stream = await oa_async.responses.create(
        model=CHAT_MODEL,
        input=[
            {"role": "system", "content": "You are a helpful and accurate assistant."},
            {"role": "user", "content": prompt},
        ],
        stream=True,
    )

    async for event in stream:
        if event.type == "response.output_text.delta":
            yield event.delta

    if generate_sources and sources is not None and len(sources) > 0:
        yield "\n\n## SOURCES\n"
        unique_sources = list(set(sources))
        for src in unique_sources:
            yield f"- {get_real_data_path(src)}\n"


async def run_rag_stream(query: str, *, k: int = 3) -> AsyncGenerator[str, None]:
    """Async streaming version of run_rag. Yields text chunks as they arrive.

    1. Retrieve top-k similar docs (offloaded to thread)
    2. Feed them as context into the LLM
    3. Yield grounded answer chunks
    """
    docs = await asyncio.to_thread(functools.partial(semantic_search, query, top_k=k))
    context = [d.get("text", "") for d in docs if d.get("text")]
    sources = [d.get("metadata", {}).get("source", "unknown") for d in docs]
    async for chunk in generate_answer_stream(
        query, context, sources=sources, generate_sources=True
    ):
        yield chunk


def llm_answer(query: str) -> str:
    """Produce an answer with the base LLM only (no RAG)."""
    resp = oa.responses.create(
        model=CHAT_MODEL,
        input=[
            {"role": "system", "content": "You are a helpful and accurate assistant."},
            {"role": "user", "content": query},
        ],
    )
    return resp.output_text


def run_rag(query: str, *, k: int = 3) -> str:
    """End-to-end RAG:

    1. Retrieve top-k similar docs
    2. Feed them as context into the LLM
    3. Return grounded answer
    """
    docs = semantic_search(query, top_k=k)
    context = [d.get("text", "") for d in docs if d.get("text")]
    sources = [d.get("metadata", {}).get("source", "unknown") for d in docs]
    return generate_answer(query, context, sources=sources, generate_sources=True)


def get_last_retrieved_count() -> int:
    """最後に取得された文書数を返す"""
    global _last_retrieved_count
    return _last_retrieved_count


def compare_rag_vs_vanilla(query: str, *, k: int = 3) -> str:
    """Compare answers:

    - Standard LLM (no retrieval)
    - RAG (retrieval + generation)
    """
    lines: list[str] = []
    lines.append(f"Query: {query}")
    lines.append("-" * 100)

    vanilla = llm_answer(query)
    lines.append("[Standard LLM]")
    lines.append(vanilla)
    lines.append("")

    lines.append("-" * 100)
    rag_ans = run_rag(query, k=k)
    lines.append("[RAG Answer]")
    lines.append(rag_ans)
    lines.append("")

    result = "\n".join(lines)
    print(result)
    return result


def debug_es_state() -> None:
    print("== ES quick check ==")
    try:
        if not es.indices.exists(index=ES_INDEX):
            print(f"Index '{ES_INDEX}' does not exist.")
            return
        cnt = es.count(index=ES_INDEX)["count"]
        print(f"Doc count: {cnt}")

        mapping = es.indices.get_mapping(index=ES_INDEX)
        props = mapping[ES_INDEX]["mappings"].get("properties", {})
        vmap = props.get("vector", {})
        print("vector mapping:", vmap)

        if cnt > 0:
            hit = es.search(index=ES_INDEX, size=1, query={"match_all": {}})
            src = hit["hits"]["hits"][0]["_source"]
            print("Sample _source keys:", list(src.keys()))
            print("Sample text head:", (src.get("text") or "")[:120])
            if "vector" in src and isinstance(src["vector"], list):
                print("Sample vector dim:", len(src["vector"]))
    except Exception as e:
        print("debug_es_state error:", e)


def debug_semantic_search(query: str, k: int = 3) -> None:
    docs = semantic_search(query, top_k=k)
    print(f"semantic_search hits: {len(docs)}")
    for i, d in enumerate(docs, 1):
        t = (d.get("text") or "")[:120].replace("\n", " ")
        print(f"[{i}] text≒ {t!r}")


if __name__ == "__main__":
    debug_es_state()
    debug_semantic_search("geriatric medicine", k=3)
    sample_query = "Tell me about bidding bots."

    for src in semantic_search(sample_query, top_k=3):
        print("----")
        print(src.get("text", "")[:400])

    compare_rag_vs_vanilla(sample_query)
