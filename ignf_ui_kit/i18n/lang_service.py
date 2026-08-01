"""Catalogo de idiomas generico, reutilizavel entre apps.

Cada idioma vive como um arquivo JSON numa pasta que o app fornece, no
formato:

    {
      "_meta": {"name": "English (US)", "code": "en_US"},
      "add_button": "Add",
      ...
    }
"""
from __future__ import annotations

import json
from pathlib import Path


class LanguageCatalog:
    def __init__(self, lang_dir: Path, fallback_code: str = "en_US") -> None:
        self.lang_dir = Path(lang_dir)
        self.fallback_code = fallback_code

    def list_available(self) -> dict[str, str]:
        """Retorna {codigo: nome_exibicao} lendo os arquivos *.json da pasta."""
        languages: dict[str, str] = {}
        if not self.lang_dir.exists():
            return languages
        for file_path in sorted(self.lang_dir.glob("*.json")):
            code = file_path.stem
            name = code
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                name = data.get("_meta", {}).get("name", code)
            except Exception:
                pass
            languages[code] = name
        return languages

    def load(self, code: str) -> dict[str, str]:
        file_path = self.lang_dir / f"{code}.json"
        if not file_path.exists():
            return {}
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self, code: str, name: str, values: dict[str, str]) -> None:
        self.lang_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.lang_dir / f"{code}.json"
        payload = {"_meta": {"name": name, "code": code}}
        payload.update(values)
        file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def display_name(self, code: str) -> str:
        return self.list_available().get(code, code)

    def get_strings(self, code: str) -> dict[str, str]:
        """Strings do idioma pedido, com fallback chave-a-chave para o
        idioma de referencia (fallback_code) quando faltar alguma chave
        (ex.: idioma novo/incompleto criado no editor).
        """
        fallback = self.load(self.fallback_code)
        if code == self.fallback_code:
            return dict(fallback)
        current = self.load(code)
        merged = dict(fallback)
        merged.update({key: value for key, value in current.items() if key != "_meta"})
        return merged
