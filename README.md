
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/7fceb52b899d44b3bb151b568dc99d38)](https://app.codacy.com/gh/Mitrichdfklwhcluio/MCUBFB/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![GitHub repo size](https://img.shields.io/github/repo-size/hairpin01/tabfix)](https://github.com/Mitrichdfklwhcluio/MCUBFB)
[![GitHub last commit](https://img.shields.io/github/last-commit/hairpin01/tabfix)](https://github.com/Mitrichdfklwhcluio/MCUBFB/commits/main)
[![GitHub issues](https://img.shields.io/github/issues-raw/hairpin01/tabfix)](https://github.com/Mitrichdfklwhcluio/MCUBFB/issues)
[![GitHub forks](https://img.shields.io/github/forks/hairpin01/tabfix?style=flat)](https://github.com/Mitrichdfklwhcluio/MCUBFB/network/members)
[![GitHub stars](https://img.shields.io/github/stars/hairpin01/tabfix)](https://github.com/Mitrichdfklwhcluio/MCUBFB/stargazers)
[![GitHub license](https://img.shields.io/github/license/hairpin01/tabfix)](https://github.com/Mitrichdfklwhcluio/MCUBFB/blob/main/LICENSE) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# Mitrich UserBot

Юзербот для Telegram, работающий от имени вашего аккаунта.

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

1. Получите API_ID и API_HASH на https://my.telegram.org
2. Скопируйте `config.example.json` в `config.json`:
   ```bash
   cp config.example.json config.json
   ```
3. Откройте `config.json` и заполните:
   - `api_id` - ваш API ID
   - `api_hash` - ваш API Hash
   - `phone` - ваш номер телефона (+79991234567)

## Запуск

```bash
python3 userbot.py
```
> [!TIP]
> иногда нужно создать виртуальное окружение (`python -m venv .venv ; source .venv/bin/activate`)


При первом запуске введите код подтверждения из Telegram.

**Важно:** Файл `config.json` содержит конфиденциальные данные и добавлен в .gitignore

## Команды

- `.ping` - проверка задержки
- `.info` - информация о юзерботе
- `.restart` - перезагрузка
- `.im` - установить модуль (ответ на .py файл)
- `.lm` - список модулей
- `.um [название]` - удалить модуль

## Модули

Модули устанавливаются через команду `.im` (ответ на .py файл).
Примеры модулей в дириктории `modules/`.
