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

[English](#english) | [Русский](#русский)

---

## English

`MCUB-fork` is a Telegram userbot and a fork of `MCUBFB` with improved API and correct structure.

> [!TIP]
> Module documentation: [API documentation](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md)

### Installation

<details>
<summary><b>Installation on different systems (click to expand)</b></summary>

#### Ubuntu / Debian
```bash
sudo apt update && sudo apt install -y python3 python3-pip git
git clone https://github.com/hairpin01/MCUB-fork.git && cd MCUB-fork
pip3 install -r requirements.txt
python3 -m core
```

#### Arch Linux
```bash
sudo pacman -S python python-pip git
git clone https://github.com/hairpin01/MCUB-fork.git && cd MCUB-fork
pip install -r requirements.txt
python -m core
```

#### Fedora
```bash
sudo dnf install python3 python3-pip git
git clone https://github.com/hairpin01/MCUB-fork.git && cd MCUB-fork
pip3 install -r requirements.txt
python3 -m core
```

#### macOS
```bash
brew install python3 git
git clone https://github.com/hairpin01/MCUB-fork.git && cd MCUB-fork
pip3 install -r requirements.txt
python3 -m core
```

#### Docker
```bash
# Build and run
docker build -t mcub-fork .
docker run -d -p 8080:8080 --name mcub mcub-fork

# Or use docker-compose
docker-compose up -d
```

#### Virtual Environment (recommended)
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m core
```

</details>

### Configuration

1. Get `API_ID` and `API_HASH` from https://my.telegram.org
2. Run MCUB as a package:
```shell
python3 -m core
```
3. Fill in:
   - `api_id` - your API ID
   - `api_hash` - your API Hash
   - `phone` - your phone number (+79991234567)

> [!TIP]
> Sometimes you need to create a virtual environment (`python -m venv .venv ; source .venv/bin/activate`)

> [!IMPORTANT]
> The `config.json` file contains confidential data

### CLI Flags

| Flag | Description | Default | Environment Variable |
|------|-------------|---------|---------------------|
| `--no-web` | Disable the web panel | `false` | `MCUB_NO_WEB=1` |
| `--proxy-web` | Enable web proxy at specified path (e.g., `/web` or `/`) | - | `MCUB_PROXY_WEB=/web` |
| `--port` | Web panel port | `8080` | `MCUB_PORT=8080` |
| `--host` | Web panel host | `127.0.0.1` | `MCUB_HOST=127.0.0.1` |

#### Examples
```bash
# Run with web panel disabled
python3 -m core --no-web

# Run on custom port
python3 -m core --port 9000

# Run with web proxy at /web path
python3 -m core --proxy-web=/web

# Run on all interfaces
python3 -m core --host 0.0.0.0

# Using environment variables
MCUB_NO_WEB=1 MCUB_PORT=9000 python3 -m core
```

### Commands

- `.ping` - check latency
- `.info` - userbot info
- `.restart` - restart
- `.iload` - install module __(reply to `.py` file)__
- `.man` - list of modules __(and their commands)__
- `.um [name]` - remove module

> [!TIP]
> __Security:__ Do NOT install __suspicious__ modules. For security, there is api protection (to enable: `.api_protection`).
> Do not execute suspicious code using `.py` (python) or `.t` (terminal)

> [!NOTE]
> To get HTML source of a message - just reply with `.py print(r_text)`

### Modules

Modules are installed via the `.iload` command (reply to .py file).
Module directory: `modules_loaded/`.

### Support?
Telegram chat [*click here*](https://t.me/+LVnbdp4DNVE5YTFi)

### Official Repositories (`.dlm`)
Install: `.dlm` {module name / without arguments for all modules}

Module list ___(without inline bot)___: `.dlm -list {module name / nothing}`

Need a module for MCUB-fork? [click here](https://github.com/hairpin01/repo-MCUB-fork)

---

## Русский

`MCUB-fork` это userbot и форк `MCUBFB` с улучшенным `API`, и с правильной структурой.

> [!TIP]
> документация по модулям: [api documentation](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md)

### Установка

<details>
<summary><b>Установка на разные системы (нажмите чтобы раскрыть)</b></summary>

#### Ubuntu / Debian
```bash
sudo apt update && sudo apt install -y python3 python3-pip git
git clone https://github.com/hairpin01/MCUB-fork.git && cd MCUB-fork
pip3 install -r requirements.txt
python3 -m core
```

#### Arch Linux
```bash
sudo pacman -S python python-pip git
git clone https://github.com/hairpin01/MCUB-fork.git && cd MCUB-fork
pip install -r requirements.txt
python -m core
```

#### Fedora
```bash
sudo dnf install python3 python3-pip git
git clone https://github.com/hairpin01/MCUB-fork.git && cd MCUB-fork
pip3 install -r requirements.txt
python3 -m core
```

#### macOS
```bash
brew install python3 git
git clone https://github.com/hairpin01/MCUB-fork.git && cd MCUB-fork
pip3 install -r requirements.txt
python3 -m core
```

#### Docker
```bash
# Собрать и запустить
docker build -t mcub-fork .
docker run -d -p 8080:8080 --name mcub mcub-fork

# Или через docker-compose
docker-compose up -d
```

#### Виртуальное окружение (рекомендуется)
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m core
```

</details>

### Настройка

1. Получите `API_ID` и `API_HASH` на https://my.telegram.org
2. Запустите MCUB как пакет
```shell
python3 -m core
```
3. Заполните:
   - `api_id` - ваш API ID
   - `api_hash` - ваш API Hash
   - `phone` - ваш номер телефона (+79991234567)

> [!TIP]
> иногда нужно создать виртуальное окружение (`python -m venv .venv ; source .venv/bin/activate`)

> [!IMPORTANT]
> Файл `config.json` содержит конфиденциальные данные

### Аргументы командной строки

| Аргумент | Описание | По умолчанию | Переменная окружения |
|----------|----------|--------------|---------------------|
| `--no-web` | Отключить веб-панель | `false` | `MCUB_NO_WEB=1` |
| `--proxy-web` | Включить прокси веба по указанному пути (например, `/web` или `/`) | - | `MCUB_PROXY_WEB=/web` |
| `--port` | Порт веб-панели | `8080` | `MCUB_PORT=8080` |
| `--host` | Хост веб-панели | `127.0.0.1` | `MCUB_HOST=127.0.0.1` |

#### Примеры
```bash
# Запуск без веб-панели
python3 -m core --no-web

# Запуск на другом порту
python3 -m core --port 9000

# Запуск с прокси веба по пути /web
python3 -m core --proxy-web=/web

# Запуск на всех интерфейсах
python3 -m core --host 0.0.0.0

# Использование переменных окружения
MCUB_NO_WEB=1 MCUB_PORT=9000 python3 -m core
```

### Команды

- `.ping` - проверка задержки
- `.info` - информация о юзерботе
- `.restart` - перезагрузка
- `.iload` - установить модуль __(ответ на `.py` файл)__
- `.man` - список модулей __(и их команды)__
- `.um [название]` - удалить модуль

> [!TIP]
> __безопасность:__ **НЕ** устанавливайте **подозрительные** модули. для безопасности есть api protection (чтобы включить `.api_protection`).
> не исполняйте подозрительный код с помощью `.py` (python) или `.t` (терминал)

> [!NOTE]
> чтобы получить html развёртку сообщения - просто ответом отправте `.py print(r_text)`

### Модули

Модули устанавливаются через команду `.iload` (ответ на .py файл).
Дириктория для модулей в `modules_loaded/`.

### Support?
Чат в Telegram [*жмяк*](https://t.me/+LVnbdp4DNVE5YTFi)

### Офицальные репозиторий (`.dlm`)
Установить: `.dlm` {название-модуля/без аргумента все модули}

Список модулей ___(без инлайн бота)___: `.dlm -list {название модуля/нечего}`

Нужен модуль который для MCUB-fork? [жмякни здесь](https://github.com/hairpin01/repo-MCUB-fork)
