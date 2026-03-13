import streamlit as st
import gspread
import time
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
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
st.set_page_config(page_title="台股 1-15 項極速監控", layout="wide")


def init_connection():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client


client = init_connection()
spreadsheet = client.open_by_key("10Oz6imH-bywS6sk23HquvgUw-3rKHLMU4g8MCC8ek-M")
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
        else:
            st.warning("請輸入群組名稱")

    st.divider()

    group_data = sheet2.get_all_records()
    df_groups = pd.DataFrame(group_data)

    if not df_groups.empty and "username" in df_groups.columns:
        user_groups = df_groups[df_groups["username"] == current_user]["class"].tolist()
    else:
        user_groups = []

    st.header("⚙️ 參數設定")
    with st.form("input_form"):
        stock_no = st.text_input("股票代號 (No)")
        category = st.selectbox(
            "分類 (Class)",
            user_groups if user_groups else ["請先建立群組"],
            disabled=not user_groups,
        )

        day_a = st.number_input("天數 A (day_a)", min_value=1, value=5)
        day_b = st.number_input("天數 B (day_b)", min_value=1, value=20)
        day_c = st.number_input("天數 C (day_c)", min_value=1, value=60)
        submitted = st.form_submit_button("💾 儲存", use_container_width=True)

if submitted:
    if not user_groups:
        st.sidebar.error("❌ 請先建立群組後再儲存！")
    elif stock_no:
        records = sheet1.get_all_records()
        df_existing = pd.DataFrame(records)
        now_time = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        existing_row_index = None
        if not df_existing.empty:
            match = df_existing[
                (df_existing["username"] == current_user)
                & (df_existing["no"].astype(str) == str(stock_no))
            ]
            if not match.empty:
                existing_row_index = match.index[0]
                old_day_a = match.iloc[0]["day_a"]
                old_day_b = match.iloc[0]["day_b"]
                old_day_c = match.iloc[0].get("day_c", 0)

        if existing_row_index is not None:
            if old_day_a == day_a and old_day_b == day_b and old_day_c == day_c:
                st.sidebar.info(f"ℹ️ {stock_no} 參數相同，無需更新。")
            else:
                row_to_update = int(existing_row_index) + 2
                sheet1.update_cell(row_to_update, 1, now_time)
                sheet1.update_cell(row_to_update, 4, day_a)
                sheet1.update_cell(row_to_update, 5, day_b)
                sheet1.update_cell(row_to_update, 6, day_c)
                sheet1.update_cell(row_to_update, 7, category)

                st.sidebar.success(f"🔄 {stock_no} 的參數已更新！")
                st.rerun()
        else:
            new_row = [now_time, current_user, stock_no, day_a, day_b, day_c, category]
            sheet1.append_row(new_row)
            st.sidebar.success(f"✅ {stock_no} 已新增儲存！")
            st.rerun()
    else:
        st.sidebar.error("請填寫股票代號 (No)")


@st.cache_data(ttl=3600)
def get_history_base(stock_no, max_count):
    now = datetime.now()
    current_date = now.replace(day=1)
    all_data = []

    while len(all_data) < max_count + 5:
        date_str = current_date.strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={date_str}&stockNo={stock_no}&response=html"
        try:
            resp = requests.get(url, timeout=10, verify=False)
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table")
            if table:
                rows = table.find_all("tr")[1:]
                month_data = []
                for row in rows:
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) >= 9:
                        month_data.append(
                            {
                                "收盤價": float(cols[6].replace(",", "")),
                                "成交股數": int(cols[1].replace(",", "")),
                            }
                        )
                all_data = month_data + all_data
            current_date = (current_date.replace(day=1) - timedelta(days=1)).replace(
                day=1
            )
            time.sleep(0.3)
        except:
            break
    return all_data


def get_realtime_info(stock_no):
    try:
        timestamp = int(time.time() * 1000)
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{stock_no}.tw&json=1&delay=0&_={timestamp}"
        headers = {
            "User-Agent": "Mozilla/5.0",
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
        }
    except:
        return None


# =========================
# 使用 Fragment 每 10 秒更新
# =========================


@st.fragment(run_every=10.0)
def update_stock_tables():

    group_data = sheet2.get_all_records()
    df_groups = pd.DataFrame(group_data)

    if not df_groups.empty and "username" in df_groups.columns:
        all_class = (
            df_groups[df_groups["username"] == current_user]["class"].unique().tolist()
        )
    else:
        all_class = []

    records = sheet1.get_all_records()
    df_records = pd.DataFrame(records)

    if not df_records.empty and "username" in df_records.columns:
        user_df = df_records[df_records["username"] == current_user]
    else:
        user_df = pd.DataFrame()

    for group in all_class:
        st.subheader(f"📁 {group}")

        if not user_df.empty:
            group_df = user_df[user_df["class"] == group]

            for _, row in group_df.iterrows():
                user_stock = str(row["no"]).split(".")[0].zfill(4)
                day_a = int(row["day_a"])
                day_b = int(row["day_b"])
                day_c = int(row["day_c"])

                max_target = max(day_a, day_b, day_c)
                history_data = get_history_base(user_stock, max_target)
                realtime = get_realtime_info(user_stock)

                if history_data and realtime:
                    prices = [item["收盤價"] for item in history_data]
                    volumes = [item["成交股數"] / 1000 for item in history_data]

                    ma_daya = sum(prices[-day_a:]) / day_a
                    ma_dayb = sum(prices[-day_b:]) / day_b
                    ma_dayc = sum(prices[-day_c:]) / day_c

                    last_4_vol = sum(volumes[-4:])
                    diff = realtime["price"] - realtime["yesterday_close"]
                    diff_percent = (diff / realtime["yesterday_close"]) * 100

                    vol_lots = realtime["volume"] / 1000
                    est_vol_lots = vol_lots
                    mv_custom = (est_vol_lots + last_4_vol) / 5

                    price_ma_diff = ((realtime["price"] - ma_daya) / ma_daya) * 100
                    vol_ratio = (est_vol_lots / mv_custom) * 100 if mv_custom > 0 else 0

                    data = [
                        [
                            user_stock,
                            realtime["name"],
                            realtime["price"],
                            f"{diff:.2f} ({diff_percent:.2f}%)",
                            f"{price_ma_diff:.2f}%",
                            ma_daya,
                            day_a,
                            ma_dayb,
                            day_b,
                            ma_dayc,
                            day_c,
                            vol_lots,
                            f"{vol_ratio:.2f}%",
                            mv_custom,
                            est_vol_lots,
                        ]
                    ]

                    columns = [
                        "1.代號",
                        "2.名稱",
                        "3.成交價",
                        "4.漲跌(%)",
                        "5.線價比",
                        "6.均線A",
                        "7.天數A",
                        "8.均線B",
                        "9.天數B",
                        "10.均線C",
                        "11.天數C",
                        "12.成交張數",
                        "13.量增比",
                        "14.日均量",
                        "15.預估量",
                    ]

                    df_display = pd.DataFrame(data, columns=columns)
                    st.table(df_display)
                else:
                    st.warning(f"正在抓取 {user_stock} 資料中...")

    st.caption(f"最後更新時間：{datetime.now().strftime('%H:%M:%S')}")


update_stock_tables()
