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
   copy config.example.json config.json
   ```
3. Откройте `config.json` и заполните:
   - `api_id` - ваш API ID
   - `api_hash` - ваш API Hash
   - `phone` - ваш номер телефона (+79991234567)

## Запуск

```bash
python3 userbot.py
```

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
Примеры модулей в папке `modules/`.
