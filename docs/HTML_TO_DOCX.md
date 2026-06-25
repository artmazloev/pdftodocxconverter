# HTML → DOCX через Adobe (полный путь)

Пошаговый рецепт для дизайнерских документов, сверстанных как HTML (с встроенным
шрифтом). Конвейер: **HTML → авто-фикс шрифтов → Chrome (чистый PDF) → Adobe → DOCX.**

## 1. Обновить репу и поставить зависимости

```bash
cd pdftodocxconverter
git checkout main
git pull origin main

source .venv/bin/activate            # или создать: python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # ядро (pdf2docx, PyMuPDF, python-docx)
pip install -r requirements-html.txt     # HTML-вход: playwright + fonttools
pip install -r requirements-adobe.txt    # Adobe: pdfservices-sdk
playwright install chromium              # браузер для рендера HTML (один раз)
```

## 2. Получить бесплатные ключи Adobe (один раз)

1. <https://developer.adobe.com/document-services/> → **Get credentials**.
2. Тип аутентификации — **OAuth Server-to-Server**.
3. Скопируй **Client ID** и **Client Secret** (бесплатный тариф ~500 конвертаций/мес).

Пропиши ключи в файл `.env` в корне проекта (уже в `.gitignore`):

```
PDF_SERVICES_CLIENT_ID=твой_client_id
PDF_SERVICES_CLIENT_SECRET=твой_client_secret
```

> Вместо `.env` можно положить скачанный `pdfservices-api-credentials.json` в корень.

## 3. Сконвертировать

```bash
# положи .html в inputs/, затем:
python convert.py --engine adobe              # все html/pdf из inputs/
# или один файл:
python convert.py CANDIDATE_v8.html --engine adobe
# если на карте/в SVG подписи бьются пробелами («Г р у з и ю»):
python convert.py CANDIDATE_v8.html --engine adobe --clean-svg-text
```

Готовый DOCX появится в `outputs/`. Скрипт сам:
1. чинит шрифты: вариативные `@font-face` → статические инстансы (фикс Type3); а
   если шрифт (Manrope) только ссылается, но не встроен — **подставляет локальный
   Manrope** из `assets/` и убирает Google-Fonts ссылки (рендер офлайн);
2. (опц. `--clean-svg-text`) снимает обводку с SVG-текста, чтобы подписи карт не
   становились Type3;
3. отрендерит чистый PDF через headless Chrome;
4. прогонит его через Adobe;
5. сделает безопасную постобработку (для Adobe — только чистка пробелов, шрифты и
   макет не трогаются).

Подробнее про шрифты и причины искажений — [FONTS.md](FONTS.md).

## Что ожидать

- **Текст** — чистый и редактируемый, без склеенных слов и патчворка шрифтов.
- **Дизайн** — Adobe держит сложную вёрстку заметно лучше локального движка.
- **Остаётся компромисс формата:** часть инфографики (чарты, карты) — это
  графика без редактируемого эквивалента в Word; 100% «пиксель-в-пиксель + полностью
  редактируемо» недостижимо в принципе (см. [ARCHITECTURE](ARCHITECTURE.md)).

## Если нет ключей Adobe

Можно прогнать локальным движком (офлайн, бесплатно):

```bash
python convert.py CANDIDATE_v8.html          # --engine local по умолчанию
```

Текст будет чистый, но вёрстка дизайнерских страниц — грубее (ограничение
`pdf2docx`). Для дизайн-документов Adobe предпочтительнее.

## Только чистый PDF (без DOCX)

Если нужен лишь корректный PDF из HTML (например, чтобы загрузить в другой сервис):

```bash
python scripts/html_to_pdf.py design.html design.pdf
```
