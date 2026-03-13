import streamlit as st
import twstock
import pandas as pd
import datetime
import pytz
import time
import ssl  # 1. 新增這個匯入
import requests

# 2. 全域禁用 SSL 憑證檢查 (最直接的解法)
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# --- 以下維持原有的設定 ---

def fetch_stock_data(stock_id):
    """獲取股票即時資料"""
    try:
        # 在呼叫 twstock 之前，也可以手動測試連線 (選配)
        # requests.get('https://mis.twse.com.tw', verify=False)
        
        data = twstock.realtime.get(stock_id)
        if data and data['success']:
            info = data['info']
            realtime_data = data['realtime']
            
            # 確保資料格式正確
            price = realtime_data['latest_trade_price']
            vol = realtime_data['accumulate_trade_volume']
            
            result = {
                "股票代號": info['code'],
                "股票名稱": info['name'],
                "當前成交價": float(price) if price != '-' else "暫無成交",
                "當日累計成交量": int(vol) if vol != '-' else 0,
                "最後更新時間": info['time']
            }
            return result
        else:
            st.warning(f"證交所回傳失敗：{data.get('rtmessage', '未知錯誤')}")
    except Exception as e:
        # 這裡會捕捉到剛剛提到的 SSLError
        st.error(f"資料抓取失敗: {e}")
    return None

# ... 後續 UI 程式碼不變 ...
