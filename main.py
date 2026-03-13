import streamlit as st
import gspread
import time
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import urllib3
from FinMind.data import DataLoader
import pytz  # 新增時區處理模組
import yfinance as yf

# 關閉不安全請求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 定義台灣時區
tw_tz = pytz.timezone('Asia/Taipei')

# FinMind 設定
FINMIND_TOKEN = st.secrets["finmind"]["token"]
dl = DataLoader()
dl.login_by_token(api_token=FINMIND_TOKEN)

# 預估量因子
EST_FACTORS = {
    "09:05": 14.99, "09:10": 9.48, "09:15": 7.12, "09:20": 5.83, "09:25": 4.99,
    "09:30": 4.42, "09:35": 3.99, "09:40": 3.66, "09:45": 3.39, "09:50": 3.18,
    "09:55": 2.99, "10:00": 2.83, "10:05": 2.70, "10:10": 2.58, "10:15": 2.48,
    "10:20": 2.39, "10:25": 2.30, "10:30": 2.23, "10:35": 2.15, "10:40": 2.09,
    "10:45": 2.03, "10:50": 1.97, "10:55": 1.92, "11:00": 1.87, "11:05": 1.83,
    "11:10": 1.79, "11:15": 1.74, "11:20": 1.71, "11:25": 1.67, "11:30": 1.63,
    "11:35": 1.60, "11:40": 1.57, "11:45": 1.54, "11:50": 1.51, "11:55": 1.48,
    "12:00": 1.46, "12:05": 1.43, "12:10": 1.41, "12:15": 1.38, "12:20": 1.36,
    "12:25": 1.34, "12:30": 1.32, "12:35": 1.30, "12:40": 1.28, "12:45": 1.25,
    "12:50": 1.23, "12:55": 1.21, "13:00": 1.19, "13:05": 1.17, "13:10": 1.14,
    "13:15": 1.12, "13:20": 1.09, "13:25": 1.06, "13:30": 1.00,
}

def get_est_factor(time_str):
    if time_str >= "13:30": return 1.0
    keys = sorted(EST_FACTORS.keys())
    if time_str < "09:05": return 14.99
    for k in keys:
        if time_str <= k: return EST_FACTORS[k]
    return 1.0

def is_market_open():
    now = datetime.now(tw_tz)  # 使用台灣時間
    if now.weekday() < 5 and "09:00" <= now.strftime("%H:%M") <= "13:35":
        return True
    return False

def check_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if not st.session_state.logged_in:
        st.subheader("🔐 系統登入")
        user_input = st.text_input("請輸入授權帳號", type="default")
        allowed_users = st.secrets["auth"]["allowed_users"]
        if st.button("進入系統"):
            if user_input in allowed_users:
                st.session_state.logged_in = True
                st.session_state.current_user = user_input
                st.success("登入成功！")
                st.rerun()
            else:
                st.error("帳號錯誤，請聯繫管理員。")
        st.stop()

st.set_page_config(page_title="台股 1-15 項極速監控", layout="wide")
check_login()

def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

client = init_connection()
GSHEET_KEY = st.secrets["gspread"]["sheet_key"]
spreadsheet = client.open_by_key(GSHEET_KEY)
sheet1 = spreadsheet.get_worksheet(0) 
sheet2 = spreadsheet.get_worksheet(1) 

current_user = st.session_state.current_user

st.title("📈 股票參數永久保存系統")
st.caption(f"當前使用者：{current_user}")

