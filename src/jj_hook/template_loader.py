"""テンプレート読み込みモジュール。"""

import os
from pathlib import Path
from typing import Optional


class TemplateLoader:
    """プロンプトテンプレートを読み込み、変数を置換するクラス。"""

    def __init__(self, templates_dir: Optional[Path] = None):
        """初期化。"""
        if templates_dir is None:
            # デフォルトはこのファイルと同じディレクトリのtemplatesフォルダ
            self.templates_dir = Path(__file__).parent / "templates"
        else:
            self.templates_dir = templates_dir

    def load_template(self, template_name: str, **kwargs: str) -> str:
        """
        テンプレートを読み込み、変数を置換して返す。

        Args:
            template_name: テンプレートファイル名（拡張子なし）
            **kwargs: テンプレート内で置換する変数

        Returns:
            置換済みのテンプレート文字列
        """
        template_path = self.templates_dir / f"{template_name}.md"

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        # テンプレートファイルを読み込み
        with open(template_path, encoding="utf-8") as f:
            template_content = f.read()

        # 言語を自動取得・capitalize
        language = os.environ.get("JJ_HOOK_LANGUAGE", "english").capitalize()

        # デフォルト変数を設定
        variables = {"language": language, **kwargs}

        # 変数を置換
        try:
            return template_content.format(**variables)
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")

    def get_language_instruction(self) -> str:
        """言語指定文を取得する。"""
        language = os.environ.get("JJ_HOOK_LANGUAGE", "english").capitalize()
        return f"Please respond in {language}."


# デフォルトのテンプレートローダーインスタンス
template_loader = TemplateLoader()


def load_template(template_name: str, **kwargs: str) -> str:
    """
    テンプレートを読み込む便利関数。

    Args:
        template_name: テンプレートファイル名（拡張子なし）
        **kwargs: テンプレート内で置換する変数

    Returns:
        置換済みのテンプレート文字列
    """
    return template_loader.load_template(template_name, **kwargs)


def get_language_instruction() -> str:
    """言語指定文を取得する便利関数。"""
    return template_loader.get_language_instruction()
