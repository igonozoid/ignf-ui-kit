"""Catalogo de temas (claro/escuro + accent) genérico, reutilizavel entre apps.

Cada tema vive como um arquivo JSON numa pasta que o app fornece, no formato:

    {
      "_meta": {"name": "Verde"},
      "accent": "#00FF66",
      "background": "dark",
      "<qualquer campo extra que o app quiser>": "..."
    }

O slug (nome do arquivo, sem extensao) e o identificador estavel do tema.
"""
from __future__ import annotations

import importlib.resources as resources
import json
from pathlib import Path

DARK_PALETTE = {
    "bg": "#0D0D0D",
    "surface": "#1A1A1A",
    "surface_hover": "#262626",
    "border": "#333333",
    "text_primary": "#F2F2F2",
    "text_secondary": "#A3A3A3",
    "text_disabled": "#666666",
}

LIGHT_PALETTE = {
    "bg": "#F5F5F5",
    "surface": "#FFFFFF",
    "surface_hover": "#EDEDED",
    "border": "#DADADA",
    "text_primary": "#1A1A1A",
    "text_secondary": "#5C5C5C",
    "text_disabled": "#B0B0B0",
}

BACKGROUND_LABELS = {"dark": "Escuro", "light": "Claro"}


def get_palette(background: str) -> dict:
    """Retorna a paleta completa (menos o accent) para 'dark' ou 'light'."""
    return dict(LIGHT_PALETTE if background == "light" else DARK_PALETTE)


def build_style_vars(accent: str, background: str) -> dict:
    """Combina a paleta base com o accent, pronto pra usar em str.format()."""
    palette = get_palette(background)
    palette["accent"] = accent
    return palette


class ThemeCatalog:
    def __init__(self, themes_dir: Path, default_slug: str = "default", qss_path: Path | None = None) -> None:
        self.themes_dir = Path(themes_dir)
        self.default_slug = default_slug
        # None = usa o base.qss embutido no proprio pacote (lido via
        # importlib.resources, que funciona tanto em execucao normal
        # quanto dentro de um .exe compilado com PyInstaller -- ao
        # contrario de Path(__file__), que quebra quando o modulo esta
        # zipado dentro do bundle).
        self.qss_path = Path(qss_path) if qss_path else None

    def list_available(self) -> dict[str, dict]:
        """Retorna {slug: {"name", "accent", "background", **extras}}."""
        themes: dict[str, dict] = {}
        if not self.themes_dir.exists():
            return themes
        for file_path in sorted(self.themes_dir.glob("*.json")):
            slug = file_path.stem
            data = self._read(file_path)
            if data is not None:
                themes[slug] = data
        return themes

    def load(self, slug: str) -> dict:
        file_path = self.themes_dir / f"{slug}.json"
        return self._read(file_path) or {}

    def _read(self, file_path: Path) -> dict | None:
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        result = {
            "name": raw.get("_meta", {}).get("name", file_path.stem),
            "accent": raw.get("accent", "#FF7A1A"),
            "background": raw.get("background", "dark"),
        }
        for key, value in raw.items():
            if key not in ("_meta", "accent", "background"):
                result[key] = value
        return result

    def save(self, slug: str, name: str, accent: str, background: str = "dark", extra: dict | None = None) -> None:
        self.themes_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.themes_dir / f"{slug}.json"
        payload = {"_meta": {"name": name}, "accent": accent, "background": background}
        if extra:
            payload.update(extra)
        file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def display_label(self, slug: str, data: dict, strings: dict | None = None) -> str:
        """Nome de exibicao com o modo de fundo entre parenteses, ex.:
        'Verde (Escuro)'. Usa as chaves de traducao 'theme_<slug>' e
        'theme_background_<dark|light>' quando disponiveis; cai pro nome
        salvo no arquivo (e pro rotulo em portugues) se nao houver tradução.
        """
        strings = strings or {}
        background = data.get("background", "dark")
        name = strings.get(f"theme_{slug}", data.get("name", slug))
        label = strings.get(f"theme_background_{background}", BACKGROUND_LABELS.get(background, background.capitalize()))
        return f"{name} ({label})"

    def _read_qss_template(self) -> str | None:
        if self.qss_path is not None:
            if not self.qss_path.exists():
                return None
            try:
                return self.qss_path.read_text(encoding="utf-8")
            except Exception:
                return None
        try:
            return resources.files("ignf_ui_kit.theming").joinpath("base.qss").read_text(encoding="utf-8")
        except Exception:
            return None

    def render_style_sheet(self, accent: str, background: str) -> str | None:
        """Le o base.qss (do app, se fornecido, senao o padrao embutido no
        kit) e formata com a paleta+accent informados."""
        template = self._read_qss_template()
        if template is None:
            return None
        try:
            return template.format(**build_style_vars(accent, background))
        except Exception:
            return None
