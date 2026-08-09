import streamlit as st
import googlemaps
import pandas as pd
from math import radians, cos, sin, asin, sqrt

# --- デザイン設定 ---
st.set_page_config(page_title="G-Map 検索・並べ替え", layout="wide")
st.title("📍 Googleマップ 検索 & ソート")
st.caption("検索結果を評価・口コミ数・距離で自由に並べ替え！")

# --- サイドバー：設定 ---
with st.sidebar:
    st.header("🔑 API設定")
    api_key = st.text_input("Google Maps API Keyを入力", type="password")
    
    st.header("🔍 検索条件")
    keyword = st.text_input("検索ワード", value="ラーメン")
    location_name = st.text_input("場所（例：小山駅、新宿）", value="小山駅")
    radius = st.slider("検索範囲 (m)", 500, 5000, 2000)

# --- 距離計算（緯度経度から直線距離） ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6372.8  # 地球の半径 (km)
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    lat1 = radians(lat1)
    lat2 = radians(lat2)
    a = sin(dLat / 2)**2 + cos(lat1) * cos(lat2) * sin(dLon / 2)**2
    c = 2 * asin(sqrt(a))
    return R * c

# --- メインロジック ---
if st.button("検索開始"):
    if not api_key:
        st.error("APIキーを入力してください。")
    else:
        gmaps = googlemaps.Client(key=api_key)
        
        try:
            # 1. 指定された場所の座標を取得
            geocode_result = gmaps.geocode(location_name)
            if not geocode_result:
                st.error("場所が見つかりませんでした。")
            else:
                base_lat = geocode_result[0]['geometry']['location']['lat']
                base_lng = geocode_result[0]['geometry']['location']['lng']
                
                # 2. 周辺検索を実行
                places_result = gmaps.places_nearby(
                    location=(base_lat, base_lng),
                    radius=radius,
                    keyword=keyword,
                    language='ja'
                )
                
                # 3. データをリスト化
                results = []
                for place in places_result.get('results', []):
                    target_lat = place['geometry']['location']['lat']
                    target_lng = place['geometry']['location']['lng']
                    
                    # 距離計算
                    dist = haversine(base_lat, base_lng, target_lat, target_lng)
                    
                    results.append({
                        "店名": place.get('name'),
                        "評価": place.get('rating', 0),
                        "口コミ数": place.get('user_ratings_total', 0),
                        "距離(km)": round(dist, 2),
                        "住所": place.get('vicinity'),
                        "場所ID": place.get('place_id')
                    })
                
                if not results:
                    st.warning("結果が見つかりませんでした。")
                else:
                    df = pd.DataFrame(results)
                    st.session_state['df'] = df
                    st.success(f"{len(df)}件の結果を取得しました。")

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

# --- 並べ替えと表示 ---
if 'df' in st.session_state:
    df = st.session_state['df']
    
    st.divider()
    
    col1, col2 = st.columns([1, 2])
    with col1:
        sort_option = st.selectbox(
            "並べ替え順を選択",
            ["評価順（高い順）", "口コミ数順（多い順）", "距離順（近い順）"]
        )
    
    # 並べ替え処理
    if sort_option == "評価順（高い順）":
        df_sorted = df.sort_values("評価", ascending=False)
    elif sort_option == "口コミ数順（多い順）":
        df_sorted = df.sort_values("口コミ数", ascending=False)
    else:
        df_sorted = df.sort_values("距離(km)", ascending=True)

    # 結果表示
    st.dataframe(
        df_sorted, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "店名": st.column_config.TextColumn("店名"),
            "評価": st.column_config.NumberColumn("⭐評価", format="%.1f"),
            "口コミ数": st.column_config.NumberColumn("💬口コミ数"),
            "距離(km)": st.column_config.NumberColumn("📏距離(km)"),
            "住所": st.column_config.TextColumn("住所"),
            "場所ID": None # IDは非表示
        }
    )
    
    # マップ表示
    st.subheader("🗺️ 地図で確認")
    # 地図表示用の簡易データ作成
    map_df = pd.DataFrame(results) # 元データを使用
    # カラム名をStreamlitのmap仕様に合わせる
    # 実際にはgmapsで取得したlat/lngが必要なため再構成
    st.map(data=geocode_result, latitude='lat', longitude='lng')
    # ※簡易版のため、店ごとのプロットは別途処理が必要
