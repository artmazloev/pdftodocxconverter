# pdftodocxconverter

Локальный конвертер **PDF → DOCX** для запуска на Mac из IDE (Cursor).
Сохраняет визуальный дизайн оригинала и отдаёт **полностью редактируемый**
Word-документ (настоящие абзацы, таблицы, стили, картинки — не «текст-картинка»).

Работает **полностью локально**, без отправки файлов в облако.

## Как это работает

Ядро — библиотека [`pdf2docx`](https://github.com/dothinking/pdf2docx) (поверх
PyMuPDF): она анализирует layout страницы и пересобирает его в поток Word.
Режим — **гибридный**: текст идёт обычным редактируемым потоком, а абсолютное
позиционирование (плавающие фреймы) применяется только там, где иначе макет
не передать.

> ⚠️ Поддерживаются только **цифровые PDF** (с текстовым слоем). Отсканированные
> документы (текст = картинка) определяются автоматически и пропускаются —
> для них нужен OCR, которого пока нет.

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

## Структура проекта

```
pdftodocxconverter/
├── convert.py                  # точка входа: inputs/ → outputs/
├── requirements.txt
├── inputs/                     # сюда кладёшь PDF (содержимое в git не попадает)
├── outputs/                    # сюда падают DOCX
└── pdf2docx_converter/
    ├── analyzer.py             # проверка: цифровой PDF или скан
    ├── engine_local.py         # обёртка над pdf2docx
    └── config.py               # настройки качества/точности
```

## Точность

На цифровых PDF хорошо сохраняются: шрифты, размеры, цвета, простые таблицы,
картинки, базовый макет. Сложные места (возможны ручные правки): многоколоночные
макеты, вложенные таблицы, нестандартные шрифты, графика поверх текста. Параметры
тюнятся в `pdf2docx_converter/config.py`.

## Дальнейшие планы

- Тюнинг параметров качества под конкретные типы документов.
- Пост-обработка артефактов (`postprocess.py`).
- (Опц.) запасной движок на бесплатном тарифе Adobe PDF Services для сложных файлов.
- (Опц.) OCR для сканов.
