
# requires: telethon, aiohttp, socket

from telethon import events
import subprocess
import asyncio
import re
import aiohttp
import socket
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=10)

def run_ping(host):
    """Выполняет команду ping и возвращает результат"""
    try:
        result = subprocess.run(
            ['ping', '-c', '4', '-W', '2', host],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout, result.returncode
    except subprocess.TimeoutExpired:
        return "", 1
    except Exception as e:
        return f"Ошибка: {str(e)}", 1

def get_ip_info_sync(host):
    """Получает информацию об IP/домене"""
    try:
        # Преобразуем домен в IP
        ip = socket.gethostbyname(host)

        # Получаем информацию от DNS
        info = socket.gethostbyaddr(ip)

        # Пробуем получить ASN информацию через whois (упрощенно)
        try:
            asn_result = subprocess.run(
                ['whois', ip],
                capture_output=True,
                text=True,
                timeout=5
            )
            asn_info = ""
            for line in asn_result.stdout.split('\n'):
                if any(keyword in line.lower() for keyword in ['origin:', 'as-name:', 'netname:', 'country:', 'descr:']):
                    asn_info += line + "\n"
        except:
            asn_info = "Не удалось получить ASN информацию"

        return {
            'host': host,
            'ip': ip,
            'ptr': info[0] if info else "Не найдено",
            'asn_info': asn_info if asn_info else "Нет информации",
            'success': True
        }
    except socket.gaierror:
        return {'success': False, 'error': 'Не удалось разрешить домен'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def parse_ping_output(output):
    """Парсит вывод команды ping"""
    if not output:
        return "Нет ответа", None

    # Ищем статистику
    packets = re.search(r'(\d+) packets transmitted, (\d+) received', output)
    if packets:
        transmitted = packets.group(1)
        received = packets.group(2)
        loss = int(transmitted) - int(received)

        # Ищем время задержки
        times = re.search(r'rtt min/avg/max/mdev = ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms', output)
        if times:
            min_time = times.group(1)
            avg_time = times.group(2)
            max_time = times.group(3)

            result = f"📊 **Статистика пинга:**\n"
            result += f"📤 **Отправлено:** {transmitted}\n"
            result += f"📥 **Получено:** {received}\n"
            result += f"📉 **Потеряно:** {loss} ({int(loss/int(transmitted)*100)}%)\n\n"
            result += f"⏱ **Время отклика:**\n"
            result += f"• Минимальное: {min_time} мс\n"
            result += f"• Среднее: {avg_time} мс\n"
            result += f"• Максимальное: {max_time} мс\n"

            # Определяем статус по средней задержке
            avg = float(avg_time)
            if avg < 50:
                status = "🟢 Отличное"
            elif avg < 100:
                status = "🟡 Хорошее"
            elif avg < 200:
                status = "🟡 Среднее"
            elif avg < 500:
                status = "🟠 Плохое"
            else:
                status = "🔴 Очень плохое"

            result += f"\n**Статус:** {status}"

            return result, float(avg_time)

    # Если нет статистики времени, но есть ответы
    if "bytes from" in output:
        return "✅ Хост доступен, но не удалось получить статистику времени", None

    return "❌ Хост недоступен", None

async def get_ip_api_info(ip):
    """Получает информацию об IP через ip-api.com"""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            url = f"http://ip-api.com/json/{ip}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data['status'] == 'success':
                        return {
                            'country': data.get('country', 'Неизвестно'),
                            'countryCode': data.get('countryCode', ''),
                            'region': data.get('regionName', 'Неизвестно'),
                            'city': data.get('city', 'Неизвестно'),
                            'zip': data.get('zip', 'Неизвестно'),
                            'lat': data.get('lat'),
                            'lon': data.get('lon'),
                            'timezone': data.get('timezone', 'Неизвестно'),
                            'isp': data.get('isp', 'Неизвестно'),
                            'org': data.get('org', 'Неизвестно'),
                            'as': data.get('as', 'Неизвестно'),
                            'query': data.get('query', ip),
                            'success': True
                        }
    except:
        pass
    return {'success': False}

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.pinghost (.+)$'))
    async def pinghost_handler(event):
        """Проверяет доступность хоста и задержку"""
        host = event.pattern_match.group(1).strip()

        await event.edit(f"🔄 **Пингуем {host}...**")

        try:
            # Запускаем ping в отдельном потоке
            loop = asyncio.get_event_loop()
            output, returncode = await loop.run_in_executor(executor, run_ping, host)

            result, avg_time = parse_ping_output(output)

            await event.edit(result)

        except Exception as e:
            await event.edit(f"❌ **Ошибка:**\n```\n{str(e)}\n```")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ipi (.+)$'))
    async def ipi_handler(event):
        """Получает информацию об IP/домене"""
        target = event.pattern_match.group(1).strip()

        await event.edit(f"🔍 **Получаю информацию о {target}...**")

        try:
            # Получаем базовую информацию через socket
            loop = asyncio.get_event_loop()
            basic_info = await loop.run_in_executor(executor, get_ip_info_sync, target)

            if not basic_info.get('success'):
                await event.edit(f"❌ **Ошибка:** {basic_info.get('error', 'Неизвестная ошибка')}")
                return

            # Получаем расширенную информацию через API
            extended_info = await get_ip_api_info(basic_info['ip'])

            # Формируем ответ
            result = f"🔍 **Информация о {target}**\n\n"
            result += f"📍 **IP адрес:** `{basic_info['ip']}`\n"

            if basic_info['ptr'] != "Не найдено":
                result += f"🏷 **PTR запись:** `{basic_info['ptr']}`\n"

            if extended_info.get('success'):
                result += f"🌍 **Страна:** {extended_info['country']} ({extended_info['countryCode']})\n"
                result += f"🏙 **Регион:** {extended_info['region']}\n"
                result += f"🏙 **Город:** {extended_info['city']}\n"
                if extended_info['zip'] != "Неизвестно":
                    result += f"📮 **Индекс:** {extended_info['zip']}\n"
                result += f"🕐 **Часовой пояс:** {extended_info['timezone']}\n"
                result += f"🏢 **Провайдер:** {extended_info['isp']}\n"
                if extended_info['org']:
                    result += f"🏢 **Организация:** {extended_info['org']}\n"
                if extended_info['as']:
                    result += f"🔗 **ASN:** {extended_info['as']}\n"
                if extended_info.get('lat') and extended_info.get('lon'):
                    result += f"📍 **Координаты:** {extended_info['lat']}, {extended_info['lon']}\n"

            if basic_info['asn_info'] != "Нет информации":
                result += f"\n📋 **ASN информация:**\n```\n{basic_info['asn_info']}\n```"

            await event.edit(result)

        except Exception as e:
            await event.edit(f"❌ **Ошибка:**\n```\n{str(e)}\n```")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ping$'))
    async def ping_help_handler(event):
        help_text = """
📡 **Модулёк для проверки сети:**

`.pinghost <ip/домен>` - проверить доступность и задержку
`.ipi <ip/домен>` - получить информацию об IP/домене

Автор @Hairpin00
"""
        await event.edit(help_text)
