from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings

"""
~~~~~~~~~~ 注意 ~~~~~~~~~~
以下のコードは.envファイルの内容を元にして環境変数を設定するためのものです。
以下のコードを編集する代わりに、.env.exampleファイルと.env.local.exampleファイルを参考にして
.envファイルと.env.localファイルを各自で作成して環境変数を設定してください。
API keyやパスワードなどの機密情報は絶対にpythonファイルに直接書いたり、GitHub上にアップロードしないでください。
"""


class Settings(BaseSettings):
    MY_SECRET_KEY: str = Field(
        default="sk-your-secret-api-key",
        env="MY_SECRET_KEY",
        description="API key for authenticating requests",
    )
    OPENAI_API_KEY: str = Field(
        default="sk-your-openai-api-key",
        env="OPENAI_API_KEY",
        description="OpenAI API key for accessing OpenAI services",
    )
    WEBSOCKETS_URL_LOCAL: str = Field(
        default="ws://localhost:8000/llm/ws",
        env="WEBSOCKETS_URL_LOCAL",
        description="WebSocket URL for local development",
    )
    WEBSOCKETS_URL: str = Field(
        default="wss://dummy.onrender.com/llm/ws",
        env="WEBSOCKETS_URL",
        description="WebSocket URL for production",
    )
    ELASTIC_PASSWORD: Annotated[
        str,
        Field(
            default="elastic_password",
            description="ElasticSearch Password",
        ),
    ]
    ELASTIC_USER: Annotated[
        str,
        Field(default="elastic", description="ElasticSearch User"),
    ]
    ELASTIC_IP: Annotated[
        str,
        Field(default="es01", description="ElasticSearch IP"),
    ]
    ELASTIC_PORT: Annotated[
        str,
        Field(default="9200", description="ElasticSearch Port"),
    ]

    class Config:
        env_file = ".env"


settings = Settings()
