"""Editor visual de temas, embutivel em qualquer app PySide6 (QDialog).

Uso tipico (dentro do app):

    dialog = ThemeEditorDialog(
        catalog=my_theme_catalog,
        logo_svg_path=MY_LOGO_SVG,
        active_accent=current_accent,
        active_background=current_background,
        extra_fields=[("developer", "Desenvolvedor")],
        preview_factory=my_preview_widget_factory,
        strings=my_translated_strings,
        parent=main_window,
    )
    dialog.exec()

Tambem pode rodar standalone (veja o padrao em cada app: um script fino
que monta o catalogo/paths e chama `run_standalone(...)`).
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .svg_service import is_svg, render_tinted_svg
from .theme_service import ThemeCatalog, build_style_vars


def slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in normalized).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "tema"


class SimplePreviewWidget(QWidget):
    """Preview generico usado quando o app nao fornece um preview_factory."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._sample_button = QPushButton("Botão de exemplo")
        self._sample_label = QLabel("Texto de exemplo")
        layout.addWidget(self._sample_label)
        layout.addWidget(self._sample_button)
        layout.addStretch(1)

    def apply_preview(self, style_vars: dict, logo_pixmap: QPixmap | None) -> None:
        self.setStyleSheet(
            f"""
            QWidget {{ background: {style_vars['bg']}; color: {style_vars['text_primary']}; }}
            QPushButton {{
                background: {style_vars['surface']};
                border: 1px solid {style_vars['border']};
                color: {style_vars['text_primary']};
                padding: 8px 14px;
                border-radius: 8px;
            }}
            QPushButton:hover {{ border-color: {style_vars['accent']}; color: {style_vars['accent']}; }}
            """
        )


