# IGNF UI Kit

Kit interno reutilizável para apps desktop PySide6 da IGNF: sistema de
temas (claro/escuro, com logo SVG tintado automaticamente pela cor de
destaque) e sistema de idiomas (arquivos JSON com fallback), cada um com
um editor visual pronto (`ThemeEditorDialog`, `LangEditorDialog`) que
você embute no seu app — sem processo separado, sem subprocess.

## Instalação (modo editável, dentro de cada app)

No ambiente virtual do app:

```powershell
pip install -e ..\_shared\ignf_ui_kit
```

Assim, qualquer alteração feita aqui reflete automaticamente em todos os
apps que usam o kit, sem precisar reinstalar.

## Uso básico

### Temas

```python
from ignf_ui_kit.theming import ThemeCatalog, ThemeEditorDialog

catalog = ThemeCatalog(themes_dir=MY_APP_THEMES_DIR, default_slug="default")

# No app principal:
theme_data = catalog.load(current_slug)
stylesheet = catalog.render_style_sheet(theme_data["accent"], theme_data["background"])
window.setStyleSheet(stylesheet)

# Para abrir o editor visual:
dialog = ThemeEditorDialog(
    catalog=catalog,
    logo_svg_path=MY_APP_LOGO_SVG,
    active_accent=theme_data["accent"],
    active_background=theme_data["background"],
    extra_fields=[("developer", "Desenvolvedor")],
    preview_factory=my_preview_widget_factory,  # opcional
    strings=my_translated_strings,               # opcional
    parent=window,
)
dialog.exec()
```

### Idiomas

```python
from ignf_ui_kit.i18n import LanguageCatalog, LangEditorDialog

catalog = LanguageCatalog(lang_dir=MY_APP_LANG_DIR, fallback_code="en_US")
strings = catalog.get_strings(current_language_code)

dialog = LangEditorDialog(
    catalog=catalog,
    source_language_code="en_US",
    mymemory_source_code="en",
    strings=strings,
    parent=window,
)
dialog.exec()
```

## Convenção de logo SVG tintado

No arquivo `.svg`, pinte as partes que devem receber a cor do tema com
magenta puro — `#FF00FF` ou a palavra-chave CSS `fuchsia`/`magenta`.
`ignf_ui_kit.theming.svg_service.render_tinted_svg()` troca essa cor
pelo accent do tema atual antes de renderizar.

## O que cada app precisa fornecer

- Uma pasta própria de temas (`assets/themes/*.json`) e de idiomas
  (`assets/lang/*.json`) — o kit não assume nenhum caminho fixo.
- Campos extras de tema específicos do app (ex.: "desenvolvedor") via
  `extra_fields` — o kit não tem esse campo embutido.
- Um `preview_factory` (opcional) — uma função que retorna um `QWidget`
  com o método `apply_preview(style_vars: dict, logo_pixmap: QPixmap | None)`,
  usado pelo editor de temas pra mostrar a cara real do seu app. Se não
  fornecido, o editor mostra um preview genérico simples.
