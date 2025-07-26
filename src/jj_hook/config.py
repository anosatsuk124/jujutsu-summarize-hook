"""設定管理モジュール。"""

import os
from typing import Optional
from pydantic import BaseModel


class Config(BaseModel):
    """アプリケーション設定。"""
    
    # LiteLLM設定
    model: str = "gpt-3.5-turbo"
    max_tokens: int = 100
    temperature: float = 0.1
    prompt_language: str = "japanese"
    
    # 環境変数からの読み込み
    @classmethod
    def from_env(cls) -> "Config":
        """環境変数から設定を読み込む。"""
        return cls(
            model=os.environ.get("JJ_HOOK_MODEL", "gpt-3.5-turbo"),
            max_tokens=int(os.environ.get("JJ_HOOK_MAX_TOKENS", "100")),
            temperature=float(os.environ.get("JJ_HOOK_TEMPERATURE", "0.1")),
            prompt_language=os.environ.get("JJ_HOOK_LANGUAGE", "japanese"),
        )