with st.sidebar:
    if st.button("🚪 登出系統"):
        st.session_state.logged_in = False
        st.rerun()
    st.header("📂 群組管理")
    new_group_name = st.text_input("建立新群組名稱")
    if st.button("➕ 建立群組", use_container_width=True):
        if new_group_name:
            sheet2.append_row([current_user, new_group_name])
            st.success(f"群組 '{new_group_name}' 建立成功！")
            st.rerun()
    st.divider()
    group_data = sheet2.get_all_records()
    df_groups = pd.DataFrame(group_data)
    user_groups = df_groups[df_groups["username"] == current_user]["class"].tolist() if not df_groups.empty else []
    st.header("⚙️ 參數設定")
    with st.form("input_form"):
        stock_no = st.text_input("股票代號 (No)")
        category = st.selectbox("分類 (Class)", user_groups if user_groups else ["請先建立群組"], disabled=not user_groups)
        day_a = st.number_input("天數 A (day_a)", min_value=1, value=5)
        day_b = st.number_input("天數 B (day_b)", min_value=1, value=20)
        day_c = st.number_input("天數 C (day_c)", min_value=1, value=60)
        submitted = st.form_submit_button("💾 儲存", use_container_width=True)
    st.divider()
    st.header("🗑️ 移除股票")
    
    # 讓使用者先選群組，再選股票
    if user_groups:
        del_group = st.selectbox("選擇群組", user_groups, key="del_group_select")
        
        # 過濾出該群組的股票
        records = sheet1.get_all_records()
        df_all = pd.DataFrame(records)
        target_stocks = df_all[(df_all["username"] == current_user) & (df_all["class"] == del_group)]
        
        if not target_stocks.empty:
            # 建立顯示名稱清單
            stock_list = target_stocks["no"].astype(str).tolist()
            to_delete = st.selectbox("選擇要移除的股票", ["-- 請選擇 --"] + stock_list)
            
            if to_delete != "-- 請選擇 --":
                if st.button("🔥 執行刪除", type="primary", use_container_width=True):
                    # 執行刪除邏輯
                    match = target_stocks[target_stocks["no"].astype(str) == to_delete]
                    if not match.empty:
                        # 計算在原始 sheet1 中的行號 (DataFrame index 從0開始，加2補回標題列與1-based)
                        # 注意：這裡要從 df_all 找回正確的 index
                        total_match = df_all[(df_all["username"] == current_user) & (df_all["no"].astype(str) == to_delete)]
                        idx = total_match.index[0] + 2
                        sheet1.delete_rows(int(idx))
                        st.success(f"已移除 {to_delete}")
                        time.sleep(1)
                        st.rerun()
        else:
            st.caption("此群組目前無股票")

if submitted and stock_no:
    records = sheet1.get_all_records()
    df_existing = pd.DataFrame(records)
    now_time = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")  # 使用台灣時間
    existing_row_index = None
    if not df_existing.empty:
        match = df_existing[(df_existing["username"] == current_user) & (df_existing["no"].astype(str) == str(stock_no))]
        if not match.empty: existing_row_index = match.index[0]
    if existing_row_index is not None:
        row_to_update = int(existing_row_index) + 2
        sheet1.update_cell(row_to_update, 1, now_time)
        sheet1.update_cell(row_to_update, 4, day_a); sheet1.update_cell(row_to_update, 5, day_b); sheet1.update_cell(row_to_update, 6, day_c)
        sheet1.update_cell(row_to_update, 7, category)
        st.sidebar.success(f"🔄 {stock_no} 已更新！")
        st.rerun()
    else:
        sheet1.append_row([now_time, current_user, stock_no, day_a, day_b, day_c, category])
        st.sidebar.success(f"✅ {stock_no} 已新增！")
        st.rerun()

@st.dialog("確認刪除股票")
def delete_stock_confirm(stock_no, current_user):
    st.warning(f"確定要從清單中永久移除 {stock_no} 嗎？")
    if st.button("確認移除", type="primary", use_container_width=True):
        records = sheet1.get_all_records()
        df = pd.DataFrame(records)
        match = df[(df["username"] == current_user) & (df["no"].astype(str) == str(stock_no))]
        if not match.empty:
            sheet1.delete_rows(match.index[0] + 2)
            st.success("已成功刪除！")
            time.sleep(0.5)
            st.rerun()

@st.cache_data(ttl=3600)
def get_history_finmind(stock_no, days):
    # 抓取稍多天數確保過濾假日後天數足夠
    start_date = (datetime.now(tw_tz) - timedelta(days=days*3)).strftime("%Y-%m-%d")
    df = dl.taiwan_stock_daily(stock_id=stock_no, start_date=start_date)
    if df.empty: return None
    df = df.tail(days)
    return {"prices": df["close"].tolist(), "volumes": (df["Trading_Volume"] / 1000).tolist()}

