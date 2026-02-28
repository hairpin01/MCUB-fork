# Display IP address and geolocation info.

import aiohttp

DESCRIPTION = "Display public IP and geolocation info."


async def run(shell, args):
    target_ip = args[0] if args else None
    
    url = f"http://ip-api.com/json/{target_ip}" if target_ip else "http://ip-api.com/json"
    
    shell.output(f"\n\033[96m\033[1mIP Information\033[0m\n")
    
    try:
        with shell.spinner("Fetching IP info..."):
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
        
        if data.get("status") == "fail":
            shell.output(f"  \033[91mError: {data.get('message', 'Unknown')}\033[0m")
            return
        
        shell.output(f"  \033[93mIP:\033[0m       {data.get('query', 'N/A')}")
        shell.output(f"  \033[93mCountry:\033[0m {data.get('country', 'N/A')} ({data.get('countryCode', '')})")
        shell.output(f"  \033[93mRegion:\033[0m  {data.get('regionName', 'N/A')} ({data.get('region', '')})")
        shell.output(f"  \033[93mCity:\033[0m    {data.get('city', 'N/A')}")
        shell.output(f"  \033[93mISP:\033[0m      {data.get('isp', 'N/A')}")
        shell.output(f"  \033[93mOrg:\033[0m      {data.get('org', 'N/A')}")
        shell.output(f"  \033[93mAS:\033[0m       {data.get('as', 'N/A')}")
        
    except aiohttp.ClientError as e:
        shell.output(f"  \033[91mNetwork error: {e}\033[0m")
    except Exception as e:
        shell.output(f"  \033[91mError: {e}\033[0m")
