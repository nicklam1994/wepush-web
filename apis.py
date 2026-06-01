"""External API integrations — HKO weather via weather_hko package."""
import sys
import os
import openpyxl
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
        field_name = cd.get("field_name", "").strip()
        date_str = cd.get("date", "").strip()
        direction = cd.get("direction", "countdown")

        if not field_name or not date_str:
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
                variables[field_name] = f"{delta}天"
            else:
                variables[field_name] = f"{-delta}天" if delta < 0 else f"{delta}天"
        except (ValueError, TypeError):
            pass

    return variables


# ─── 高德天氣 API v2（帶 adcode 自動查找）───

_adcode_cache: Optional[dict] = None


def _load_adcode_xlsx() -> dict:
    """懶加載高德 adcode xlsx，緩存為 {城市名: adcode}"""
    global _adcode_cache
    if _adcode_cache is not None:
        return _adcode_cache

    xlsx_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AMap_adcode_citycode.xlsx")
    if not os.path.exists(xlsx_path):
        _adcode_cache = {}
        return _adcode_cache

    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb["Sheet1"]
    _adcode_cache = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        name = row[0]
        adcode = row[1]
        if name and adcode is not None:
            _adcode_cache[str(name).strip()] = str(adcode).strip()
    wb.close()
    return _adcode_cache


def _lookup_adcode(city_name: str) -> Optional[str]:
    """根據城市名模糊匹配 adcode"""
    adcode_map = _load_adcode_xlsx()
    if not adcode_map:
        return None

    city_name = city_name.strip()

    # 繁簡轉換表（常見城市用字）
    _t2s = {
        "廣": "广", "臺": "台", "東": "东", "門": "门", "萬": "万",
        "區": "区", "號": "号", "縣": "县", "鎮": "镇", "雲": "云",
        "亞": "亚", "蕭": "萧", "為": "为", "豐": "丰", "長": "长",
        "蘇": "苏", "蘭": "兰", "連": "连", "鄭": "郑", "滬": "沪",
        "爾": "尔", "龍": "龙", "龜": "龟",
    }

    def _simplify(s: str) -> str:
        return "".join(_t2s.get(c, c) for c in s)

    # 精確匹配
    if city_name in adcode_map:
        return adcode_map[city_name]

    # 繁簡轉換後精確匹配
    simplified = _simplify(city_name)
    if simplified != city_name and simplified in adcode_map:
        return adcode_map[simplified]

    # 模糊匹配：去掉「市」「省」「自治区」等後綴
    suffixes = ["市", "省", "自治区", "特别行政区", "地區", "地区"]
    for suffix in suffixes:
        if city_name.endswith(suffix):
            base = city_name[:-len(suffix)]
            if base in adcode_map:
                return adcode_map[base]
            # 繁簡轉換後再試
            base_s = _simplify(base)
            if base_s != base and base_s in adcode_map:
                return adcode_map[base_s]
            # 嘗試加「市」
            if (base + "市") in adcode_map:
                return adcode_map[base + "市"]
            if (base_s + "市") in adcode_map:
                return adcode_map[base_s + "市"]
            # 嘗試加「省」
            if (base + "省") in adcode_map:
                return adcode_map[base + "省"]

    # 反向：給定名稱+市 來匹配
    if (city_name + "市") in adcode_map:
        return adcode_map[city_name + "市"]
    if (simplified + "市") in adcode_map:
        return adcode_map[simplified + "市"]

    # 部分匹配：檢查 adcode_map 中是否有 key 包含城市名
    # 優先：精確匹配 > 短 adcode（省/市級）> 長 adcode（區級）
    candidates = []
    for key, adcode in adcode_map.items():
        if city_name in key or simplified in key:
            # 計算匹配分數：adcode 越短越好（省級100000=6位, 市級440100=6位, 區級440101=6位）
            # 關鍵區分：後兩位為00的是市級
            score = 0
            if city_name == key or simplified == key:
                score += 100
            if adcode.endswith("0000"):  # 省級
                score += 50
            elif adcode.endswith("00"):  # 市級
                score += 30
            candidates.append((score, adcode))

    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]

    return None


async def fetch_amap_weather_v2(api_key: str, city: str = "香港") -> Optional[dict]:
    """高德天氣 API v2 — 自動查詢 adcode"""
    if not api_key:
        return None

    # 查找 adcode（從 xlsx）
    adcode = _lookup_adcode(city)
    if not adcode:
        adcode = "810000"  # default 香港

    url = "https://restapi.amap.com/v3/weather/weatherInfo"
    params = {"key": api_key, "city": adcode, "extensions": "base"}

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
        "report_time": live.get("reporttime", ""),
    }


async def fetch_openweather_v2(api_key: str, city: str = "Hong Kong") -> Optional[dict]:
    """OpenWeather Current Weather API (簡化版)"""
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
    main = data.get("main", {})
    wind = data.get("wind", {})
    weather_list = data.get("weather", [])
    weather_desc = weather_list[0].get("description", "") if weather_list else ""
    return {
        "temp": f"{main.get('temp', 'N/A')}°C",
        "feels_like": f"{main.get('feels_like', 'N/A')}°C",
        "humidity": f"{main.get('humidity', 'N/A')}%",
        "pressure": f"{main.get('pressure', 'N/A')}hPa",
        "weather": weather_desc,
        "wind_speed": f"{wind.get('speed', 'N/A')}m/s",
        "city": data.get("name", city),
    }
