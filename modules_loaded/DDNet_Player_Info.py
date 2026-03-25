# 🔒    Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html

# ---------------------------------------------------------------------------------
# Name: DDNet player info
# Description: Модуль для получения информации о профиле игрока DDraceNetwork и KOG
# meta developer: @ElonModules
# ---------------------------------------------------------------------------------

from .. import loader, utils
import requests
import urllib.parse
import asyncio
from bs4 import BeautifulSoup

@loader.tds
class ProfileMod(loader.Module):
    """Модуль для получения информации о профиле игрока DDraceNetwork и KOG"""

    strings = {
        "name": "DDNet player info",
        "no_name": "❌ Имя игрока ",
        "error_fetch": "❌ Не удалось получить информацию о профиле",
        "fetching_ddnet": "🔍 Получаю информацию о игроке DDraceNetwork <code>{name}</code>...",
        "fetching_kog": "🔍 Получаю информацию о игроке KOG <code>{nickname}</code>...",
        "points_info_ddnet": "<b><u>📊 Информация о игроке DDraceNetwork</u></b>\n\n"
                       "<b>Ник:</b> <code>{name}</code>\n"
                       "<b>Наиграно:</b> <code>{hours} часов</code>\n"
                       "<b>Поинты:</b> <code>{points}</code>\n"
                       "<b>Место в топе:</b> <code>{rank}</code>\n"
                       "<b><a href='https://ddnet.org/players/{api_name}'>Ссылка на статистику (кликабельно)</a></b>\n\n"
                       "<b>Количество пройденных карт:</b>\n"
                       " <b>Novice:</b> <code>{novice_completed}/{novice_total}</code>\n"
                       " <b>Moderate:</b> <code>{moderate_completed}/{moderate_total}</code>\n"
                       " <b>Brutal:</b> <code>{brutal_completed}/{brutal_total}</code>\n"
                       " <b>Insane:</b> <code>{insane_completed}/{insane_total}</code>\n"
                       " <b>Dummy:</b> <code>{dummy_completed}/{dummy_total}</code>\n"
                       " <b>DDmaX.Easy:</b> <code>{ddmax_easy_completed}/{ddmax_easy_total}</code>\n"
                       " <b>DDmaX.Next:</b> <code>{ddmax_next_completed}/{ddmax_next_total}</code>\n"
                       " <b>DDmaX.Pro:</b> <code>{ddmax_pro_completed}/{ddmax_pro_total}</code>\n"
                       " <b>DDmaX.Nut:</b> <code>{ddmax_nut_completed}/{ddmax_nut_total}</code>\n"
                       " <b>Oldschool:</b> <code>{oldschool_completed}/{oldschool_total}</code>\n"
                       " <b>Solo:</b> <code>{solo_completed}/{solo_total}</code>\n"
                       " <b>Race:</b> <code>{race_completed}/{race_total}</code>\n"
                       " <b>Fun:</b> <code>{fun_completed}/{fun_total}</code>\n",
        "points_info_kog": "<b><u>📊 Информация о игроке KOG</u></b>\n\n"
                            "<b>Ник:</b> <code>{nickname}</code>\n"
                            "<b>Наиграно:</b> <code>{played_hours} часов</code>\n"
                            "<b>Поинты:</b> <code>{points}</code>\n"
                            "<b>Место в топе:</b> <code>{rank}</code>\n"
                            "<b><a href='{stats_link}'>Ссылка на статистику (кликабельно)</a></b>\n\n",
        "ddnet_cmd_description": "Получить информацию о профиле игрока DDraceNetwork. Использование: .ddnet Nick или в ответ на сообщение.",
        "kog_cmd_description": "Получить информацию о профиле игрока KOG. Использование: .kog Nick или в ответ на сообщение."
    }

    async def ddnetcmd(self, message):
        """Получить информацию о профиле игрока DDraceNetwork"""
        args = utils.get_args_raw(message)

        if not args:
            reply = await message.get_reply_message()
            if reply and reply.from_id:
                original_name = reply.message
            else:
                await utils.answer(message, self.strings["no_name"])
                return
        else:
            original_name = args

        original_name = str(original_name)
        api_name = urllib.parse.quote_plus(original_name)

        fetching_message = await utils.answer(message, self.strings["fetching_ddnet"].format(name=original_name))

        await asyncio.sleep(2)  

        try:
            response = requests.get(f"https://ddnet.org/players/?json2={api_name}", 
                                    headers={'Accept': 'application/json'})

            if response.status_code != 200:
                await utils.answer(message, self.strings["error_fetch"])
                return

            data = response.json()

            if not data or 'points' not in data:
                await utils.answer(message, self.strings["error_fetch"])
                return

            points = data['points']['points']
            rank = data['points']['rank']
            hours = data.get('hours_played_past_365_days', 0)

            hours_str = str(hours)

            def get_map_data(map_type):
                if map_type in data.get('types', {}):
                    maps = data['types'][map_type]['maps']
                    completed = sum(1 for _ in maps.values() if _['finishes'] > 0)
                    total = len(maps)
                    return completed, total
                return 0, 0  
            
            novice_completed, novice_total = get_map_data('Novice')
            moderate_completed, moderate_total = get_map_data('Moderate')
            brutal_completed, brutal_total = get_map_data('Brutal')
            insane_completed, insane_total = get_map_data('Insane')
            dummy_completed, dummy_total = get_map_data('Dummy')
            ddmax_easy_completed, ddmax_easy_total = get_map_data('DDmaX.Easy')
            ddmax_next_completed, ddmax_next_total = get_map_data('DDmaX.Next')
            ddmax_pro_completed, ddmax_pro_total = get_map_data('DDmaX.Pro')
            ddmax_nut_completed, ddmax_nut_total = get_map_data('DDmaX.Nut')
            oldschool_completed, oldschool_total = get_map_data('Oldschool')
            solo_completed, solo_total = get_map_data('Solo')
            race_completed, race_total = get_map_data('Race')
            fun_completed, fun_total = get_map_data('Fun')

            points_info = self.strings["points_info_ddnet"].format(
                name=original_name,
                api_name=api_name,
                hours=hours_str,
                points=points,
                rank=rank,
                novice_completed=novice_completed,
                novice_total=novice_total,
                moderate_completed=moderate_completed,
                moderate_total=moderate_total,
                brutal_completed=brutal_completed,
                brutal_total=brutal_total,
                insane_completed=insane_completed,
                insane_total=insane_total,
                dummy_completed=dummy_completed,
                dummy_total=dummy_total,
                ddmax_easy_completed=ddmax_easy_completed,
                ddmax_easy_total=ddmax_easy_total,
                ddmax_next_completed=ddmax_next_completed,
                ddmax_next_total=ddmax_next_total,
                ddmax_pro_completed=ddmax_pro_completed,
                ddmax_pro_total=ddmax_pro_total,
                ddmax_nut_completed=ddmax_nut_completed,
                ddmax_nut_total=ddmax_nut_total,
                oldschool_completed=oldschool_completed,
                oldschool_total=oldschool_total,
                solo_completed=solo_completed,
                solo_total=solo_total,
                race_completed=race_completed,
                race_total=race_total,
                fun_completed=fun_completed,
                fun_total=fun_total,
            )

            await utils.answer(fetching_message, points_info)

        except Exception as e:
            await utils.answer(fetching_message, f"{self.strings['error_fetch']}: {str(e)}")  

    async def kogcmd(self, message):
        """Получить информацию о профиле игрока KOG"""
        args = utils.get_args_raw(message)

        if not args:
            reply = await message.get_reply_message()
            if reply and reply.from_id:
                player_name = reply.message
            else:
                await utils.answer(message, self.strings["no_name"])
                return
        else:
            player_name = args.strip()

        fetching_message = await utils.answer(message, self.strings["fetching_kog"].format(nickname=player_name))

        await asyncio.sleep(2)  

        player_info = self.get_player_info(player_name)

        if player_info:
            played_hours = self.convert_time_to_hours(player_info.get('Hours', '0 months, 0 days, 0 hours, 0 minutes, 0 seconds'))

            output = self.strings["points_info_kog"].format(
                nickname=player_info.get('Nickname', 'Нету'),
                played_hours=played_hours,
                points=player_info.get('Points', 'Нету'),
                rank=player_info.get('Rank', 'Нету'),
                stats_link=player_info.get('Stats Link', ''),
                maps=player_info.get('Maps', 'Нету')
            )
            await utils.answer(fetching_message, output)

        else:
            await utils.answer(fetching_message, "❌ Не удалось получить информацию о профиле KOG.")  

    def convert_time_to_hours(self, time_str):
        months, days, hours, minutes, seconds = 0, 0, 0, 0, 0
        
        time_parts = time_str.split(', ')
        for part in time_parts:
            if 'months' in part:
                months = int(part.split()[0])
            elif 'days' in part:
                days = int(part.split()[0])
            elif 'hours' in part:
                hours = int(part.split()[0])
            elif 'minutes' in part:
                minutes = int(part.split()[0])
            elif 'seconds' in part:
                seconds = int(part.split()[0])

        total_hours = (months * 30 * 24) + (days * 24) + hours + (minutes / 60) + (seconds / 3600)
        return round(total_hours, 2)  

    def get_player_info(self, player_name):
        url = f"https://kog.tw/get.php?p=players&p=players&player={player_name}"

        response = requests.get(url)

        if response.status_code != 200:
            print(f"Ошибка доступа к {url}: статус {response.status_code}")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')
        info = {}

        nickname = soup.find('h2')
        info['Nickname'] = nickname.text.strip() if nickname else 'Нету'  

        wasted_time_header = soup.find('h5', text=lambda text: text and 'Wasted time due to finished maps' in text)
        if wasted_time_header:
            time_str = wasted_time_header.find_next('h6')
            info['Hours'] = time_str.text.strip() if time_str else 'Нету'
        else:
            info['Hours'] = 'Нету'  

        rank_info = soup.find(text=lambda text: 'Rank' in text)
        if rank_info:
            info['Rank'] = rank_info.find_next('b').text.strip()
            points_info = rank_info.find_next(text=lambda text: 'with' in text)
            info['Points'] = points_info.split()[1].strip() if points_info else 'Нету'
        else:
            info['Rank'] = 'Нету'
            info['Points'] = 'Нету' 

        info['Stats Link'] = f"https://kog.tw/index.php#p=players&player={player_name}"

        

        return info  
