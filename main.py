import streamlit as st
import gspread
import time
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import requests
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

check_login()
st.set_page_config(page_title="台股即時監控", layout="wide")

def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

client = init_connection()
spreadsheet = client.open_by_key("10Oz6imH-bywS6sk23HquvgUw-3rKHLMU4g8MCC8ek-M")
sheet1 = spreadsheet.get_worksheet(0)
sheet2 = spreadsheet.get_worksheet(1)

current_user = st.session_state.current_user

st.title("🚀 台股即時行情監控")
st.caption(f"當前使用者：{current_user}")

# --- 側邊欄：管理功能 ---
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

    st.header("⚙️ 股票設定")
    with st.form("input_form"):
        stock_no = st.text_input("股票代號")
        category = st.selectbox("分配群組", user_groups if user_groups else ["請先建立群組"], disabled=not user_groups)
        submitted = st.form_submit_button("💾 儲存股票", use_container_width=True)

if submitted and stock_no:
    records = sheet1.get_all_records()
    df_existing = pd.DataFrame(records)
    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 檢查是否已存在，不存在則新增
    match = df_existing[(df_existing["username"] == current_user) & (df_existing["no"].astype(str) == str(stock_no))] if not df_existing.empty else pd.DataFrame()
    
    if match.empty:
        new_row = [now_time, current_user, stock_no, 0, 0, 0, category] # 保留欄位結構以相容舊表
        sheet1.append_row(new_row)
        st.sidebar.success(f"✅ {stock_no} 已新增！")
        st.rerun()
    else:
        st.sidebar.info(f"ℹ️ {stock_no} 已在清單中。")

# --- 即時資料抓取 ---
def get_realtime_info(stock_no):
    try:
        timestamp = int(time.time() * 1000)
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{stock_no}.tw&json=1&delay=0&_={timestamp}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=5, verify=False)
        json_data = resp.json()
        if not json_data.get("msgArray"): return None
        
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
            "volume": int(info.get("v", 0)),
            "yesterday_close": y,
            "high": info.get("h", "-"),
            "low": info.get("l", "-"),
        }
    except:
        return None

# --- 資料顯示區域 ---
@st.fragment(run_every=10.0)
def update_stock_tables():
    group_data = sheet2.get_all_records()
    df_groups = pd.DataFrame(group_data)
    all_class = df_groups[df_groups["username"] == current_user]["class"].unique().tolist() if not df_groups.empty else []

    records = sheet1.get_all_records()
    df_records = pd.DataFrame(records)
    user_df = df_records[df_records["username"] == current_user] if not df_records.empty else pd.DataFrame()

    for group in all_class:
        st.subheader(f"📁 {group}")
        group_df = user_df[user_df["class"] == group] if not user_df.empty else pd.DataFrame()
        
        display_list = []
        for _, row in group_df.iterrows():
            user_stock = str(row["no"]).split(".")[0].zfill(4)
            realtime = get_realtime_info(user_stock)

            if realtime:
                diff = realtime["price"] - realtime["yesterday_close"]
                diff_percent = (diff / realtime["yesterday_close"]) * 100 if realtime["yesterday_close"] != 0 else 0
                
                display_list.append({
                    "股票代號": user_stock,
                    "股票名稱": realtime["name"],
                    "當前成交價": realtime["price"],
                    "漲跌": f"{diff:+.2f}",
                    "幅度": f"{diff_percent:+.2f}%",
                    "今日最高": realtime["high"],
                    "今日最低": realtime["low"],
                    "成交張數": realtime["volume"]
                })
        
        if display_list:
            st.table(pd.DataFrame(display_list))
        else:
            st.write("此群組尚無股票或資料讀取中...")

    st.caption(f"最後同步時間：{datetime.now().strftime('%H:%M:%S')} (每 10 秒自動刷新)")

update_stock_tables()
