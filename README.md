<div align="center">

<img src="img/start_userbot.png" alt="Bot Preview" width="600"/>

</div>

[![Codacy Badge](https://app.codacy.com/project/badge/Grade/7fceb52b899d44b3bb151b568dc99d38)](https://app.codacy.com/gh/hairpin01/MCUB-fork/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![GitHub repo size](https://img.shields.io/github/repo-size/hairpin01/MCUB-fork)](https://github.com/hairpin01/MCUB-fork)
[![GitHub last commit](https://img.shields.io/github/last-commit/hairpin01/MCUB-fork)](https://github.com/hairpin01/MCUB-fork/commits/main)
[![GitHub issues](https://img.shields.io/github/issues/hairpin01/MCUB-fork)](https://github.com/hairpin01/MCUB-fork/issues)
[![GitHub forks](https://img.shields.io/github/forks/Mitrichdfklwhcluio/MCUBFB?style=flat)](https://github.com/hairpin01/MCUB-fork/network/members)
[![GitHub stars](https://img.shields.io/github/stars/hairpin01/MCUB-fork)](https://github.com/hairpin01/MCUB-fork/stargazers)
[![GitHub license](https://img.shields.io/github/license/hairpin01/MCUB-fork)](https://github.com/hairpin01/MCUB-fork/blob/main/LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# MCUB-fork 

`MCUB fork` это userbot и форк `MCUBFB` с улучшенным `api`, и с правильной структурой 
> [!TIP]
> Скоро будет `api documentation `

## Установка

```bash
git clone https://github.com/hairpin01/MCUB-fork.git && cd MCUB-fork ; pip install -r requirements.txt ; python3 main.py
```

## Настройка

1. Получите `API_ID` и `API_HASH` на https://my.telegram.org

2. Запустите main.py
```shell
python3 main.py
```
3. Заполните:
   - `api_id` - ваш API ID
   - `api_hash` - ваш API Hash
   - `phone` - ваш номер телефона (+79991234567)


> [!TIP]
> иногда нужно создать виртуальное окружение (`python -m venv .venv ; source .venv/bin/activate`)



> **Важно:** Файл `config.json` содержит конфиденциальные  данные

## Команды

- `.ping` - проверка задержки
- `.info` - информация о юзерботе
- `.restart` - перезагрузка
- `.im` - установить модуль (ответ на `.py` файл)
- `.man` - список модулей
- `.um [название]` - удалить модуль, потом лучше всего перезагрузить `userbot`

> [!TIP]
> __безопасность:__ **НЕ** устанавливайте **подозрительные** модули. для безопасности есть api protection (чтобы включить `.api_protection` или `.fcfg api_protection true`).
> не исполняйте подозрительный код с помощью `.py` (python) или `.t` (терминал) 

## Модули

Модули устанавливаются через команду `.im` (ответ на .py файл).
Дириктория для модулей в `modules_loaded/`.

## Офицальные репозиторий (`.dlml`)
Установить: `.dlm` {название-модуля)
