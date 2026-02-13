from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI
from elasticsearch import Elasticsearch

from settings import settings

# モデル・インデックス設定
EMBEDDING_MODEL = "text-embedding-ada-002"
CHAT_MODEL = "gpt-4o-mini"
ES_INDEX = "geriatric_medicine_and_gerontology"

# クライアント初期化
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

ES_URL = settings.ELASTICSEARCH_URL
ES_USER = settings.ELASTIC_USER
ES_PASSWORD = settings.ELASTIC_PASSWORD

if ES_USER and ES_PASSWORD:
    es = Elasticsearch([ES_URL], basic_auth=(ES_USER, ES_PASSWORD), verify_certs=False)
else:
    es = Elasticsearch([ES_URL])


# --- RAG ヘルパー関数 ---


async def _embed_text(text: str) -> list[float]:
    resp = await client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return resp.data[0].embedding


async def _semantic_search(query: str, *, top_k: int = 3) -> list[dict[str, Any]]:
    query_vec = await _embed_text(query)
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
        "_source": ["text", "metadata.source", "metadata"],
    }
    try:
        res = es.search(index=ES_INDEX, body=body)
        hits = res.get("hits", {}).get("hits", [])
        return [h.get("_source", {}) for h in hits]
    except Exception as exc:
        print(f"[semantic_search] error: {exc!s}")
        return []


def _format_history(history: list[dict[str, str]]) -> str:
    lines = []
    for msg in history:
        role = "ユーザー" if msg["role"] == "user" else "AI"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


async def _rewrite_and_judge(
    latest_message: str,
    history: list[dict[str, str]],
) -> tuple[bool, str]:
    """対話履歴と最新メッセージから、検索の要否判定とクエリ書き換えを同時に行う。

    Returns:
        (needs_search, rewritten_query)
    """
    history_text = _format_history(history)
    prompt = f"""あなたはクエリ分析アシスタントです。
以下の対話履歴と最新のユーザーメッセージを分析し、JSONで回答してください。

## 対話履歴
{history_text}

## 最新のメッセージ
{latest_message}

## タスク
1. 最新メッセージに回答するために、医療・老年医学のデータベース検索が必要かどうかを判定してください。
   - 挨拶、雑談、お礼、確認などは検索不要です。
   - 医療・健康に関する質問や、専門的な情報が必要な場合は検索が必要です。
2. 検索が必要な場合、対話履歴の文脈を踏まえて、データベース検索に適したスタンドアロンの質問文に書き換えてください。

## 出力形式（JSONのみ出力）
{{"needs_search": true/false, "query": "書き換えたクエリ（検索不要ならnull）"}}"""

    resp = await client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content.strip()
    try:
        result = json.loads(text)
        return result.get("needs_search", False), result.get("query") or latest_message
    except json.JSONDecodeError:
        return True, latest_message


async def my_actual_llm_generator_async(
    prompt: str,
    history: list[dict[str, str]] | None = None,
):
    """
    対話RAG対応の非同期ストリーミングジェネレータ。

    1. 対話履歴がある場合、クエリ書き換え＋検索要否判定を行う
    2. 検索が必要な場合のみElasticsearchから文脈を取得
    3. 対話履歴＋取得コンテキストでストリーミング回答生成

    Args:
        prompt: 最新のユーザーメッセージ
        history: 対話履歴 [{"role": "user"/"assistant", "content": "..."}]
    """
    if history is None:
        history = []

    # Step 1: クエリ書き換え＋検索要否判定
    needs_search = True
    search_query = prompt
    if history:
        try:
            needs_search, search_query = await _rewrite_and_judge(prompt, history)
        except Exception as e:
            print(f"Query rewrite failed, using original prompt: {e}")

    # Step 2: 必要な場合のみ検索してコンテキスト取得
    system_content = "You are a helpful and accurate assistant."
    if needs_search:
        try:
            docs = await _semantic_search(search_query, top_k=3)
            context = [d.get("text", "") for d in docs if d.get("text")]
            if context:
                context_block = "\n\n".join(context)
                system_content = f"""You are a helpful and accurate assistant.
Use the following CONTEXT from medical textbooks when possible.

CONTEXT:
{context_block}

INSTRUCTIONS:
- Prefer facts supported by the CONTEXT.
- Be concise and directly answer the question."""
        except Exception as e:
            print(f"Elasticsearch unavailable, falling back to direct LLM: {e}")

    # Step 3: 対話履歴＋最新メッセージでストリーミング回答生成
    messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})

    try:
        stream = await client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            stream=True,
        )

        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content is not None:
                yield content

    except Exception as e:
        print(f"Error: {e}")
        yield f"[System Error: {str(e)}]"
