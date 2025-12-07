import aiohttp
from telethon import events

async def get_crypto_price(symbol):
    url = f'https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd,rub&include_24hr_change=true'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            return None

CRYPTO_MAP = {
    'btc': 'bitcoin',
    'eth': 'ethereum',
    'usdt': 'tether',
    'bnb': 'binancecoin',
    'sol': 'solana',
    'xrp': 'ripple',
    'ada': 'cardano',
    'doge': 'dogecoin',
    'ton': 'the-open-network',
    'trx': 'tron'
}

def register(bot):
    @bot.on(events.NewMessage(outgoing=True, pattern=r'^\.crypto(?:\s+(.+))?'))
    async def crypto_price(event):
        query = event.pattern_match.group(1)
        
        if not query:
            query = 'btc,eth,bnb'
        
        await event.edit('💰 Получаю курсы...')
        
        symbols = [s.strip().lower() for s in query.split(',')]
        crypto_ids = [CRYPTO_MAP.get(s, s) for s in symbols]
        
        msg = '💰 **Курсы криптовалют:**\n\n'
        
        for symbol, crypto_id in zip(symbols, crypto_ids):
            data = await get_crypto_price(crypto_id)
            
            if data and crypto_id in data:
                price_data = data[crypto_id]
                usd = price_data.get('usd', 0)
                rub = price_data.get('rub', 0)
                change = price_data.get('usd_24h_change', 0)
                
                emoji = '📈' if change > 0 else '📉'
                msg += f"**{symbol.upper()}**\n"
                msg += f"💵 ${usd:,.2f}\n"
                msg += f"₽ {rub:,.2f}\n"
                msg += f"{emoji} 24h: {change:+.2f}%\n\n"
            else:
                msg += f"**{symbol.upper()}**: ❌ Не найдено\n\n"
        
        await event.edit(msg)
