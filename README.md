# pdftodocxconverter

Локальный конвертер **PDF → DOCX** для запуска на Mac из IDE (Cursor).
Цель — отдать **редактируемый** Word-документ (настоящие абзацы, таблицы, стили —
не «текст-картинка»), максимально сохранив исходный вид.

Есть два движка:
- **`local`** (по умолчанию) — полностью офлайн, на базе `pdf2docx`. Хорош для
  текстовых документов.
- **`adobe`** — облачный (Adobe PDF Services), выше точность на сложной вёрстке.
  Загружает файл в облако Adobe.

## Как это работает

```
PDF → анализ (цифровой / скан) → движок (local | adobe) → DOCX
```

- **Локальный движок** — [`pdf2docx`](https://github.com/dothinking/pdf2docx)
  (поверх PyMuPDF): анализирует layout страницы и пересобирает его в поток Word.
  Гибридный режим: текст идёт обычным редактируемым потоком, абсолютные фреймы —
  только там, где иначе макет не передать.
- **Облачный движок** — Adobe Export PDF: заметно лучше держит сложную
  дизайнерскую вёрстку и нестандартные (Type3) шрифты. См. раздел
  [«Движки конвертации»](#движки-конвертации).

> ⚠️ Сейчас поддерживаются **цифровые PDF** (с текстовым слоем). Сканы
> (текст = картинка) локальный движок определяет и пропускает — для них нужен OCR,
> которого пока нет. Подробнее об ограничениях — в разделе
> [«Точность и ограничения»](#точность-и-ограничения).

## Требования

- **Python 3.11+** (`python3 --version`)
- **git**
- macOS / Linux / Windows (разрабатывается под macOS)

## Клонирование и развёртывание

```bash
# 1. Клонировать репозиторий
git clone https://github.com/artmazloev/pdftodocxconverter.git
cd pdftodocxconverter

# 2. Создать и активировать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate

# 3. Установить зависимости
pip install --upgrade pip
pip install -r requirements.txt

# 4. Проверить, что всё встало
python convert.py --help
```

После этого положи PDF в `inputs/` и запусти `python convert.py` — DOCX появятся в `outputs/`.

> Активная разработка идёт в ветке `claude/wonderful-goldberg-b9jfz7`. Чтобы взять
> её: `git clone ... && cd pdftodocxconverter && git checkout claude/wonderful-goldberg-b9jfz7`.

### Настройка в Cursor / VS Code

1. Открой папку проекта.
2. `Cmd+Shift+P` → **Python: Select Interpreter** → выбери `.venv/bin/python`.
3. Открой `convert.py` и нажми ▶ **Run** — обработает все PDF из `inputs/`.

## Использование

1. Положи **PDF или HTML** файлы в папку `inputs/` (HTML — см. раздел ниже).
2. Запусти скрипт:

```bash
python convert.py                 # сконвертировать все PDF/HTML из inputs/
python convert.py report.pdf      # только один файл из inputs/
python convert.py --pages 0:5     # только первые 5 страниц (0-based, end-exclusive)
python convert.py --overwrite     # пересоздать, даже если DOCX уже есть
python convert.py -v              # подробный лог
```

3. Готовые `.docx` появятся в `outputs/`.

Запуск прямо из Cursor: открой `convert.py` и нажми ▶ Run — он обработает всё из `inputs/`.

## Движки конвертации

| Движок | Где работает | Когда использовать |
|---|---|---|
| `local` (по умолчанию) | Полностью офлайн | Текстовые документы, письма, простые таблицы |
| `adobe` | **Облако Adobe** | Сложная дизайнерская вёрстка, инфографика, Type3-шрифты |

```bash
python convert.py --engine local      # офлайн (по умолчанию)
python convert.py --engine adobe      # облако Adobe, выше точность
```

> ⚠️ Локальный движок (`pdf2docx`) плохо справляется с **дизайнерскими PDF**
> (инфографика, чарты из векторных фигур, Type3-шрифты): графика превращается
> в кашу из картинок/таблиц, а текст местами склеивается. Для таких файлов
> используй `--engine adobe`.

## HTML на входе (рекомендуется для дизайнерских документов) ⭐

Если документ изначально собран как **HTML** (дизайн-шаблон/генератор) — подавай
в конвертер **сам HTML**, а не PDF. Скрипт сделает всё сам:

1. находит во встроенных `@font-face` **вариативные** шрифты и заменяет их на
   **статические инстансы** (по весам, которые реально используются в вёрстке);
2. рендерит HTML в чистый PDF через **headless Chrome** (правильные print-ключи);
3. конвертирует PDF → DOCX выбранным движком.

```bash
pip install -r requirements-html.txt   # playwright + fonttools (один раз)
playwright install chromium            # скачать браузер (один раз)

# просто положи .html в inputs/ и запусти:
python convert.py --engine adobe
# или один файл:
python convert.py design.html --engine adobe
```

**Зачем это нужно.** Chrome печатает **вариативные** шрифты в PDF как **Type3**
(контуры глифов без имени) → любой PDF→DOCX конвертер угадывает шрифт поглифно →
патчворк шрифтов и склеенные слова. **Статические** инстансы того же шрифта
embed'ятся как **Type0** (именованный subset) → текст чистый. Доказано на Manrope:
`font-weight: 200 800` (variable) → Type3 ❌; статические веса → Type0 ✅.
Метрики статического инстанса = метрики того же веса variable-шрифта, поэтому
**вёрстка не едет**.

### Отдельные скрипты (если нужно по шагам)

```bash
# вариативный шрифт → статический @font-face (CSS для вставки в свой генератор)
python scripts/make_static_fontface.py "Manrope[wght].ttf" \
    --family Manrope --weights 400 500 600 700 800 -o fontface.css

# HTML → PDF через Chrome
python scripts/html_to_pdf.py design.html design.pdf
```

### Настройка движка Adobe (бесплатный тариф)

Adobe PDF Services даёт **500 бесплатных конвертаций в месяц**. Документ при
этом **загружается в облако Adobe** — не используй для того, что не должно
покидать твою машину.

1. Получи бесплатные ключи: <https://developer.adobe.com/document-services/>
   (Get Started → создать Credentials → получишь `Client ID` и `Client Secret`).
2. Установи опциональную зависимость:
   ```bash
   pip install -r requirements-adobe.txt
   ```
3. Пропиши ключи одним из способов:
   - файл `.env` в корне проекта:
     ```
     PDF_SERVICES_CLIENT_ID=твой_client_id
     PDF_SERVICES_CLIENT_SECRET=твой_client_secret
     ```
   - либо положи скачанный из консоли `pdfservices-api-credentials.json` в корень.
   - либо экспортируй переменные окружения с теми же именами.
4. Конвертируй:
   ```bash
   python convert.py --engine adobe
   ```

`.env` и `pdfservices-api-credentials.json` уже в `.gitignore` — ключи не утекут в репозиторий.

## Постобработка DOCX

Дизайнерские PDF часто используют Type3-шрифты без имени. Любой конвертер
(включая Adobe) тогда **угадывает шрифт по каждому глифу** — слово разрывается на
куски в разных шрифтах, часть из которых не установлена → текст искажается. Плюс
кернинг превращается в лишние пробелы.

Постобработка умеет две вещи:
1. **Чистка пробелов** (безопасно всегда) — схлопывает множественные пробелы,
   убирает пробелы перед пунктуацией.
2. **Нормализация шрифтов** (рискованно для fidelity-вёрстки) — сводит «угаданные»
   шрифты к одному (`--font`, по умолчанию `Arial`).

> ⚠️ **Важно про макет.** Нормализация шрифтов меняет метрики (ширину символов).
> В выводе Adobe текст лежит в абсолютно спозиционированных фреймах, подогнанных
> под исходные шрифты — после смены шрифта он перестаёт помещаться, и блоки
> «плывут». Поэтому:
> - для **`--engine local`** (потоковая вёрстка, фреймов нет) нормализация шрифтов
>   **включена** — безопасна и полезна;
> - для **`--engine adobe`** (макет на фреймах) автоматически делается **только
>   чистка пробелов**, шрифты сохраняются как есть.

```bash
python convert.py --engine local                 # чистка пробелов + шрифты
python convert.py --engine adobe                 # только чистка пробелов (макет цел)
python convert.py --no-postprocess               # отключить полностью
```

Ручной запуск на готовом DOCX:

```bash
# безопасно для Adobe-файла: только пробелы, шрифты не трогаем
python -m pdf2docx_converter.postprocess file.docx --no-normalize-fonts

# агрессивно (может сдвинуть макет): унификация шрифтов
python -m pdf2docx_converter.postprocess file.docx --font "Arial"
```

> Ограничение: одиночные пробелы **внутри** слов (`«предел ах»`) автоматически
> не убираются — без словаря это рискует склеить реально разные слова
> (см. [#13](https://github.com/artmazloev/pdftodocxconverter/issues/13)).

## Структура проекта

```
pdftodocxconverter/
├── convert.py                  # точка входа: inputs/ → outputs/
├── requirements.txt            # зависимости локального движка
├── requirements-adobe.txt      # доп. зависимость для --engine adobe
├── inputs/                     # сюда кладёшь PDF (содержимое в git не попадает)
├── outputs/                    # сюда падают DOCX
├── pdf2docx_converter/
│   ├── analyzer.py             # проверка: цифровой PDF или скан
│   ├── engine_local.py         # офлайн-движок (pdf2docx)
│   ├── engine_adobe.py         # облачный движок (Adobe PDF Services)
│   ├── postprocess.py          # нормализация шрифтов и пробелов в DOCX
│   ├── html_prep.py            # variable→static шрифты в HTML
│   └── config.py               # настройки качества/точности
├── scripts/
│   └── smoke_test.py           # e2e-проверка (используется в CI)
├── docs/
│   └── ARCHITECTURE.md         # архитектура, движки, решения
├── CONTRIBUTING.md             # процесс разработки
├── CHANGELOG.md                # история изменений
└── .github/                    # шаблоны issues/PR, CI
```

## Точность и ограничения

**Локальный движок** хорошо держит текстовые документы (письма, договоры, отчёты
с простыми таблицами): шрифты, размеры, цвета, базовый макет. Плохо держит
**дизайнерские PDF** — инфографику, чарты из векторных фигур, нестандартные
(Type3) шрифты: для таких файлов используй `--engine adobe`.

> ⚠️ 100% визуальной точности **и** 100% редактируемости одновременно
> недостижимы ни одним инструментом: PDF — формат с абсолютным позиционированием,
> DOCX — с потоковой вёрсткой. Чем сложнее дизайн, тем сильнее этот компромисс.

## Дальнейшие планы

- Тюнинг параметров качества под конкретные типы документов ([#5](https://github.com/artmazloev/pdftodocxconverter/issues/5)).
- Пост-обработка артефактов `postprocess.py` ([#6](https://github.com/artmazloev/pdftodocxconverter/issues/6)).
- OCR для сканов ([#8](https://github.com/artmazloev/pdftodocxconverter/issues/8)).

Полный план — [Roadmap #11](https://github.com/artmazloev/pdftodocxconverter/issues/11).
История изменений — [CHANGELOG.md](CHANGELOG.md). Архитектура — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
