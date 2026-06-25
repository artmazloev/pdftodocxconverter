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

1. Положи PDF-файлы в папку `inputs/`.
2. Запусти скрипт:

```bash
python convert.py                 # сконвертировать все PDF из inputs/
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

## Постобработка: нормализация шрифтов

Дизайнерские PDF часто используют Type3-шрифты без имени. Любой конвертер
(включая Adobe) тогда **угадывает шрифт по каждому глифу** — одно слово разрывается
на куски в разных шрифтах, половина из которых не установлена в системе, и текст
искажается. Плюс межбуквенный кернинг превращается в лишние пробелы.

После конвертации скрипт **автоматически** прогоняет постобработку:
- сводит все «угаданные» текстовые шрифты к одному (по умолчанию `Arial`),
  сохраняя символьные/иконочные шрифты;
- схлопывает множественные пробелы и убирает пробелы перед пунктуацией;
- склеивает соседние одинаковые фрагменты (чище для редактирования).

```bash
python convert.py --engine adobe                 # постобработка включена по умолчанию
python convert.py --engine adobe --font "Helvetica Neue"   # свой целевой шрифт
python convert.py --no-postprocess               # отключить
```

Можно прогнать на **уже готовом** DOCX (например, полученном вручную через Adobe):

```bash
python -m pdf2docx_converter.postprocess outputs/file.docx --font "Arial"
```

> Ограничение: одиночные пробелы **внутри** слов (`«предел ах»`) автоматически
> не убираются — без словаря это рискует склеить реально разные слова. Множественные
> пробелы между словами чистятся надёжно.

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