class ThemeEditorDialog(QDialog):
    def __init__(
        self,
        catalog: ThemeCatalog,
        logo_svg_path: Path | None = None,
        active_accent: str = "#FF7A1A",
        active_background: str = "dark",
        extra_fields: list[tuple[str, str]] | None = None,
        preview_factory=None,
        strings: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._catalog = catalog
        self._logo_svg_path = Path(logo_svg_path) if logo_svg_path else None
        self._extra_fields = extra_fields or []
        self._strings = strings or {}
        self._current_slug: str | None = None
        self._accent = active_accent
        self._background = active_background
        self._extra_inputs: dict[str, QLineEdit] = {}

        self.setWindowTitle(self._tr("theme_editor_window_title", "Editor de Temas"))
        self.setModal(True)
        self.resize(880, 560)

        # Segue o tema ativo do app hospedeiro na hora de abrir.
        active_qss = self._catalog.render_style_sheet(active_accent, active_background)
        if active_qss:
            self.setStyleSheet(active_qss)

        root = QHBoxLayout(self)

        form_panel = QWidget()
        form_panel.setMaximumWidth(320)
        form_layout = QVBoxLayout(form_panel)

        form_layout.addWidget(QLabel(self._tr("theme_editor_existing_label", "Tema existente")))
        self.theme_combo = QComboBox()
        self._reload_theme_list()
        self.theme_combo.currentIndexChanged.connect(self._on_theme_selected)
        form_layout.addWidget(self.theme_combo)

        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(self._tr("theme_editor_name_placeholder", "Ex.: Roxo Neon"))
        form.addRow(self._tr("theme_editor_name_label", "Nome"), self.name_input)

        for field_key, field_label in self._extra_fields:
            field_input = QLineEdit()
            form.addRow(self._tr(f"theme_editor_{field_key}_label", field_label), field_input)
            self._extra_inputs[field_key] = field_input

        self.background_combo = QComboBox()
        self.background_combo.addItem(self._tr("theme_editor_background_dark_option", "Escuro"), "dark")
        self.background_combo.addItem(self._tr("theme_editor_background_light_option", "Claro"), "light")
        self.background_combo.currentIndexChanged.connect(self._on_background_changed)
        form.addRow(self._tr("theme_editor_background_label", "Fundo"), self.background_combo)

        color_row = QHBoxLayout()
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(32, 24)
        color_button = QPushButton(self._tr("theme_editor_choose_color", "Escolher cor"))
        color_button.clicked.connect(self.choose_color)
        color_row.addWidget(self.color_preview)
        color_row.addWidget(color_button)
        form.addRow(self._tr("theme_editor_accent_label", "Cor de destaque"), color_row)

        form_layout.addLayout(form)
        form_layout.addStretch(1)

        self.save_button = QPushButton(self._tr("theme_editor_save_button", "Salvar tema"))
        self.save_button.clicked.connect(self.save_current_theme)
        form_layout.addWidget(self.save_button)

        info_label = QLabel(f"{self._tr('theme_editor_files_saved_in', 'Arquivos salvos em:')}\n{self._catalog.themes_dir}")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888; font-size: 11px;")
        form_layout.addWidget(info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        form_layout.addWidget(buttons)

        root.addWidget(form_panel)

        self.preview_widget = (preview_factory or SimplePreviewWidget)()
        root.addWidget(self.preview_widget, 1)

        self._apply_preview()

    def _tr(self, key: str, fallback: str) -> str:
        return self._strings.get(key, fallback)

    # ------------------------------------------------------------------
    def _apply_preview(self) -> None:
        style_vars = build_style_vars(self._accent, self._background)
        self.color_preview.setStyleSheet(
            f"background: {self._accent}; border: 1px solid {style_vars['border']}; border-radius: 4px;"
        )

        logo_pixmap = None
        if self._logo_svg_path and is_svg(self._logo_svg_path):
            logo_pixmap = render_tinted_svg(self._logo_svg_path, self._accent, target_width=None)

        if hasattr(self.preview_widget, "apply_preview"):
            self.preview_widget.apply_preview(style_vars, logo_pixmap)

    def _reload_theme_list(self) -> None:
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        self.theme_combo.addItem(self._tr("theme_editor_new_theme", "Novo tema..."), "")
        for slug, data in self._catalog.list_available().items():
            self.theme_combo.addItem(self._catalog.display_label(slug, data, self._strings), slug)
        self.theme_combo.blockSignals(False)

    def _on_theme_selected(self, index: int) -> None:
        slug = self.theme_combo.itemData(index)
        if not slug:
            self._current_slug = None
            self.name_input.clear()
            for field_input in self._extra_inputs.values():
                field_input.clear()
            self._accent = "#FF7A1A"
            self._background = "dark"
            self.background_combo.setCurrentIndex(self.background_combo.findData("dark"))
            self._apply_preview()
            return
        data = self._catalog.load(slug)
        self._current_slug = slug
        self.name_input.setText(data.get("name", slug))
        for field_key, field_input in self._extra_inputs.items():
            field_input.setText(str(data.get(field_key, "")))
        self._accent = data.get("accent", "#FF7A1A")
        self._background = data.get("background", "dark")
        self.background_combo.blockSignals(True)
        self.background_combo.setCurrentIndex(self.background_combo.findData(self._background))
        self.background_combo.blockSignals(False)
        self._apply_preview()

    def _on_background_changed(self, index: int) -> None:
        self._background = self.background_combo.itemData(index)
        self._apply_preview()

    def choose_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self._accent), self, self._tr("theme_editor_choose_color_dialog", "Escolher cor de destaque")
        )
        if color.isValid():
            self._accent = color.name().upper()
            self._apply_preview()

    def save_current_theme(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, self.windowTitle(), self._tr("theme_editor_name_required", "Informe um nome para o tema."))
            return
        extra = {key: field.text().strip() for key, field in self._extra_inputs.items()}
        slug = self._current_slug or slugify(name)
        self._catalog.save(slug, name, self._accent, self._background, extra)
        self._reload_theme_list()
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == slug:
                self.theme_combo.setCurrentIndex(i)
                break
        QMessageBox.information(
            self,
            self.windowTitle(),
            self._tr("theme_editor_saved_message", 'Tema "{name}" salvo.').format(name=name),
        )


def run_standalone(
    catalog: ThemeCatalog,
    logo_svg_path: Path | None = None,
    active_accent: str = "#FF7A1A",
    active_background: str = "dark",
    extra_fields: list[tuple[str, str]] | None = None,
    preview_factory=None,
    strings: dict | None = None,
) -> None:
    """Helper pra rodar o editor como app standalone (python meu_script.py)."""
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = ThemeEditorDialog(
        catalog=catalog,
        logo_svg_path=logo_svg_path,
        active_accent=active_accent,
        active_background=active_background,
        extra_fields=extra_fields,
        preview_factory=preview_factory,
        strings=strings,
    )
    dialog.exec()
