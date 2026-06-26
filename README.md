# pdftodocxconverter

Локальный конвертер **PDF/HTML → DOCX** для запуска на Mac из IDE (Cursor).
Цель — отдать **редактируемый** Word-документ (настоящие абзацы, таблицы, стили —
не «текст-картинка»), максимально сохранив исходный вид.

Кладёшь файлы в `inputs/`, запускаешь `convert.py`, забираешь `.docx` из `outputs/`.

## Возможности

- Вход — **PDF** и **HTML**.
- Два движка: **`local`** (офлайн, `pdf2docx`) и **`adobe`** (облако Adobe PDF
  Services, выше точность на сложной вёрстке).
- HTML-исходники: автоматический фикс шрифтов (variable→static, встраивание
  Manrope) и рендер чистого PDF через headless Chrome.
- Постобработка DOCX: чистка пробелов и нормализация шрифтов.

## Требования

- **Python 3.11+**, **git**
- macOS / Linux / Windows (разрабатывается под macOS)

## Установка

```bash
git clone https://github.com/artmazloev/pdftodocxconverter.git
cd pdftodocxconverter
python3 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt                        # ядро
pip install -r requirements-html.txt                   # для HTML-входа (Chrome + fonttools)
pip install -r requirements-adobe.txt                  # для --engine adobe
playwright install chromium                            # браузер для HTML-рендера
python convert.py --help
```

> В Cursor/VS Code: `Cmd+Shift+P` → **Python: Select Interpreter** → `.venv/bin/python`.

## Использование

Положи **PDF или HTML** в `inputs/` и запусти:

```bash
python convert.py                      # все файлы из inputs/ (движок local)
python convert.py file.html --engine adobe          # один файл через Adobe
python convert.py --engine adobe --clean-svg-text   # + фикс подписей на картах
python convert.py --pages 0:5          # только первые 5 страниц
python convert.py --overwrite          # пересоздать существующие
python convert.py -v                   # подробный лог
```

Готовые `.docx` появятся в `outputs/`.

## Движки

| Движок | Где работает | Когда |
|---|---|---|
| `local` (по умолчанию) | Офлайн | Текстовые документы, письма, простые таблицы |
| `adobe` | **Облако Adobe** | Дизайнерская вёрстка, инфографика |

### Ключи Adobe (бесплатный тариф ~500/мес)

1. Получи Client ID / Client Secret: <https://developer.adobe.com/document-services/>
   (тип — OAuth Server-to-Server).
2. Положи ключи в `.env` в корне проекта:
   ```
   PDF_SERVICES_CLIENT_ID=...
   PDF_SERVICES_CLIENT_SECRET=...
   ```
   (или скачанный `pdfservices-api-credentials.json` в корень). Файлы с ключами
   уже в `.gitignore`.

## HTML на входе

Для документов, свёрстанных как HTML, подавай **сам HTML** — конвертер сам чинит
шрифты (вариативные → статические, встраивает Manrope при необходимости) и
рендерит чистый PDF через Chrome, затем конвертирует в DOCX.

```bash
python convert.py design.html --engine adobe --clean-svg-text
```

Полный рецепт — **[docs/HTML_TO_DOCX.md](docs/HTML_TO_DOCX.md)**. Почему искажаются
шрифты и как это лечится — **[docs/FONTS.md](docs/FONTS.md)**.

## Постобработка

После конвертации DOCX автоматически чистится (флаги `--no-postprocess`, `--font`):
чистка пробелов — всегда; нормализация шрифтов — только для `local` (для Adobe она
сломала бы спозиционированный макет). Запуск вручную на готовом DOCX:

```bash
python -m pdf2docx_converter.postprocess file.docx --no-normalize-fonts
```

## Структура проекта

```
convert.py                       # точка входа: inputs/ → outputs/ (PDF/HTML)
pdf2docx_converter/
  ├── analyzer.py                # цифровой PDF / скан
  ├── engine_local.py            # офлайн-движок (pdf2docx)
  ├── engine_adobe.py            # облачный движок (Adobe)
  ├── html_prep.py               # фикс шрифтов в HTML
  ├── postprocess.py             # нормализация шрифтов/пробелов в DOCX
  ├── config.py                  # настройки
  └── assets/                    # встроенный Manrope (OFL)
scripts/                         # smoke_test, html_to_pdf, make_static_fontface
docs/                            # ARCHITECTURE, HTML_TO_DOCX, FONTS
.github/                         # шаблоны issues/PR, CI
```

## Ограничения

- Локальный движок хорошо держит текстовые документы; для дизайнерских — `--engine adobe`.
- 100% визуальной точности **и** 100% редактируемости одновременно недостижимы:
  PDF — абсолютное позиционирование, DOCX — поток. Чем сложнее дизайн, тем сильнее
  компромисс.
- Сканы (текст = картинка) пока не поддерживаются (нужен OCR).

## Документация

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — архитектура, движки, решения
- [docs/HTML_TO_DOCX.md](docs/HTML_TO_DOCX.md) — полный путь HTML → DOCX через Adobe
- [docs/FONTS.md](docs/FONTS.md) — шрифты: причины искажений и фиксы
- [CONTRIBUTING.md](CONTRIBUTING.md) · [CHANGELOG.md](CHANGELOG.md)
