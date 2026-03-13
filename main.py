import streamlit as st
import twstock
import pandas as pd
import datetime
import pytz
import time
import requests
import urllib3

# --- 關鍵修正：解決 Streamlit Cloud 的 SSL 憑證問題 ---
# 1. 禁用警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 2. 強制讓 requests 預設不驗證 SSL (針對 twstock 底層)
session = requests.Session()
session.verify = False
requests.get = session.get
# --------------------------------------------------

st.set_page_config(page_title="2330 即時監控", layout="wide")

def get_taiwan_time():
    """處理 Streamlit Cloud 時區，確保與台灣同步"""
    tw_tz = pytz.timezone('Asia/Taipei')
    return datetime.datetime.now(tw_tz)

@st.cache_data(ttl=3)
def fetch_stock_data(stock_id):
    """獲取股票即時資料"""
    try:
        # 這裡 twstock 會呼叫被我們修改過的 requests
        data = twstock.realtime.get(stock_id)
        if data and data['success']:
            return data
    except Exception as e:
        st.error(f"連線異常: {e}")
    return None

# --- UI 介面 ---
st.title("🚀 台積電 (2330) 即時監控牆")

now = get_taiwan_time()
st.info(f"📅 台灣時間：{now.strftime('%Y-%m-%d %H:%M:%S')}")

# 判斷開盤狀態
is_weekday = now.weekday() < 5
is_market_time = (datetime.time(9, 0) <= now.time() <= datetime.time(13, 35))
is_open = is_weekday and is_market_time

if not is_open:
    st.warning("⚠️ 目前非交易時段，資料可能為最後收盤價或不更新。")

# 獲取資料
raw_data = fetch_stock_data('2330')

if raw_data:
    info = raw_data['info']
    realtime = raw_data['realtime']
    
    # 數值處理（處理可能為 '-' 的情況）
    def clean_val(val):
        return val if val != '-' else "0"

    price = clean_val(realtime['latest_trade_price'])
    vol = clean_val(realtime['accumulate_trade_volume'])
    high = clean_val(realtime['high'])
    low = clean_val(realtime['low'])
    open_p = clean_val(realtime['open'])

    # 建立儀表板
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("成交價", f"{price} TWD")
    m2.metric("成交量", f"{vol} 張")
    m3.metric("今日最高", f"{high}")
    m4.metric("今日最低", f"{low}")

    # 整理表格
    df_data = {
        "指標項目": ["股票代碼", "名稱", "開盤價", "更新時間"],
        "數值": [info['code'], info['name'], open_p, info['time']]
    }
    st.table(pd.DataFrame(df_data))
else:
    st.error("❌ 無法從證交所抓取資料。這通常是 IP 被暫時限制或證交所主機維護。")

# --- 自動更新機制 ---
# 考慮到 Streamlit Cloud 效能與安全性，建議設為 10 秒
# 若堅持 5 秒請改為 time.sleep(5)
st.divider()
st.caption("系統將在 10 秒後自動刷新...")
time.sleep(10)
st.rerun()
