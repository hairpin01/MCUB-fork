# requires: aiohttp
import aiohttp
from telethon import events

async def get_weather(city):
    url = f'https://wttr.in/{city}?format=j1'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
    return None

def register(client):
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.weather\s+(.+)'))
    async def weather_handler(event):
        city = event.pattern_match.group(1).strip()
        await event.edit('🌤 Получение погоды...')
        
        try:
            data = await get_weather(city)
            if data and 'current_condition' in data:
                current = data['current_condition'][0]
                location = data['nearest_area'][0]
                
                city_name = location['areaName'][0]['value']
                country = location['country'][0]['value']
                
                temp = current['temp_C']
                feels = current['FeelsLikeC']
                desc = current['weatherDesc'][0]['value']
                humidity = current['humidity']
                wind = current['windspeedKmph']
                pressure = current['pressure']
                
                text = f"🌍 **{city_name}, {country}**\n\n"
                text += f"🌡 Температура: {temp}°C (ощущается как {feels}°C)\n"
                text += f"☁️ Условия: {desc}\n"
                text += f"💧 Влажность: {humidity}%\n"
                text += f"💨 Ветер: {wind} км/ч\n"
                text += f"🔽 Давление: {pressure} мбар"
                
                await event.edit(text)
            else:
                await event.edit('❌ Город не найден')
        except Exception as e:
            await event.edit(f'❌ Ошибка: {str(e)}')
