import streamlit as st
import twstock
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# 設定網頁標題與圖示
st.set_page_config(page_title="台股即時監控 - 2330", page_icon="📈")

# --- 自動更新設定 ---
# 每 5000 毫秒 (5秒) 刷新一次網頁
count = st_autorefresh(interval=5000, limit=None, key="stock_refresh")

def get_stock_data(stock_code):
    try:
        # 使用 twstock 抓取即時資料
        data = twstock.realtime.get(stock_code)
        if data['success']:
            return data
        else:
            return None
    except Exception as e:
        st.error(f"抓取資料發生錯誤: {e}")
        return None

# --- UI 介面設計 ---
st.title("🚀 台股即時監控系統")
st.subheader(f"監控目標：2330 台積電")
st.caption(f"最後更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 獲取資料
realtime_data = get_stock_data('2330')

if realtime_data:
    info = realtime_data['info']
    realtime = realtime_data['realtime']
    
    # 1. 關鍵指標卡片 (成交價、成交量)
    col1, col2, col3 = st.columns(3)
    
    # 成交價
    latest_price = realtime['latest_trade_price']
    if latest_price == '-': # 盤前或暫無成交
        latest_price = realtime['best_bid_price'][0]
        
    col1.metric("當前成交價", f"{latest_price} 元")
    col2.metric("當日成交量", f"{realtime['accumulate_trade_volume']} 張")
    col3.metric("今日最高/最低", f"{realtime['high']} / {realtime['low']}")

    st.divider()

    # 2. 盤中即時細節
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.write("### 📈 買進報價 (Bid)")
        # 整理買進五檔
        bid_df = {
            "價格": realtime['best_bid_price'],
            "張數": realtime['best_bid_volume']
        }
        st.table(bid_df)

    with col_b:
        st.write("### 📉 賣出報價 (Ask)")
        # 整理賣出五檔
        ask_df = {
            "價格": realtime['best_ask_price'],
            "張數": realtime['best_ask_volume']
        }
        st.table(ask_df)

else:
    st.warning("無法取得即時資料，請確認是否為開盤時間或網路連接正常。")

# 腳註說明
st.info("註：twstock 資料來源為證交所即時資訊，可能會有數秒延遲。請注意 API 請求頻率限制。")
