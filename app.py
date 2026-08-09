import streamlit as st
import pandas as pd
import requests
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import time

# --- デザイン設定 ---
st.set_page_config(page_title="無料スポット検索・ソート", layout="wide")
st.title("🗺️ 検索・並べ替えアプリ (API不要版)")
st.caption("OpenStreetMapのデータを使用して、評価(推定)・距離で並べ替えます。")

# --- サイドバー：検索条件 ---
with st.sidebar:
    st.header("🔍 検索設定")
    location_input = st.text_input("中心となる場所", value="小山駅")
    keyword = st.selectbox("カテゴリ", ["restaurant", "cafe", "convenience", "supermarket", "school"], index=0)
    radius_km = st.slider("検索範囲 (km)", 1.0, 10.0, 2.0)

# --- 中心座標の取得 (Nominatim) ---
def get_coordinates(place_name):
    try:
        geolocator = Nominatim(user_agent="my_map_app_v1")
        location = geolocator.geocode(place_name)
        if location:
            return location.latitude, location.longitude
    except:
        return None, None
    return None, None

# --- 周辺スポットの取得 (Overpass API) ---
def fetch_places(lat, lon, radius, category):
    # Overpass APIのクエリ (指定座標の周囲radiusメートルからカテゴリに一致するものを探す)
    radius_m = radius * 1000
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    (
      node["amenity"="{category}"](around:{radius_m},{lat},{lon});
      way["amenity"="{category}"](around:{radius_m},{lat},{lon});
    );
    out center;
    """
    response = requests.get(overpass_url, params={'data': overpass_query})
    data = response.json()
    
    places = []
    for element in data.get('elements', []):
        name = element.get('tags', {}).get('name', "名称不明")
        
        # 座標取得 (nodeならそのまま、wayならcenter)
        p_lat = element.get('lat') or element.get('center', {}).get('lat')
        p_lon = element.get('lon') or element.get('center', {}).get('lon')
        
        if p_lat and p_lon:
            # 距離計算
            dist = geodesic((lat, lon), (p_lat, p_lon)).km
            
            # 評価の代用スコア (Webサイトや電話番号が登録されているかなど)
            tags = element.get('tags', {})
            score = 0.0
            if 'website' in tags: score += 2.0
            if 'phone' in tags: score += 1.0
            if 'opening_hours' in tags: score += 1.0
            # 少しランダム性を加えて、ソートを面白くする (本来は口コミ数ですがOSMにはないため)
            import random
            score += random.uniform(0.5, 1.0)
            
            places.append({
                "店名": name,
                "推定評価": round(min(score, 5.0), 1), # 最大5.0
                "口コミ(推定)": int(score * 10), # スコアに比例
                "距離(km)": round(dist, 2),
                "詳細": tags.get('cuisine', tags.get('shop', '施設')),
                "緯度": p_lat,
                "経度": p_lon
            })
    return places

# --- メイン処理 ---
if st.button("検索開始"):
    with st.spinner("位置情報を取得中..."):
        base_lat, base_lon = get_coordinates(location_input)
        
        if base_lat:
            with st.spinner(f"{location_input} 周辺のスポットを検索中..."):
                results = fetch_places(base_lat, base_lon, radius_km, keyword)
                
                if results:
                    df = pd.DataFrame(results)
                    st.session_state['map_df'] = df
                    st.success(f"{len(df)}件のスポットが見つかりました！")
                else:
                    st.warning("スポットが見つかりませんでした。")
        else:
            st.error("入力された場所が見つかりませんでした。")

# --- ソートと表示 ---
if 'map_df' in st.session_state:
    df = st.session_state['map_df']
    
    st.divider()
    
    col1, col2 = st.columns([1, 2])
    with col1:
        sort_opt = st.selectbox(
            "並べ替え順",
            ["評価が高い順", "口コミが多い順", "距離が近い順"]
        )
    
    if sort_opt == "評価が高い順":
        df = df.sort_values("推定評価", ascending=False)
    elif sort_opt == "口コミが多い順":
        df = df.sort_values("口コミ(推定)", ascending=False)
    else:
        df = df.sort_values("距離(km)", ascending=True)

    # テーブル表示
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # マップ表示
    st.subheader("🗺️ 地図")
    st.map(df, latitude="緯度", longitude="経度")
