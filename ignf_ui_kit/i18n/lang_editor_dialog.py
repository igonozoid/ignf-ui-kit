"""Editor visual de idiomas, embutivel em qualquer app PySide6 (QDialog).

Usa um idioma de referencia (source_language_code) como fonte das chaves
e permite auto-traducao via API gratuita MyMemory (sem necessidade de
chave de API).
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .lang_service import LanguageCatalog


def mymemory_lang(language_code: str) -> str:
    return language_code.split("_")[0].lower()


def translate_text(text: str, target_lang: str, source_lang: str) -> str:
    if not text.strip():
        return text
    params = urllib.parse.urlencode({"q": text, "langpair": f"{source_lang}|{target_lang}"})
    url = f"https://api.mymemory.translated.net/get?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        translated = payload.get("responseData", {}).get("translatedText", "")
        return translated or text
    except Exception:
        return text


class LangEditorDialog(QDialog):
    def __init__(
        self,
        catalog: LanguageCatalog,
        source_language_code: str,
        mymemory_source_code: str = "en",
        strings: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._catalog = catalog
        self._source_language_code = source_language_code
        self._mymemory_source_code = mymemory_source_code
        self._ui_strings = strings or {}
        self._source_data = catalog.load(source_language_code)
        self._current_code: str | None = None
        self._field_inputs: dict[str, QLineEdit] = {}

        self.setWindowTitle(self._tr("lang_editor_window_title", "Editor de Idiomas"))
        self.setModal(True)
        self.resize(760, 640)

        root = QVBoxLayout(self)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel(self._tr("lang_editor_language_label", "Idioma")))
        self.lang_combo = QComboBox()
        self._reload_lang_list()
        self.lang_combo.currentIndexChanged.connect(self._on_lang_selected)
        top_row.addWidget(self.lang_combo, 1)

        new_button = QPushButton(self._tr("lang_editor_new_language_button", "Novo idioma..."))
        new_button.clicked.connect(self.create_new_language)
        top_row.addWidget(new_button)
        root.addLayout(top_row)

        code_row = QFormLayout()
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText(self._tr("lang_editor_code_placeholder", "Ex.: fr_FR"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(self._tr("lang_editor_name_placeholder", "Ex.: Français"))
        code_row.addRow(self._tr("lang_editor_code_label", "Código"), self.code_input)
        code_row.addRow(self._tr("lang_editor_name_label", "Nome de exibição"), self.name_input)
        root.addLayout(code_row)

        translate_row = QHBoxLayout()
        auto_button = QPushButton(self._tr("lang_editor_auto_translate_button", "Auto-traduzir tudo (via MyMemory, gratuito)"))
        auto_button.clicked.connect(self.auto_translate_all)
        translate_row.addWidget(auto_button)
        translate_row.addStretch(1)
        root.addLayout(translate_row)

        note = QLabel(self._tr(
            "lang_editor_note",
            "A auto-tradução usa a API pública gratuita MyMemory. Revise sempre o resultado antes de salvar.",
        ))
        note.setWordWrap(True)
        note.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        fields_container = QWidget()
        self.fields_layout = QFormLayout(fields_container)
        scroll.setWidget(fields_container)
        root.addWidget(scroll, 1)

        self._build_fields()

        save_button = QPushButton(self._tr("lang_editor_save_button", "Salvar idioma"))
        save_button.clicked.connect(self.save_current_language)
        root.addWidget(save_button)

        info_label = QLabel(f"{self._tr('lang_editor_files_saved_in', 'Arquivos salvos em:')}\n{self._catalog.lang_dir}")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if self.lang_combo.count():
            self._on_lang_selected(0)

    def _tr(self, key: str, fallback: str) -> str:
        return self._ui_strings.get(key, fallback)

    # ------------------------------------------------------------------
    def _build_fields(self) -> None:
        while self.fields_layout.rowCount():
            self.fields_layout.removeRow(0)
        self._field_inputs.clear()
        for key in self._source_data:
            if key == "_meta":
                continue
            field = QLineEdit()
            self.fields_layout.addRow(key, field)
            self._field_inputs[key] = field

    def _reload_lang_list(self) -> None:
        self.lang_combo.blockSignals(True)
        self.lang_combo.clear()
        for code, display_name in self._catalog.list_available().items():
            self.lang_combo.addItem(f"{display_name} ({code})", code)
        self.lang_combo.blockSignals(False)

    def _on_lang_selected(self, index: int) -> None:
        code = self.lang_combo.itemData(index)
        if not code:
            return
        self._current_code = code
        data = self._catalog.load(code)
        self.code_input.setText(code)
        self.code_input.setEnabled(False)
        self.name_input.setText(data.get("_meta", {}).get("name", code))
        for key, field in self._field_inputs.items():
            field.setText(data.get(key, self._source_data.get(key, "")))

    def create_new_language(self) -> None:
        self._current_code = None
        self.code_input.clear()
        self.code_input.setEnabled(True)
        self.name_input.clear()
        for key, field in self._field_inputs.items():
            field.setText(self._source_data.get(key, ""))

    def auto_translate_all(self) -> None:
        code = self.code_input.text().strip() or self._current_code
        if not code:
            QMessageBox.warning(self, self.windowTitle(), self._tr("lang_editor_code_required", "Informe o código do idioma antes de traduzir."))
            return
        target = mymemory_lang(code)
        if target == self._mymemory_source_code:
            QMessageBox.information(
                self, self.windowTitle(),
                self._tr("lang_editor_source_no_translation_needed", "O idioma de origem não precisa de tradução."),
            )
            return

        total = len(self._field_inputs)
        for index, (key, field) in enumerate(self._field_inputs.items(), start=1):
            source_text = self._source_data.get(key, "")
            translated = translate_text(source_text, target, self._mymemory_source_code)
            field.setText(translated)
            QApplication.processEvents()
        QMessageBox.information(
            self, self.windowTitle(),
            self._tr("lang_editor_translation_done", "Tradução automática concluída. Revise os textos antes de salvar."),
        )

    def save_current_language(self) -> None:
        code = self.code_input.text().strip()
        name = self.name_input.text().strip()
        if not code or not name:
            QMessageBox.warning(self, self.windowTitle(), self._tr("lang_editor_code_name_required", "Preencha código e nome de exibição."))
            return

        values = {key: field.text() for key, field in self._field_inputs.items()}
        self._catalog.save(code, name, values)

        self._reload_lang_list()
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == code:
                self.lang_combo.setCurrentIndex(i)
                break
        self._current_code = code
        self.code_input.setEnabled(False)
        QMessageBox.information(
            self, self.windowTitle(),
            self._tr("lang_editor_saved_message", 'Idioma "{name}" salvo.').format(name=name),
        )


def run_standalone(
    catalog: LanguageCatalog,
    source_language_code: str,
    mymemory_source_code: str = "en",
    strings: dict | None = None,
) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = LangEditorDialog(
        catalog=catalog,
        source_language_code=source_language_code,
        mymemory_source_code=mymemory_source_code,
        strings=strings,
    )
    dialog.exec()
