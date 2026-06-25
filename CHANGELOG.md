# Changelog

Все заметные изменения проекта. Формат — по мотивам
[Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

## [Unreleased]

### Added
- Облачный движок **Adobe PDF Services** (`--engine adobe`) для дизайнерских PDF,
  с которыми не справляется локальный движок.
- `requirements-adobe.txt` — опциональная зависимость `pdfservices-sdk`.
- `docs/ARCHITECTURE.md` — архитектура, сравнение движков, журнал решений.
- `CHANGELOG.md`.
- Документация по получению ключей Adobe и настройке `.env` (README).

### Changed
- README: вступление и «Как это работает» переписаны под два движка; обновлены
  структура проекта и раздел «Точность и ограничения».
- CONTRIBUTING: актуализированы структура, фазы и шаги тестирования.

### Known limitations
- Локальный движок (`pdf2docx`) плохо держит дизайнерскую вёрстку (векторные
  чарты, карточки) и **Type3-шрифты** (склеивает слова) — для таких файлов
  используйте `--engine adobe`.

## [0.1.0] — Фаза 1 (MVP)

### Added
- Базовый конвертер: батч `inputs/ → outputs/` (`convert.py`).
- Локальный движок на `pdf2docx` (`engine_local.py`).
- Pre-flight анализатор: цифровой PDF vs скан (`analyzer.py`).
- Инфраструктура: шаблоны issues/PR, CI (GitHub Actions), smoke-тест,
  README с развёртыванием, CONTRIBUTING.
- Backlog задач в issues (#2–#11) с группировкой по фазам.
