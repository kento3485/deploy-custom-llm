# pip install fastapi "uvicorn[standard]" openai pydantic
import asyncio

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from openai import AsyncOpenAI
from pydantic import BaseModel

from settings import settings

# 認証用のトークン
MY_SECRET_KEY = settings.MY_SECRET_KEY
OPENAI_API_KEY = settings.OPENAI_API_KEY

app = FastAPI()

# クライアント初期化
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


class LLMRequest(BaseModel):
    prompt: str
    streaming: bool = False


# --- 共通ロジック ---


# async def my_actual_llm_generator_async(prompt: str):
#     """
#     OpenAIのストリームをラップする共通ジェネレータ。
#     """
#     try:
#         stream = await client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[{"role": "user", "content": prompt}],
#             stream=True,
#         )

#         async for chunk in stream:
#             content = chunk.choices[0].delta.content
#             if content is not None:
#                 yield content

#     except Exception as e:
#         print(f"Error: {e}")
#         yield f"[System Error: {str(e)}]"

async def my_actual_llm_generator_async(prompt: str):
    # ダミーのストリーム生成器（実際にはOpenAIのストリームを使用）
    results = f"This is a simulated response from the LLM. You said: {prompt}"
    for char in results:
        await asyncio.sleep(0.1)  # 擬似的な遅延
        yield char

def verify_token(token: str) -> bool:
    """トークン検証用ヘルパー関数"""
    return token == MY_SECRET_KEY


# --- WebSocket エンドポイント ---


@app.websocket("/llm/ws")
async def websocket_endpoint(websocket: WebSocket):
    # 1. まず接続を受け入れる (まだ認証していない状態)
    await websocket.accept()

    try:
        # 2. クライアントからの「最初のメッセージ」を認証情報として待ち受ける
        # タイムアウトを設定するのがベストプラクティス（例: 5秒以内に認証こなければ切断）
        initial_message = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)

        token = initial_message.get("token")

        # 3. トークン検証
        if not token or not verify_token(token):
            # 認証失敗：エラーを送って切断
            await websocket.send_json({"error": "Authentication failed"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # 認証成功通知（オプション）
        await websocket.send_json({"status": "authenticated"})

        # 4. 以降、通常の会話ループへ
        while True:
            data = await websocket.receive_json()
            user_prompt = data.get("prompt")

            if not user_prompt:
                await websocket.send_json({"error": "Prompt is required"})
                continue

            # LLM生成処理
            async for chunk in my_actual_llm_generator_async(user_prompt):
                await websocket.send_json({"token": chunk})

            await websocket.send_json({"status": "done"})

    except asyncio.TimeoutError:
        # 認証待ちタイムアウト
        print("Authentication timed out")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)

    except WebSocketDisconnect:
        print("Client disconnected")

    except Exception as e:
        print(f"Error: {e}")
        # 接続がまだ生きているならエラーを送る
        try:
            await websocket.send_json({"error": str(e)})
        except:  # noqa: E722
            pass