def get_realtime_twse(stock_no):
    try:
        timestamp = int(time.time() * 1000)
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{stock_no}.tw&json=1&delay=0&_={timestamp}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://mis.twse.com.tw/stock/fibest.jsp",
        }
        resp = requests.get(url, headers=headers, timeout=5, verify=False)
        json_data = resp.json()
        if not json_data.get("msgArray"):
            return None
        info = json_data["msgArray"][0]
        z = info.get("z", "-")
        y = float(info.get("y", 0))
        if z != "-" and float(z) != 0:
            latest_price = float(z)
        else:
            b_list = info.get("b", "").split("_")
            latest_price = float(b_list[0]) if b_list[0] and b_list[0] != "-" else y

        return {
            "name": info.get("n", ""),
            "price": latest_price,
            "volume": int(info.get("v", 0)) * 1000,
            "yesterday_close": y,
            "time": info.get("t", ""),
            "sys_time": datetime.now().strftime("%H:%M:%S"),
        }
    except:
        return None
    # try:

    #     ts = int(time.time() * 1000)
    #     # headers = {
    #     #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    #     #     "Referer": "https://mis.twse.com.tw/"
    #     # }
    #     for prefix in ["tse", "otc"]:
    #         url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={prefix}_{stock_no}.tw&json=1&delay=0&_={ts}"
    #         resp = requests.get(url,  timeout=5, verify=False)
    #         data = resp.json()
    #         if data.get("msgArray"):
    #             info = data["msgArray"][0]
    #             z = info.get("z", "-")
    #             y = float(info.get("y", 0))
    #             price = float(z) if z != "-" and float(z) != 0 else float(info.get("b", "0").split("_")[0])
    #             return {"name": info.get("n", ""), "price": price, "volume": int(info.get("v", 0)), "yesterday_close": y}
    #     return None
    # except: return None

def style_dataframe(df):
    def highlight_ratio(val):
        try:
            num = float(str(val).replace('%', ''))
            return 'background-color: #ffcccc; color: black; font-weight: bold' if num < 5.0 else ''
        except: return ''
    return df.style.applymap(highlight_ratio, subset=['5.線價比'])

# --- 主畫面更新邏輯 ---
refresh_rate = 10.0 if is_market_open() else None

