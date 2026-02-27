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

[English](#english) | [Русский](#русский) | [Українська](#українська) | [Español](#español) | [Deutsch](#deutsch) | [中文](#中文)

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

#### Windows
```powershell
# Using Python from Microsoft Store or python.org
git clone https://github.com/hairpin01/MCUB-fork.git
cd MCUB-fork
pip install -r requirements.txt
python -m core
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

### Support
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

#### Windows
```powershell
# Используя Python из Microsoft Store или python.org
git clone https://github.com/hairpin01/MCUB-fork.git
cd MCUB-fork
pip install -r requirements.txt
python -m core
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

### Поддержка
Чат в Telegram [*жмяк*](https://t.me/+LVnbdp4DNVE5YTFi)

### Официальные репозитории (`.dlm`)
Установить: `.dlm` {название-модуля/без аргумента все модули}

Список модулей ___(без инлайн бота)___: `.dlm -list {название модуля/нечего}`

Нужен модуль для MCUB-fork? [жмякни здесь](https://github.com/hairpin01/repo-MCUB-fork)

---

## Українська

`MCUB-fork` — це Telegram userbot та форк `MCUBFB` з покращеним API та правильною структурою.

> [!TIP]
> Документація до модулів: [API documentation](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md)

### Встановлення

<details>
<summary><b>Встановлення на різні системи (натисніть щоб розгорнути)</b></summary>

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

#### Windows
```powershell
# Використовуючи Python з Microsoft Store або python.org
git clone https://github.com/hairpin01/MCUB-fork.git
cd MCUB-fork
pip install -r requirements.txt
python -m core
```

#### Docker
```bash
# Збудувати та запустити
docker build -t mcub-fork .
docker run -d -p 8080:8080 --name mcub mcub-fork

# Або через docker-compose
docker-compose up -d
```

#### Віртуальне середовище (рекомендовано)
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m core
```

</details>

### Налаштування

1. Отримайте `API_ID` та `API_HASH` на https://my.telegram.org
2. Запустіть MCUB як пакет:
```shell
python3 -m core
```
3. Заповніть:
   - `api_id` — ваш API ID
   - `api_hash` — ваш API Hash
   - `phone` — ваш номер телефону (+79991234567)

> [!TIP]
> Іноді потрібно створити віртуальне середовище (`python -m venv .venv ; source .venv/bin/activate`)

> [!IMPORTANT]
> Файл `config.json` містить конфіденційні дані

### Параметри командного рядка

| Параметр | Опис | За замовчуванням | Змінна середовища |
|----------|------|------------------|-------------------|
| `--no-web` | Вимкнути веб-панель | `false` | `MCUB_NO_WEB=1` |
| `--proxy-web` | Увімкнути проксі вебу за вказаним шляхом (наприклад, `/web` або `/`) | - | `MCUB_PROXY_WEB=/web` |
| `--port` | Порт веб-панелі | `8080` | `MCUB_PORT=8080` |
| `--host` | Хост веб-панелі | `127.0.0.1` | `MCUB_HOST=127.0.0.1` |

#### Приклади
```bash
# Запуск без веб-панелі
python3 -m core --no-web

# Запуск на іншому порту
python3 -m core --port 9000

# Запуск з проксі вебу за шляхом /web
python3 -m core --proxy-web=/web

# Запуск на всіх інтерфейсах
python3 -m core --host 0.0.0.0

# Використання змінних середовища
MCUB_NO_WEB=1 MCUB_PORT=9000 python3 -m core
```

### Команди

- `.ping` — перевірка затримки
- `.info` — інформація про юзербот
- `.restart` — перезавантаження
- `.iload` — встановити модуль __(відповідь на `.py` файл)__
- `.man` — список модулів __(та їх команди)__
- `.um [назва]` — видалити модуль

> [!TIP]
> __Безпека:__ НЕ встановлюйте __підозрілі__ модулі. Для безпеки є api protection (щоб увімкнути: `.api_protection`).
> Не виконуйте підозрілий код за допомогою `.py` (python) або `.t` (термінал)

> [!NOTE]
> Щоб отримати HTML-розгортку повідомлення — просто у відповідь надішліть `.py print(r_text)`

### Модулі

Модулі встановлюються через команду `.iload` (відповідь на .py файл).
Директорія для модулів: `modules_loaded/`.

### Підтримка
Чат у Telegram [*натисніть тут*](https://t.me/+LVnbdp4DNVE5YTFi)

### Офіційні репозиторії (`.dlm`)
Встановити: `.dlm` {назва-модуля/без аргументу всі модулі}

Список модулів ___(без інлайн бота)___: `.dlm -list {назва модуля/нічого}`

Потрібен модуль для MCUB-fork? [натисніть тут](https://github.com/hairpin01/repo-MCUB-fork)

---

## Español

`MCUB-fork` es un userbot de Telegram y un fork de `MCUBFB` con API mejorada y estructura correcta.

> [!TIP]
> Documentación de módulos: [API documentation](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md)

### Instalación

<details>
<summary><b>Instalación en diferentes sistemas (clic para expandir)</b></summary>

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

#### Windows
```powershell
# Usando Python desde Microsoft Store o python.org
git clone https://github.com/hairpin01/MCUB-fork.git
cd MCUB-fork
pip install -r requirements.txt
python -m core
```

#### Docker
```bash
# Construir y ejecutar
docker build -t mcub-fork .
docker run -d -p 8080:8080 --name mcub mcub-fork

# O usar docker-compose
docker-compose up -d
```

#### Entorno virtual (recomendado)
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m core
```

</details>

### Configuración

1. Obtén `API_ID` y `API_HASH` de https://my.telegram.org
2. Ejecuta MCUB como paquete:
```shell
python3 -m core
```
3. Rellena:
   - `api_id` - tu API ID
   - `api_hash` - tu API Hash
   - `phone` - tu número de teléfono (+79991234567)

> [!TIP]
> A veces necesitas crear un entorno virtual (`python -m venv .venv ; source .venv/bin/activate`)

> [!IMPORTANT]
> El archivo `config.json` contiene datos confidenciales

### Banderas CLI

| Bandera | Descripción | Por defecto | Variable de entorno |
|---------|-------------|--------------|---------------------|
| `--no-web` | Desactivar el panel web | `false` | `MCUB_NO_WEB=1` |
| `--proxy-web` | Activar proxy web en la ruta especificada (ej. `/web` o `/`) | - | `MCUB_PROXY_WEB=/web` |
| `--port` | Puerto del panel web | `8080` | `MCUB_PORT=8080` |
| `--host` | Host del panel web | `127.0.0.1` | `MCUB_HOST=127.0.0.1` |

#### Ejemplos
```bash
# Ejecutar sin panel web
python3 -m core --no-web

# Ejecutar en puerto personalizado
python3 -m core --port 9000

# Ejecutar con proxy web en /web
python3 -m core --proxy-web=/web

# Ejecutar en todas las interfaces
python3 -m core --host 0.0.0.0

# Usando variables de entorno
MCUB_NO_WEB=1 MCUB_PORT=9000 python3 -m core
```

### Comandos

- `.ping` - verificar latencia
- `.info` - información del userbot
- `.restart` - reiniciar
- `.iload` - instalar módulo __(responder a archivo `.py`)__
- `.man` - lista de módulos __(y sus comandos)__
- `.um [nombre]` - eliminar módulo

> [!TIP]
> __Seguridad:__ NO instales módulos __sospechosos__. Para seguridad existe api protection (para activar: `.api_protection`).
> No ejecutes código sospechoso usando `.py` (python) o `.t` (terminal)

> [!NOTE]
> Para obtener el código HTML de un mensaje - solo responde con `.py print(r_text)`

### Módulos

Los módulos se instalan mediante el comando `.iload` (responder a archivo .py).
Directorio de módulos: `modules_loaded/`.

### Soporte
Chat de Telegram [*haz clic aquí*](https://t.me/+LVnbdp4DNVE5YTFi)

### Repositorios Oficiales (`.dlm`)
Instalar: `.dlm` {nombre-del-módulo / sin argumentos para todos los módulos}

Lista de módulos ___(sin bot inline)___: `.dlm -list {nombre-del-módulo / nada}`

¿Necesitas un módulo para MCUB-fork? [haz clic aquí](https://github.com/hairpin01/repo-MCUB-fork)

---

## Deutsch

`MCUB-fork` ist ein Telegram-Userbot und ein Fork von `MCUBFB` mit verbesserter API und korrekter Struktur.

> [!TIP]
> Moduldokumentation: [API documentation](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md)

### Installation

<details>
<summary><b>Installation auf verschiedenen Systemen (klicken zum Erweitern)</b></summary>

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

#### Windows
```powershell
# Python von Microsoft Store oder python.org verwenden
git clone https://github.com/hairpin01/MCUB-fork.git
cd MCUB-fork
pip install -r requirements.txt
python -m core
```

#### Docker
```bash
# Builden und ausführen
docker build -t mcub-fork .
docker run -d -p 8080:8080 --name mcub mcub-fork

# Oder docker-compose verwenden
docker-compose up -d
```

#### Virtuelle Umgebung (empfohlen)
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m core
```

</details>

### Konfiguration

1. Erhalte `API_ID` und `API_HASH` von https://my.telegram.org
2. MCUB als Paket ausführen:
```shell
python3 -m core
```
3. Ausfüllen:
   - `api_id` - deine API ID
   - `api_hash` - dein API Hash
   - `phone` - deine Telefonnummer (+79991234567)

> [!TIPP]
> Manchmal musst du eine virtuelle Umgebung erstellen (`python -m venv .venv ; source .venv/bin/activate`)

> [!WICHTIG]
> Die `config.json` Datei enthält vertrauliche Daten

### CLI-Flags

| Flag | Beschreibung | Standard | Umgebungsvariable |
|------|--------------|----------|-------------------|
| `--no-web` | Webpanel deaktivieren | `false` | `MCUB_NO_WEB=1` |
| `--proxy-web` | Webproxy unter dem angegebenen Pfad aktivieren (z.B. `/web` oder `/`) | - | `MCUB_PROXY_WEB=/web` |
| `--port` | Webpanel-Port | `8080` | `MCUB_PORT=8080` |
| `--host` | Webpanel-Host | `127.0.0.1` | `MCUB_HOST=127.0.0.1` |

#### Beispiele
```bash
# Ohne Webpanel ausführen
python3 -m core --no-web

# Auf benutzerdefiniertem Port ausführen
python3 -m core --port 9000

# Mit Webproxy unter /web ausführen
python3 -m core --proxy-web=/web

# Auf allen Interfaces ausführen
python3 -m core --host 0.0.0.0

# Umgebungsvariablen verwenden
MCUB_NO_WEB=1 MCUB_PORT=9000 python3 -m core
```

### Befehle

- `.ping` - Latenz prüfen
- `.info` - Userbot-Info
- `.restart` - Neustart
- `.iload` - Modul installieren __(auf `.py` Datei antworten)__
- `.man` - Modulliste __(und ihre Befehle)__
- `.um [name]` - Modul entfernen

> [!TIPP]
> __Sicherheit:__ Installiere KEINE __verdächtigen__ Module. Für Sicherheit gibt es API-Schutz (aktivieren mit: `.api_protection`).
> Führe keinen verdächtigen Code mit `.py` (Python) oder `.t` (Terminal) aus

> [!HINWEIS]
> Um die HTML-Quelle einer Nachricht zu erhalten - antworte einfach mit `.py print(r_text)`

### Module

Module werden über den `.iload` Befehl installiert (auf .py Datei antworten).
Modulverzeichnis: `modules_loaded/`.

### Support
Telegram-Chat [*hier klicken*](https://t.me/+LVnbdp4DNVE5YTFi)

### Offizielle Repositories (`.dlm`)
Installieren: `.dlm` {Modulname / ohne Argumente für alle Module}

Modulliste ___(ohne Inline-Bot)___: `.dlm -list {Modulname / nichts}`

Brauchst du ein Modul für MCUB-fork? [hier klicken](https://github.com/hairpin01/repo-MCUB-fork)

---

## 中文

`MCUB-fork` 是一个 Telegram 用户机器人，是 `MCUBFB` 的分支，具有改进的 API 和正确的结构。

> [!TIP]
> 模块文档：[API 文档](https://github.com/hairpin01/MCUB-fork/blob/main/API_DOC.md)

### 安装

<details>
<summary><b>在不同系统上安装（点击展开）</b></summary>

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

#### Windows
```powershell
# 使用 Microsoft Store 或 python.org 的 Python
git clone https://github.com/hairpin01/MCUB-fork.git
cd MCUB-fork
pip install -r requirements.txt
python -m core
```

#### Docker
```bash
# 构建并运行
docker build -t mcub-fork .
docker run -d -p 8080:8080 --name mcub mcub-fork

# 或使用 docker-compose
docker-compose up -d
```

#### 虚拟环境（推荐）
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m core
```

</details>

### 配置

1. 从 https://my.telegram.org 获取 `API_ID` 和 `API_HASH`
2. 以包形式运行 MCUB：
```shell
python3 -m core
```
3. 填写：
   - `api_id` - 你的 API ID
   - `api_hash` - 你的 API Hash
   - `phone` - 你的电话号码 (+79991234567)

> [!提示]
> 有时需要创建虚拟环境（`python -m venv .venv ; source .venv/bin/activate`）

> [!重要]
> `config.json` 文件包含敏感数据

### CLI 参数

| 参数 | 描述 | 默认值 | 环境变量 |
|------|------|--------|----------|
| `--no-web` | 禁用网页面板 | `false` | `MCUB_NO_WEB=1` |
| `--proxy-web` | 在指定路径启用网页代理（例如 `/web` 或 `/`） | - | `MCUB_PROXY_WEB=/web` |
| `--port` | 网页面板端口 | `8080` | `MCUB_PORT=8080` |
| `--host` | 网页面板主机 | `127.0.0.1` | `MCUB_HOST=127.0.0.1` |

#### 示例
```bash
# 禁用网页面板运行
python3 -m core --no-web

# 自定义端口运行
python3 -m core --port 9000

# 在 /web 路径启用网页代理
python3 -m core --proxy-web=/web

# 在所有接口上运行
python3 -m core --host 0.0.0.0

# 使用环境变量
MCUB_NO_WEB=1 MCUB_PORT=9000 python3 -m core
```

### 命令

- `.ping` - 检查延迟
- `.info` - 用户机器人信息
- `.restart` - 重启
- `.iload` - 安装模块 __(回复 `.py` 文件)__
- `.man` - 模块列表 __(及其命令)__
- `.um [名称]` - 删除模块

> [!提示]
> __安全：__ 不要安装__可疑__模块。为了安全，有 API 保护（启用：`.api_protection`）。
> 不要使用 `.py`（Python）或 `.t`（终端）执行可疑代码

> [!注意]
> 要获取消息的 HTML 源码 - 只需回复 `.py print(r_text)`

### 模块

模块通过 `.iload` 命令安装（回复 .py 文件）。
模块目录：`modules_loaded/`。

### 支持
Telegram 群组 [*点击这里*](https://t.me/+LVnbdp4DNVE5YTFi)

### 官方仓库（`.dlm`）
安装：`.dlm` {模块名称 / 无参数则安装所有模块}

模块列表 ___(无内联机器人)___：`.dlm -list {模块名称 / 无}`

需要 MCUB-fork 的模块？ [*点击这里*](https://github.com/hairpin01/repo-MCUB-fork)
