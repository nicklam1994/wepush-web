"""External API integrations: weather, map, etc."""
import httpx
from typing import Optional, Any


async def fetch_weather_hko() -> Optional[dict]:
    """從香港天文台獲取天氣數據（無需 API Key）"""
    url = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            data = resp.json()
    except Exception:
        return None

    result = {}
    if "temperature" in data and data["temperature"].get("data"):
        t = data["temperature"]["data"][0]
        result["temp"] = f"{t.get('value', 'N/A')}°C"
        result["temp_place"] = t.get("place", "")
    if "humidity" in data:
        result["humidity"] = f"{data['humidity'].get('value', 'N/A')}%"
    if "rainfall" in data and data["rainfall"].get("data"):
        r = data["rainfall"]["data"][0]
        result["rain"] = f"{r.get('value', 'N/A')}mm"
    if "icon" in data:
        icons = data["icon"]
        icon_map = {
            50: "☀️ 晴", 51: "☀️ 晴", 52: "☁️ 短暫陽光", 53: "⛅ 多雲",
            54: "🌥️ 多雲", 60: "🌧️ 下雨", 61: "🌧️ 有雨", 62: "🌧️ 大雨",
            63: "⛈️ 雷暴", 64: "⛈️ 雷暴", 65: "🌧️ 有雨", 70: "🌦️ 幾陣雨",
            71: "🌦️ 幾陣雨", 72: "🌦️ 幾陣雨", 73: "🌦️ 幾陣雨", 74: "🌦️ 幾陣雨",
            75: "🌧️ 雨", 76: "🌧️ 雨", 77: "🌧️ 大雨", 80: "🌫️ 薄霧",
            81: "🌫️ 霧", 82: "🌁 煙霞", 83: "🌫️ 霧", 84: "🌁 煙霞", 85: "🌬️ 大風",
        }
        if isinstance(icons, dict) and icons.get("value") in icon_map:
            result["weather"] = icon_map[icons["value"]]
        elif isinstance(icons, int) and icons in icon_map:
            result["weather"] = icon_map[icons]
    result["update_time"] = data.get("updateTime", "")
    return result


async def fetch_openweathermap(api_key: str, city: str = "Hong Kong") -> Optional[dict]:
    """從 OpenWeatherMap 獲取天氣（需要 API Key）"""
    if not api_key:
        return None
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric", "lang": "zh_cn"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
    except Exception:
        return None
    if data.get("cod") != 200:
        return None
    weather_desc = data.get("weather", [{}])[0].get("description", "")
    main = data.get("main", {})
    wind = data.get("wind", {})
    city_name = data.get("name", city)
    return {
        "temp": f"{main.get('temp', 'N/A')}°C",
        "feels_like": f"{main.get('feels_like', 'N/A')}°C",
        "humidity": f"{main.get('humidity', 'N/A')}%",
        "pressure": f"{main.get('pressure', 'N/A')}hPa",
        "weather": weather_desc,
        "wind_speed": f"{wind.get('speed', 'N/A')}m/s",
        "city": city_name,
    }


async def fetch_amap_weather(api_key: str, city_code: str = "440100") -> Optional[dict]:
    """從高德地圖天氣 API 獲取天氣"""
    if not api_key:
        return None
    url = "https://restapi.amap.com/v3/weather/weatherInfo"
    params = {"key": api_key, "city": city_code, "extensions": "base"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
    except Exception:
        return None
    if data.get("status") != "1" or not data.get("lives"):
        return None
    live = data["lives"][0]
    return {
        "temp": f"{live.get('temperature', 'N/A')}°C",
        "weather": live.get("weather", ""),
        "humidity": f"{live.get('humidity', 'N/A')}%",
        "wind": f"{live.get('winddirection', '')}风 {live.get('windpower', '')}级",
        "city": live.get("city", ""),
        "province": live.get("province", ""),
    }


async def fetch_amap_poi(api_key: str, keywords: str, city: str = "广州") -> Optional[list]:
    """從高德地圖 POI 搜索 API 獲取地點信息"""
    if not api_key:
        return None
    url = "https://restapi.amap.com/v3/place/text"
    params = {"key": api_key, "keywords": keywords, "city": city, "offset": 5}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
    except Exception:
        return None
    if data.get("status") != "1" or not data.get("pois"):
        return None
    pois = []
    for poi in data["pois"][:5]:
        pois.append({
            "name": poi.get("name", ""),
            "address": poi.get("address", ""),
            "distance": poi.get("distance", ""),
            "type": poi.get("type", ""),
        })
    return pois


async def resolve_data_source(data_source: str, data_config: dict) -> dict:
    """根據任務配置，調用對應的外部 API 並返回數據字典"""
    variables = {}
    if data_source in ("weather", "weather_map"):
        weather_vars = await fetch_weather_hko()
        if weather_vars:
            variables.update(weather_vars)
        amap_key = data_config.get("amap_key", "")
        if amap_key and not weather_vars:
            city_code = data_config.get("city_code", "440100")
            amap_vars = await fetch_amap_weather(amap_key, city_code)
            if amap_vars:
                variables.update(amap_vars)
        owm_key = data_config.get("openweathermap_key", "")
        if owm_key:
            city = data_config.get("city", "Hong Kong")
            owm_vars = await fetch_openweathermap(owm_key, city)
            if owm_vars:
                variables.update(owm_vars)
    if data_source in ("map", "weather_map"):
        amap_key = data_config.get("amap_key", "")
        poi_keywords = data_config.get("poi_keywords", "")
        poi_city = data_config.get("poi_city", "广州")
        if amap_key and poi_keywords:
            pois = await fetch_amap_poi(amap_key, poi_keywords, poi_city)
            if pois:
                variables["poi_list"] = "\n".join(
                    [f"• {p['name']} ({p['address']})" for p in pois]
                )
                variables["poi_count"] = str(len(pois))
                if pois:
                    variables["poi_first"] = pois[0]["name"]
    from datetime import datetime
    now = datetime.now()
    variables["now"] = now.strftime("%Y-%m-%d %H:%M:%S")
    variables["today"] = now.strftime("%Y-%m-%d")
    variables["time"] = now.strftime("%H:%M")
    variables["weekday"] = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]
    return variables
