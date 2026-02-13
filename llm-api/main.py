import asyncio

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from settings import settings
from generate_answer import my_actual_llm_generator_async

# 認証用のトークン
MY_SECRET_KEY = settings.MY_SECRET_KEY

app = FastAPI()


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

        # 4. 以降、通常の会話ループへ（対話履歴を保持）
        history: list[dict[str, str]] = []

        while True:
            data = await websocket.receive_json()
            user_prompt = data.get("prompt")

            if not user_prompt:
                await websocket.send_json({"error": "Prompt is required"})
                continue

            # LLM生成処理（対話履歴付き）
            full_response: list[str] = []
            async for chunk in my_actual_llm_generator_async(user_prompt, history):
                await websocket.send_json({"token": chunk})
                full_response.append(chunk)

            # 対話履歴を更新
            history.append({"role": "user", "content": user_prompt})
            history.append({"role": "assistant", "content": "".join(full_response)})

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
