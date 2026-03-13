import streamlit as st
import twstock
import pandas as pd
import datetime
import pytz
import time

# 設定網頁標題
st.set_page_config(page_title="台股即時監控 - 2330", layout="centered")

def get_taiwan_time():
    """處理 Streamlit Cloud 時區問題，統一轉換為台灣時間"""
    tw_tz = pytz.timezone('Asia/Taipei')
    return datetime.datetime.now(tw_tz)

def fetch_stock_data(stock_id):
    """獲取股票即時資料"""
    try:
        # 獲取即時資料
        data = twstock.realtime.get(stock_id)
        if data and data['success']:
            info = data['info']
            realtime_data = data['realtime']
            
            # 整理成字典
            result = {
                "股票代號": info['code'],
                "股票名稱": info['name'],
                "當前成交價": float(realtime_data['latest_trade_price']) if realtime_data['latest_trade_price'] != '-' else "暫無成交",
                "當日累計成交量": realtime_data['accumulate_trade_volume'],
                "最後更新時間": info['time']
            }
            return result
    except Exception as e:
        st.error(f"資料抓取失敗: {e}")
    return None

# --- UI 介面 ---
st.title("📈 2330 台積電即時監控")

# 顯示當前台灣時間
now = get_taiwan_time()
st.write(f"目前台灣時間：{now.strftime('%Y-%m-%d %H:%M:%S')}")

# 檢查是否在開盤時間 (09:00 - 13:30)
is_market_open = (now.hour == 9 and now.minute >= 0) or (10 <= now.hour < 13) or (now.hour == 13 and now.min <= 30)

if is_market_open:
    st.success("市場交易中")
else:
    st.warning("目前為非交易時段，顯示最後收盤資料")

# 獲取資料
stock_data = fetch_stock_data('2330')

if stock_data:
    # 使用 Metric 顯示大字報
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="成交價", value=f"{stock_data['當前成交價']} TWD")
    with col2:
        st.metric(label="成交量", value=f"{stock_data['當日累計成交量']} 張")

    # 顯示詳細表單
    st.table(pd.DataFrame([stock_data]))
else:
    st.error("無法取得資料，請檢查網路或 twstock 狀態")

# --- 自動刷新邏輯 ---
# 每 5 秒自動重新整理頁面
time.sleep(5)
st.rerun()