@st.fragment(run_every=refresh_rate)
def update_stock_tables():
    s_data = sheet1.get_all_records()
    st.write(f"讀取到 {len(s_data)} 筆原始資料") # 測試點 2
    alert_container = st.container()
    
    g_data = sheet2.get_all_records()
    df_g = pd.DataFrame(g_data)
    user_classes = df_g[df_g["username"] == current_user]["class"].unique().tolist() if not df_g.empty else []
    
    s_data = sheet1.get_all_records()
    df_s = pd.DataFrame(s_data)
    user_stocks_df = df_s[df_s["username"] == current_user] if not df_s.empty else pd.DataFrame()

    if not user_classes:
        st.info("請先在左側建立群組。")
        return

    alerts = []
    tabs = st.tabs([f"📂 {c}" for c in user_classes])

    for i, group_name in enumerate(user_classes):
        with tabs[i]:
            group_stocks = user_stocks_df[user_stocks_df["class"] == group_name]
            if group_stocks.empty:
                st.write("此群組尚無股票。")
                continue

            all_rows = []
            for _, row in group_stocks.iterrows():
                stock_no = str(row['no']).split('.')[0].zfill(4)
                day_a, day_b, day_c = int(row['day_a']), int(row['day_b']), int(row['day_c'])
                
                max_d = max(day_a, day_b, day_c, 5)
                hist = get_history_finmind(stock_no, max_d)
                real = get_realtime_twse(stock_no)
                if not real:
                    # 嘗試從歷史資料 hist 拿最後一筆收盤價當作參考
                    if hist and len(hist["prices"]) > 0:
                        real = {
                            "name": f"{stock_no}(未連線)", 
                            "price": hist["prices"][-1], 
                            "volume": hist["volumes"][-1], 
                            "yesterday_close": hist["prices"][-1]
                        }
                    else:
                        continue # 如果連歷史資料都沒，才跳過
                # if real is None:
                #     st.warning(f"無法取得 {stock_no} 的即時行情，請檢查 Logs")
                # if not hist or not real: continue

                fm_prices = hist["prices"]
                fm_vols = hist["volumes"]
                
                market_open = is_market_open()
                has_today_data = (real["volume"] > 0)
                current_price = real["price"]
                current_vol = real["volume"]

                def calculate_ma_custom(n, prices, cur_p, is_open, has_data):
                    if is_open or has_data:
                        last_n_minus_1 = prices[-(n-1):] if n > 1 else []
                        ma_val = (sum(last_n_minus_1) + cur_p) / n
                        debug_ma = f"({'+'.join(map(str, last_n_minus_1))}+{cur_p})/{n}"
                    else:
                        last_n = prices[-n:]
                        ma_val = sum(last_n) / n
                        debug_ma = f"({'+'.join(map(str, last_n))})/{n}"
                    return ma_val, debug_ma

                ma_a, dbg_ma_a = calculate_ma_custom(day_a, fm_prices, current_price, market_open, has_today_data)
                ma_b, dbg_ma_b = calculate_ma_custom(day_b, fm_prices, current_price, market_open, has_today_data)
                ma_c, dbg_ma_c = calculate_ma_custom(day_c, fm_prices, current_price, market_open, has_today_data)

                if market_open or has_today_data:
                    last_4_v = fm_vols[-4:]
                    mv5_custom = (sum(last_4_v) + current_vol) / 5
                    dbg_mv5 = f"({'+'.join(map(str, last_4_v))}+{current_vol})/5"
                    formula_type = "即時/盤後"
                else:
                    last_5_v = fm_vols[-5:]
                    mv5_custom = sum(last_5_v) / 5
                    dbg_mv5 = f"({'+'.join(map(str, last_5_v))})/5"
                    formula_type = "假日/無開盤"

                print(f"[{datetime.now(tw_tz).strftime('%H:%M:%S')}] 股票: {stock_no} | 模式: {formula_type}")
                print(f"  > MA A ({day_a}日) 算式: {dbg_ma_a} = {ma_a:.2f}")
                print(f"  > MV5 (5日均量) 算式: {dbg_mv5} = {mv5_custom:.2f}")

                diff = current_price - real["yesterday_close"]
                diff_pct = (diff / real["yesterday_close"] * 100) if real["yesterday_close"] != 0 else 0
                price_ma_diff = ((current_price - ma_a) / ma_a * 100) if ma_a != 0 else 0
                
                curr_t = datetime.now(tw_tz).strftime("%H:%M")  # 使用台灣時間
                factor = get_est_factor(curr_t)
                est_vol = current_vol * factor
                vol_ratio = (est_vol / mv5_custom) if mv5_custom > 0 else 0

                if vol_ratio > 2.0 or price_ma_diff < 5.0:
                    alerts.append(f"{stock_no} {real['name']}")

                def fmt(val):
                    if isinstance(val, (int, float)):
                        return f"{val:g}"
                    return val

                all_rows.append({
                    "1.代號": stock_no, 
                    "2.名稱": real["name"], 
                    "3.成交價": fmt(current_price), 
                    "4.漲跌(%)": f"{diff:g} ({diff_pct:.2f}%)", 
                    "5.線價比": f"{price_ma_diff:.2f}%", 
                    "6.均線A": fmt(round(ma_a, 2)), 
                    "7.天數A": day_a, 
                    "8.均線B": fmt(round(ma_b, 2)), 
                    "9.天數B": day_b, 
                    "10.均線C": fmt(round(ma_c, 2)), 
                    "11.天數C": day_c, 
                    "12.成交張數": int(current_vol), 
                    "13.量增比": f"{vol_ratio:.2f}", 
                    "14.五日均量": fmt(round(mv5_custom, 2)), 
                    "15.預估量": int(round(est_vol, 0))
                })

            if all_rows:
                st.dataframe(style_dataframe(pd.DataFrame(all_rows)), use_container_width=True, hide_index=True)


    if alerts:
        with alert_container:
            st.error(f"🚨 異常監控警示 (量增>2 或 線價<5%): {', '.join(alerts)}")

    # 底部狀態列更新時間改為台灣時間
    st.caption(f"最後更新時間：{datetime.now(tw_tz).strftime('%H:%M:%S')} {'(自動監控中)' if is_market_open() else '(非交易時段)'}")

update_stock_tables()

