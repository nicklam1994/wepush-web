"""External API integrations — HKO weather via weather_hko package."""
import sys
import os
import httpx
from typing import Optional
from datetime import datetime

# 引入 weather-hko-api 項目
_HKO_PATH = "/home/nicklam-ai/repos/weather-hko-api"
if _HKO_PATH not in sys.path:
    sys.path.insert(0, _HKO_PATH)


async def fetch_weather_hko() -> Optional[dict]:
    """使用 weather_hko 獲取香港天文台完整天氣數據"""
    from weather_hko import fetch, parse_all

    raw = fetch()
    if not raw:
        return None

    parsed = parse_all(raw)
    curr = parsed.get("current", {})
    flw = parsed.get("flw", {})
    common = parsed.get("common", {})
    regional = parsed.get("regional", {})
    hdr = parsed.get("header", {})

    return {
        # 即時觀測
        "temp": f"{curr.get('temperature', 'N/A')}°C",
        "humidity": f"{curr.get('humidity', 'N/A')}%",
        "latest_temp": f"{curr.get('latest_temp', 'N/A')}°C",
        "temp_max": f"{curr.get('temp_max_today', 'N/A')}°C",
        "temp_min": f"{curr.get('temp_min_today', 'N/A')}°C",
        # 天文台
        "update_time": curr.get("update_time", ""),
        "weather": flw.get("forecast_desc", ""),
        "situation": flw.get("general_situation", ""),
        # 颱風 / 特殊天氣
        "tc_info": flw.get("tc_info", "") or "",
        "fire_danger": flw.get("fire_danger_warning") or "",
        # 日夜
        "sunrise": common.get("sunrise", ""),
        "sunset": common.get("sunset", ""),
        "lunar_date": hdr.get("lunar_date", ""),
        "solar_term": hdr.get("solar_term", "") or "",
        # UV
        "uv_index": regional.get("uv_index", ""),
        "uv_intensity": regional.get("uv_intensity", ""),
        # 日期
        "date_display": hdr.get("date_display", ""),
        # 簡短描述（截取第一句，避免撐破排版）
        "weather_short": (flw.get("forecast_desc", "").split("。")[0] + "。") if flw.get("forecast_desc") else "",
    }


# ── legacy wrappers (keep backward compat) ──

async def fetch_openweathermap(api_key: str, city: str = "Hong Kong") -> Optional[dict]:
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
    """根據任務配置，調用對應的外部 API 並返回數據字典（用於模板變量注入）"""
    variables = {}

    if data_source in ("weather", "weather_map"):
        weather_vars = await fetch_weather_hko()
        if weather_vars:
            variables.update(weather_vars)

        # 高德後備
        amap_key = data_config.get("amap_key", "")
        if amap_key and not weather_vars:
            city_code = data_config.get("city_code", "440100")
            amap_vars = await fetch_amap_weather(amap_key, city_code)
            if amap_vars:
                variables.update(amap_vars)

        # OpenWeatherMap 覆蓋
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

    # 當前時間
    now = datetime.now()
    variables["now"] = now.strftime("%Y-%m-%d %H:%M:%S")
    variables["today"] = now.strftime("%Y-%m-%d")
    variables["time"] = now.strftime("%H:%M")
    variables["weekday"] = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]

    return variables


def resolve_custom_dates(custom_dates: list) -> dict:
    """解析自定義日期，生成倒計時/正計時變量"""
    variables = {}
    today = datetime.now().date()

    for cd in custom_dates:
        label = cd.get("label", "").strip()
        date_str = cd.get("date", "").strip()
        direction = cd.get("direction", "countdown")

        if not label or not date_str:
            continue

        try:
            target = datetime.strptime(date_str, "%Y-%m-%d").date()
            # 倒計時：過去日期自動推到下一年（每年重複）
            if direction == "countdown" and target < today:
                target = target.replace(year=today.year)
                if target < today:
                    target = target.replace(year=today.year + 1)
            delta = (target - today).days

            if direction == "countdown":
                key = f"{label}_倒數"
                variables[key] = f"{delta}天" if delta >= 0 else f"已過{-delta}天"
            else:
                key = f"{label}_天數"
                variables[key] = f"{delta}天"
        except (ValueError, TypeError):
            pass

    return variables
