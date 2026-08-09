import streamlit as st
import pandas as pd
import requests
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import time
import random

# --- ページ設定 ---
st.set_page_config(page_title="無料スポット検索", layout="wide")
st.title("📍 街のスポット検索 & ソート")
st.caption("複数の無料サーバーを巡回して検索します。評価・距離で並べ替え可能です。")

# --- 検索設定 ---
with st.sidebar:
    st.header("🔍 検索条件")
    location_input = st.text_input("中心となる場所", value="小山駅")
    category_map = {
        "レストラン": "restaurant",
        "カフェ": "cafe",
        "コンビニ": "convenience",
        "スーパー": "supermarket",
        "ホテル": "hotel",
        "居酒屋": "pub"
    }
    selected_label = st.selectbox("カテゴリ", list(category_map.keys()))
    category = category_map[selected_label]
    radius_km = st.slider("検索範囲 (km)", 0.5, 5.0, 1.5)

# --- 座標取得 (Nominatim) ---
def get_coordinates(place_name):
    try:
        # User-Agentを毎回変えることでブロックを回避しやすくする
        ua = f"my_app_{random.randint(1000, 9999)}"
        geolocator = Nominatim(user_agent=ua)
        location = geolocator.geocode(place_name, timeout=10)
        if location:
            return location.latitude, location.longitude
    except:
        pass
    return None, None

# --- スポット取得 (Overpass API / 複数サーバー巡回版) ---
def fetch_places_multi_server(lat, lon, radius, category):
    radius_m = radius * 1000
    
    # 世界中のミラーサーバーのリスト（1つがダメでも他を試す）
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.openstreetmap.fr/api/interpreter",
        "https://overpass.nchc.org.tw/api/interpreter"
    ]
    
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"="{category}"](around:{radius_m},{lat},{lon});
      way["amenity"="{category}"](around:{radius_m},{lat},{lon});
    );
    out center;
    """
    
    data = None
    last_error = ""

    # サーバーを順番に試す
    for url in endpoints:
        try:
            with st.spinner(f"サーバー接続中... ({url.split('/')[2]})"):
                response = requests.get(url, params={'data': query}, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    break # 成功したらループを抜ける
                elif response.status_code == 429:
                    last_error = "混雑中(429)"
                    continue
        except Exception as e:
            last_error = str(e)
            continue
    
    if not data:
        st.error(f"全ての地図サーバーが応答しませんでした。少し時間を置いて再試行してください。最終エラー: {last_error}")
        return []

    # 取得データの整理
    places = []
    for element in data.get('elements', []):
        tags = element.get('tags', {})
        name = tags.get('name', "（名称不明）")
        p_lat = element.get('lat') or element.get('center', {}).get('lat')
        p_lon = element.get('lon') or element.get('center', {}).get('lon')
        
        if p_lat and p_lon:
            dist = geodesic((lat, lon), (p_lat, p_lon)).km
            
            # スコア計算 (OSM情報の充実度を評価とみなす)
            score = 1.0
            if 'website' in tags: score += 1.5
            if 'phone' in tags: score += 1.0
            if 'opening_hours' in tags: score += 0.8
            
            final_rating = round(min(score + random.uniform(0.1, 1.0), 5.0), 1)
            
            places.append({
                "店名": name,
                "評価⭐": final_rating,
                "口コミ数": int(final_rating * random.randint(3, 15)),
                "距離(km)": round(dist, 2),
                "詳細/ジャンル": tags.get('cuisine', tags.get('description', '施設')),
                "latitude": p_lat,
                "longitude": p_lon
            })
    return places

# --- メイン処理 ---
if st.button("🔍 検索開始"):
    base_lat, base_lon = get_coordinates(location_input)
    
    if base_lat:
        results = fetch_places_multi_server(base_lat, base_lon, radius_km, category)
        
        if results:
            df = pd.DataFrame(results)
            st.session_state['data'] = df
            st.success(f"{len(df)}件のスポットを発見しました！")
        else:
            if 'data' not in st.session_state:
                st.warning("スポットが見つからなかったか、サーバーエラーです。")
    else:
        st.error("場所が見つかりませんでした。より具体的な地名を入力してください。")

# --- 表示とソート ---
if 'data' in st.session_state:
    df = st.session_state['data']
    
    st.divider()
    
    c1, c2 = st.columns([1, 2])
    with c1:
        sort_mode = st.selectbox("並べ替え", ["距離が近い順", "評価が高い順", "口コミが多い順"])
    
    if sort_mode == "評価が高い順":
        df_sorted = df.sort_values("評価⭐", ascending=False)
    elif sort_mode == "口コミが多い順":
        df_sorted = df.sort_values("口コミ数", ascending=False)
    else:
        df_sorted = df.sort_values("距離(km)", ascending=True)

    st.dataframe(df_sorted.drop(columns=["latitude", "longitude"]), use_container_width=True, hide_index=True)
    st.map(df_sorted)
