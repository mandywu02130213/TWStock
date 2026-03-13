import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz
import time

# 頁面基本設定
st.set_page_config(page_title="2330 即時監控", layout="wide")

def get_taiwan_time():
    """處理 Streamlit Cloud 時區問題"""
    tw_tz = pytz.timezone('Asia/Taipei')
    return datetime.datetime.now(tw_tz)

def fetch_2330_data():
    """使用 yfinance 抓取台積電資料"""
    try:
        # 台股代碼在 yfinance 中需加上 .TW
        ticker = yf.Ticker("2330.TW")
        # 抓取當天即時數據 (1分鐘層級)
        df = ticker.history(period="1d", interval="1m")
        if not df.empty:
            latest = df.iloc[-1]
            return {
                "price": round(latest['Close'], 2),
                "volume": int(latest['Volume'] / 1000), # 轉換為「張」
                "high": round(latest['High'], 2),
                "low": round(latest['Low'], 2),
                "time": df.index[-1].astimezone(pytz.timezone('Asia/Taipei')).strftime('%H:%M:%S')
            }
    except Exception as e:
        st.error(f"資料抓取失敗: {e}")
    return None

# --- UI 介面 ---
st.title("📈 台積電 (2330) 即時監控牆")

now = get_taiwan_time()
st.info(f"📅 台灣時間：{now.strftime('%Y-%m-%d %H:%M:%S')}")

# 檢查開盤狀態 (09:00 - 13:30)
is_open = (now.weekday() < 5) and (9 <= now.hour < 14)

# 執行抓取
data = fetch_2330_data()

if data:
    # 建立儀表板
    col1, col2, col3 = st.columns(3)
    col1.metric("成交價", f"{data['price']} TWD")
    col2.metric("當分鐘成交量", f"{data['volume']} 張")
    col3.metric("最後更新時間", data['time'])

    # 製作小表格
    st.write("### 今日盤中資訊")
    status_df = pd.DataFrame({
        "項目": ["當日最高", "當日最低", "監控狀態"],
        "數值": [f"{data['high']}", f"{data['low']}", "連線正常 (Yahoo Finance API)"]
    })
    st.table(status_df)
else:
    st.error("目前無法獲取資料，請稍後再試。")

# --- 自動刷新 ---
if is_open:
    st.write("🔄 市場交易中，每 5 秒自動更新...")
    time.sleep(5)
    st.rerun()
else:
    st.write("😴 目前非交易時段，停止自動刷新以節省資源。")
    if st.button("手動刷新"):
        st.rerun()
