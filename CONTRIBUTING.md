# Участие в разработке

Спасибо за вклад! Этот документ описывает, как устроена разработка проекта.

## Развёртывание

См. раздел [«Клонирование и развёртывание»](README.md#клонирование-и-развёртывание)
в README. Кратко:

```bash
git clone https://github.com/artmazloev/pdftodocxconverter.git
cd pdftodocxconverter
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Структура проекта

```
convert.py                  # точка входа: inputs/ → outputs/ (PDF/HTML), выбор движка
pdf2docx_converter/
  ├── analyzer.py           # детект цифровой PDF / скан
  ├── engine_local.py       # офлайн-движок (pdf2docx), по умолчанию
  ├── engine_adobe.py       # облачный движок (Adobe PDF Services)
  ├── html_prep.py          # фикс шрифтов в HTML (variable→static, инжект Manrope)
  ├── postprocess.py        # нормализация шрифтов/пробелов в DOCX
  ├── config.py             # настройки точности/качества
  └── assets/               # встроенный Manrope (OFL)
scripts/
  ├── smoke_test.py         # e2e-проверка (CI)
  ├── html_to_pdf.py        # HTML → PDF (headless Chrome)
  └── make_static_fontface.py
docs/                       # ARCHITECTURE, HTML_TO_DOCX, FONTS
.github/                    # шаблоны issues/PR, CI
```

Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/FONTS.md](docs/FONTS.md).

## Рабочий процесс (Git Flow)

1. Каждая задача = **issue**. Группировка по фазам через лейблы `phase:*`.
2. Ветки от `main`:
   - `feat/<кратко>` — новые возможности
   - `fix/<кратко>` — багфиксы
   - `quality/<кратко>` — улучшения качества конвертации
   - `docs/<кратко>` — документация
3. Коммиты — в настоящем времени, по сути: `Add encrypted-PDF handling`.
4. **Pull Request** в `main`, ссылается на issue (`Closes #N`), проходит CI и ревью.
5. `main` всегда в рабочем состоянии.

## Фазы разработки

- **Фаза 1 — MVP** ✅ Базовый конвертер `inputs/ → outputs/`.
- **Фаза 2 — Надёжность** Обработка ошибок, edge-cases, логирование.
- **Фаза 3 — Качество** Тюнинг точности, тестовый корпус PDF, пост-обработка.
- **Фаза 4 — Движки** ✅ Adobe free-tier движок (`--engine adobe`); ⏳ OCR для сканов.

Актуальный статус — в [Roadmap #11](https://github.com/artmazloev/pdftodocxconverter/issues/11).

## Тестирование изменений

Перед PR прогони smoke-тест и реальные PDF:

```bash
python scripts/smoke_test.py  # быстрый e2e (как в CI)
python convert.py -v          # на реальных файлах, подробный лог
```

Проверь, что DOCX открывается в Word/Pages и **редактируется** (текст не превратился
в картинку, таблицы остались таблицами). Если трогал Adobe-движок — прогони с
`--engine adobe` на тестовых ключах.

## Стиль кода

- Python 3.11+, type hints, докстринги на модулях/функциях.
- Не коммить PDF/DOCX (они в `.gitignore`) и секреты (`.env`, ключи Adobe).
