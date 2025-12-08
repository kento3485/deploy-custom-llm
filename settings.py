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

    class Config:
        env_file = ".env"


settings = Settings()
