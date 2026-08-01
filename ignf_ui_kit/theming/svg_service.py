"""Renderizacao de logos SVG tintados por uma cor de destaque (accent).

Convencao: no arquivo .svg, as partes que devem receber a cor do tema
(o simbolo/marca do app) devem usar magenta puro como fill -- seja como
#FF00FF (hex) ou como as palavras-chave CSS "fuchsia"/"magenta" (o
CorelDRAW costuma exportar dessa forma). Qualquer uma dessas formas e
reconhecida e trocada pelo hex de destaque atual antes de renderizar.

Partes que devem permanecer neutras (ex.: um texto do logotipo) devem
usar a cor final desejada normalmente, sem o marcador.
"""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PLACEHOLDER_HEX = "#FF00FF"
PLACEHOLDER_KEYWORDS = ("fuchsia", "magenta")

_PLACEHOLDER_PATTERN = re.compile(
    r"#ff00ff|" + "|".join(PLACEHOLDER_KEYWORDS),
    re.IGNORECASE,
)

# SVG Fonts (<font>/@font-face embutidos) sao um recurso antigo do SVG 1.1
# mal suportado pelo QSvgRenderer -- costuma sobrar no arquivo exportado do
# CorelDRAW mesmo depois de converter o texto em curvas (o Qt tenta
# processar mesmo sem uso, gerando avisos tipo "QFont::setPointSize: Point
# size <= 0"). Seguro remover: nao afeta nenhum path/forma vetorial.
_FONT_BLOCK_PATTERN = re.compile(r"<font[\s\S]*?</font>", re.IGNORECASE)
_FONT_FACE_CSS_PATTERN = re.compile(r"@font-face\s*\{[^}]*\}", re.IGNORECASE)


def is_svg(path: Path) -> bool:
    return path.suffix.lower() == ".svg"


def _strip_embedded_fonts(svg_text: str) -> str:
    text = _FONT_BLOCK_PATTERN.sub("", svg_text)
    text = _FONT_FACE_CSS_PATTERN.sub("", text)
    return text


def _tint_svg_text(svg_text: str, accent_hex: str) -> str:
    return _PLACEHOLDER_PATTERN.sub(accent_hex, svg_text)


def render_tinted_svg(svg_path: Path, accent_hex: str, target_width: int | None = None) -> QPixmap | None:
    """Le o SVG, remove fontes SVG incorporadas (nao suportadas/sem uso
    apos converter texto em curvas), troca o marcador de cor
    (fuchsia/magenta/#FF00FF) pelo accent informado e rasteriza. Retorna
    None se o arquivo nao existir ou nao puder ser lido/renderizado.
    """
    if not svg_path.exists():
        return None
    try:
        svg_text = svg_path.read_text(encoding="utf-8")
    except Exception:
        return None

    cleaned_text = _strip_embedded_fonts(svg_text)
    tinted_text = _tint_svg_text(cleaned_text, accent_hex)

    renderer = QSvgRenderer(QByteArray(tinted_text.encode("utf-8")))
    if not renderer.isValid():
        return None

    default_size = renderer.defaultSize()
    if default_size.isEmpty():
        default_size = QSize(420, 120)

    if target_width:
        scale = target_width / default_size.width()
        size = QSize(target_width, max(1, int(default_size.height() * scale)))
    else:
        size = default_size

    pixmap = QPixmap(size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    # Passar o retangulo de destino explicitamente e essencial: sem isso,
    # o QSvgRenderer pode desenhar no tamanho "nativo" do documento SVG em
    # vez de encaixar no pixmap que criamos, cortando o que sobra da
    # imagem (sintoma classico: logo aparece cortado/faltando pedaco).
    renderer.render(painter, QRectF(0, 0, size.width(), size.height()))
    painter.end()
    return pixmap
