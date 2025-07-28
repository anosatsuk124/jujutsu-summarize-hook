"""テンプレート読み込みモジュール。"""

import os
from pathlib import Path
from typing import Optional


class TemplateLoader:
    """プロンプトテンプレートを読み込み、変数を置換するクラス。"""

    def __init__(self, templates_dir: Optional[Path] = None, vcs_type: Optional[str] = None):
        """初期化。"""
        if templates_dir is None:
            # デフォルトはこのファイルと同じディレクトリのtemplatesフォルダ
            self.base_templates_dir = Path(__file__).parent / "templates"
        else:
            self.base_templates_dir = templates_dir

        self.vcs_type = vcs_type

    def load_template(self, template_name: str, **kwargs: str) -> str:
        """
        テンプレートを読み込み、変数を置換して返す。
        VCS固有 → 共通の順で検索する。

        Args:
            template_name: テンプレートファイル名（拡張子なし）
            **kwargs: テンプレート内で置換する変数

        Returns:
            置換済みのテンプレート文字列
        """
        template_path = None

        # VCS固有のテンプレートを優先的に検索
        if self.vcs_type:
            vcs_specific_path = self.base_templates_dir / self.vcs_type / f"{template_name}.md"
            if vcs_specific_path.exists():
                template_path = vcs_specific_path

        # VCS固有が見つからない場合は共通テンプレートを検索
        if template_path is None:
            common_path = self.base_templates_dir / "common" / f"{template_name}.md"
            if common_path.exists():
                template_path = common_path

        # 従来の場所も検索（下位互換）
        if template_path is None:
            legacy_path = self.base_templates_dir / f"{template_name}.md"
            if legacy_path.exists():
                template_path = legacy_path

        if template_path is None:
            raise FileNotFoundError(
                f"Template not found: {template_name} (searched in VCS-specific, common, and legacy locations)"
            )

        # テンプレートファイルを読み込み
        with open(template_path, encoding="utf-8") as f:
            template_content = f.read()

        # 言語を自動取得・capitalize
        language = os.environ.get(
            "VCS_CC_HOOK_LANGUAGE",
            os.environ.get(
                "JJ_CC_HOOK_LANGUAGE", os.environ.get("GIT_CC_HOOK_LANGUAGE", "english")
            ),
        ).capitalize()

        # デフォルト変数を設定
        variables = {"language": language, **kwargs}

        # 変数を置換
        try:
            return template_content.format(**variables)
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")

    def get_language_instruction(self) -> str:
        """言語指定文を取得する。"""
        language = os.environ.get(
            "VCS_CC_HOOK_LANGUAGE",
            os.environ.get(
                "JJ_CC_HOOK_LANGUAGE", os.environ.get("GIT_CC_HOOK_LANGUAGE", "english")
            ),
        ).capitalize()
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
