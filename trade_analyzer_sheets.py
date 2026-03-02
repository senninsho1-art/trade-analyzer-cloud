import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
import os
import uuid

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

st.set_page_config(
    page_title="TradeLog",
    page_icon="📈",
    layout="wide",
    initial_sidebar_ebar="collapsed"
)

# ==================== CSS ====================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {
    --bg:       #0d0f0e;
    --surface:  #161a18;
    --surface2: #1e2421;
    --border:   #2a312e;
    --green:    #00e676;
    --green-dim:#1a4a2e;
    --red:      #ef5350;
    --blue:     #42a5f5;
    --yellow:   #ffca28;
    --text:     #e8ede9;
    --text2:    #8a9e91;
    --mono:     'DM Mono', monospace;
    --sans:     'DM Sans', sans-serif;
}

*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"] {
    font-family: var(--sans) !important;
    background: var(--bg) !important;
    color: var(--text) !important;
}

/* スクロールバー */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

.main .block-container {
    padding: 56px 12px 24px !important;
    max-width: 100% !important;
    background: var(--bg) !important;
}

/* タブ固定 */
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] {
    position: fixed !important;
    top: 0 !important; left: 0 !important; right: 0 !important;
    z-index: 99999 !important;
    background: var(--surface) !important;
    border-bottom: 1px solid var(--border) !important;
    padding: 0 8px !important;
    gap: 0 !important;
}
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] button {
    font-family: var(--mono) !important;
    font-size: 10px !important;
    padding: 14px 10px !important;
    color: var(--text2) !important;
    border-bottom: 2px solid transparent !important;
    letter-spacing: 0.04em !important;
}
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] button[aria-selected="true"] {
    color: var(--green) !important;
    border-bottom: 2px solid var(--green) !important;
}
div[data-testid="stTabs"] > div[data-testid="stTabPanel"] {
    padding-top: 0 !important;
}

/* ボタン */
.stButton > button {
    font-family: var(--mono) !important;
    font-size: 12px !important;
    border-radius: 6px !important;
    height: 44px !important;
    border: 1px solid var(--border) !important;
    background: var(--surface2) !important;
    color: var(--text) !important;
    transition: all 0.12s ease !important;
    width: 100% !important;
}
.stButton > button:hover {
    border-color: var(--green) !important;
    color: var(--green) !important;
    background: rgba(0,230,118,0.06) !important;
}
.stButton > button[kind="primary"] {
    background: var(--green-dim) !important;
    border-color: var(--green) !important;
    color: var(--green) !important;
    font-weight: 600 !important;
}

/* タイルボタン系 */
div[data-tag-type="large"] .stButton > button {
    height: 52px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}

/* 入力 */
.stTextInput input, .stNumberInput input, .stSelectbox > div > div {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 6px !important;
    font-family: var(--mono) !important;
    font-size: 13px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: var(--green) !important;
    box-shadow: 0 0 0 2px rgba(0,230,118,0.12) !important;
}

/* メトリクス */
[data-testid="stMetric"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    padding: 12px !important;
}
[data-testid="stMetricValue"] {
    font-family: var(--mono) !important;
    font-size: 20px !important;
}

/* データフレーム */
.stDataFrame { font-size: 12px !important; }

/* ラジオ */
div[data-testid="stRadio"] label { font-size: 12px !important; }

/* チェックボックス */
.stCheckbox label { font-size: 13px !important; }

/* カスタムコンポーネント */
.trade-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 12px;
    position: relative;
}
.trade-card.win  { border-left: 3px solid var(--red); }
.trade-card.loss { border-left: 3px solid var(--blue); }
.trade-card.untagged { border-left: 3px solid var(--yellow); }

.tc-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }
.tc-ticker  { font-family: var(--mono); font-size: 15px; font-weight: 500; }
.tc-name    { font-size: 11px; color: var(--text2); margin-top: 2px; }
.tc-pl-pos  { font-family: var(--mono); font-size: 16px; font-weight: 600; color: var(--red); }
.tc-pl-neg  { font-family: var(--mono); font-size: 16px; font-weight: 600; color: var(--blue); }
.tc-meta    { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
.tc-meta span { font-size: 10px; color: var(--text2); font-family: var(--mono); }

.tile-grid  { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0; }
.tile-btn {
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface2);
    color: var(--text2);
    font-family: var(--mono);
    font-size: 11px;
    cursor: pointer;
    transition: all 0.1s;
    white-space: nowrap;
}
.tile-btn.active {
    border-color: var(--green);
    background: rgba(0,230,118,0.1);
    color: var(--green);
}
.tile-btn.active-sub {
    border-color: #42a5f5;
    background: rgba(66,165,245,0.1);
    color: #42a5f5;
}

.stat-grid  { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin: 8px 0; }
.stat-card  {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 12px;
    text-align: center;
}
.stat-val   { font-family: var(--mono); font-size: 18px; font-weight: 600; line-height: 1.2; }
.stat-lbl   { font-size: 9px; color: var(--text2); margin-top: 3px; letter-spacing: 0.06em; text-transform: uppercase; }
.val-pos    { color: var(--red); }
.val-neg    { color: var(--blue); }
.val-green  { color: var(--green); }
.val-yellow { color: var(--yellow); }

.section-title {
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--green);
    margin: 16px 0 10px;
    display: flex; align-items: center; gap: 8px;
}
.section-title::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
}

.badge {
    display: inline-flex; align-items: center;
    font-family: var(--mono); font-size: 9px; letter-spacing: 0.04em;
    padding: 2px 7px; border-radius: 4px; font-weight: 500;
}
.badge-win    { background: rgba(239,83,80,0.12);  color: var(--red);    border: 1px solid rgba(239,83,80,0.3); }
.badge-loss   { background: rgba(66,165,245,0.12); color: var(--blue);   border: 1px solid rgba(66,165,245,0.3); }
.badge-tagged { background: rgba(0,230,118,0.12);  color: var(--green);  border: 1px solid rgba(0,230,118,0.3); }
.badge-pending{ background: rgba(255,202,40,0.12); color: var(--yellow); border: 1px solid rgba(255,202,40,0.3); }

.pos-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 11px 14px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 6px;
}
.pos-ticker { font-family: var(--mono); font-size: 13px; font-weight: 500; }
.pos-sub    { font-size: 10px; color: var(--text2); margin-top: 2px; }
.pos-right  { text-align: right; }
.pos-qty    { font-family: var(--mono); font-size: 13px; }
.pos-avg    { font-size: 10px; color: var(--text2); font-family: var(--mono); }

.counter-badge {
    display: inline-block;
    background: var(--yellow);
    color: #000;
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 700;
    padding: 2px 9px;
    border-radius: 10px;
}
.star-btn { font-size: 22px; cursor: pointer; opacity: 0.35; transition: opacity 0.1s; }
.star-btn.active { opacity: 1; }

.import-drop {
    border: 2px dashed var(--border);
    border-radius: 10px;
    padding: 24px 16px;
    text-align: center;
    background: var(--surface);
    transition: border-color 0.15s;
}
.import-drop:hover { border-color: var(--green); }

.filter-row { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }

div[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    background: var(--surface) !important;
}
</style>
""", unsafe_allow_html=True)

# ==================== Google Sheets ====================
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
TRADELOG_SHEET = 'Trade_Log'
POSITIONS_SHEET = 'Positions'
SETTINGS_SHEET = 'Settings'

TRADELOG_COLS = [
    'id', 'market',
    'ticker', 'name',
    'trade_date', 'build_date',      # 約定日, 建約定日
    'quantity', 'sell_price', 'avg_cost',
    'realized_pl', 'realized_pl_pct',
    'hold_days',
    'tag_large', 'tag_detail',
    'satisfaction',                  # 1-5
    'stop_loss_price', 'discipline', # 規律
    'memo',
    'created_at'
]

@st.cache_resource
def get_sheets_client():
    try:
        gcp = os.environ.get("GCP_SERVICE_ACCOUNT_JSON", "")
        if gcp:
            info = json.loads(gcp)
            cred = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            return build('sheets', 'v4', credentials=cred).spreadsheets()
        if hasattr(st, 'secrets') and "gcp_service_account" in st.secrets:
            cred = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"], scopes=SCOPES)
            return build('sheets', 'v4', credentials=cred).spreadsheets()
        return None
    except Exception as e:
        st.error(f"Sheets接続エラー: {e}")
        return None

def get_sid():
    sid = os.environ.get("SPREADSHEET_ID", "")
    if sid: return sid
    try: return st.secrets.get("spreadsheet_id", "")
    except: return ""

def read_sheet(client, sid, sheet, has_header=True):
    try:
        r = client.values().get(spreadsheetId=sid, range=f"{sheet}!A:ZZ").execute()
        vals = r.get('values', [])
        if not vals: return pd.DataFrame()
        if has_header:
            h = vals[0]; rows = [v + [''] * (len(h) - len(v)) for v in vals[1:]]
            return pd.DataFrame(rows, columns=h)
        return pd.DataFrame(vals)
    except HttpError as e:
        if e.resp.status == 404: return pd.DataFrame()
        return pd.DataFrame()
    except: return pd.DataFrame()

def write_sheet(client, sid, sheet, df):
    try:
        vals = [df.columns.tolist()] + df.fillna('').astype(str).values.tolist()
        client.values().clear(spreadsheetId=sid, range=f"{sheet}!A:ZZ").execute()
        client.values().update(
            spreadsheetId=sid, range=f"{sheet}!A1",
            valueInputOption='RAW', body={'values': vals}
        ).execute()
        return True
    except Exception as e:
        st.error(f"書き込みエラー: {e}"); return False

def ensure_sheet(client, sid, name):
    try:
        r = client.get(spreadsheetId=sid).execute()
        existing = [s['properties']['title'] for s in r.get('sheets', [])]
        if name not in existing:
            client.batchUpdate(spreadsheetId=sid, body={
                'requests': [{'addSheet': {'properties': {'title': name}}}]
            }).execute()
    except: pass

def init_sheets(client, sid):
    for s in [TRADELOG_SHEET, POSITIONS_SHEET, SETTINGS_SHEET]:
        ensure_sheet(client, sid, s)
    df = read_sheet(client, sid, TRADELOG_SHEET)
    if len(df) == 0:
        write_sheet(client, sid, TRADELOG_SHEET, pd.DataFrame(columns=TRADELOG_COLS))

# ==================== CSV パーサー ====================
def _clean_num(s):
    return pd.to_numeric(
        s.astype(str).str.replace(',', '').str.replace('−', '-').str.strip(),
        errors='coerce'
    ).fillna(0)

def parse_realized_jp(df):
    df = df.copy()
    df.columns = df.columns.str.strip()
    result = pd.DataFrame({
        'market': '日本株',
        'ticker': df['銘柄コード'].astype(str).str.strip().apply(
            lambda x: str(int(float(x))) if x.replace('.','').isdigit() else x),
        'name': df['銘柄名'],
        'trade_date': pd.to_datetime(df['約定日'], format='%Y/%m/%d', errors='coerce').dt.strftime('%Y-%m-%d'),
        'build_date': '',
        'quantity': _clean_num(df['数量[株]']).astype(int),
        'sell_price': _clean_num(df['売却/決済単価[円]']),
        'avg_cost': _clean_num(df['平均取得価額[円]']),
        'realized_pl': _clean_num(df['実現損益[円]']),
    })
    # 建約定日があれば
    if '建約定日' in df.columns:
        result['build_date'] = pd.to_datetime(df['建約定日'], format='%Y/%m/%d', errors='coerce').dt.strftime('%Y-%m-%d')
    result['realized_pl_pct'] = np.where(
        result['avg_cost'] > 0,
        (result['realized_pl'] / (result['avg_cost'] * result['quantity']) * 100).round(2),
        0.0
    )
    result['hold_days'] = ''
    return result

def parse_realized_us(df):
    df = df.copy()
    df.columns = df.columns.str.strip()
    result = pd.DataFrame({
        'market': '米国株',
        'ticker': df['ティッカーコード'].astype(str).str.strip(),
        'name': df['銘柄名'],
        'trade_date': pd.to_datetime(df['約定日'], format='%Y/%m/%d', errors='coerce').dt.strftime('%Y-%m-%d'),
        'build_date': '',
        'quantity': _clean_num(df['数量[株]']).astype(int),
        'sell_price': _clean_num(df['売却/決済単価[USドル]']),
        'avg_cost': _clean_num(df['平均取得価額[円]']),
        'realized_pl': _clean_num(df['実現損益[円]']),
    })
    result['realized_pl_pct'] = np.where(
        result['avg_cost'] > 0,
        (result['realized_pl'] / result['avg_cost'] / result['quantity'] * 100).round(2),
        0.0
    )
    result['hold_days'] = ''
    return result

def parse_history_jp(df):
    df = df.copy()
    df.columns = df.columns.str.strip()
    return pd.DataFrame({
        'market': '日本株',
        'trade_date': pd.to_datetime(df['約定日'], format='%Y/%m/%d', errors='coerce').dt.strftime('%Y-%m-%d'),
        'ticker': df['銘柄コード'].astype(str).str.strip().apply(
            lambda x: str(int(float(x))) if x.replace('.','').isdigit() else x),
        'name': df['銘柄名'],
        'trade_type': df['取引区分'],
        'action': df['売買区分'],
        'quantity': _clean_num(df['数量［株］']).astype(int),
        'price': _clean_num(df['単価［円］']),
        'build_date': pd.to_datetime(df['建約定日'], format='%Y/%m/%d', errors='coerce').dt.strftime('%Y-%m-%d') if '建約定日' in df.columns else '',
    })

def parse_history_us(df):
    df = df.copy()
    df.columns = df.columns.str.strip()
    return pd.DataFrame({
        'market': '米国株',
        'trade_date': pd.to_datetime(df['約定日'], format='%Y/%m/%d', errors='coerce').dt.strftime('%Y-%m-%d'),
        'ticker': df['ティッカー'].astype(str).str.strip(),
        'name': df['銘柄名'],
        'trade_type': df['取引区分'],
        'action': df['売買区分'],
        'quantity': _clean_num(df['数量［株］']).astype(int),
        'price': _clean_num(df['単価［USドル］']),
        'build_date': '',
    })

# ==================== ポジション計算 ====================
def calc_positions(df_hist):
    """取引履歴から現在ポジションを算出"""
    if len(df_hist) == 0:
        return pd.DataFrame()
    result = []
    for ticker in df_hist['ticker'].unique():
        sub = df_hist[df_hist['ticker'] == ticker].sort_values('trade_date')
        name = sub['name'].iloc[-1]
        market = sub['market'].iloc[-1]

        # 現物
        spot = sub[sub['trade_type'].isin(['現物', '現引']) | (sub['market'] == '米国株')]
        spot_buy  = spot[spot['action'].isin(['買付', '入庫'])]['quantity'].sum()
        spot_sell = spot[spot['action'] == '売付']['quantity'].sum()
        spot_qty  = spot_buy - spot_sell

        # 信用
        margin_buy  = sub[sub['action'] == '買建']['quantity'].sum()
        margin_sell = sub[sub['action'] == '売埋']['quantity'].sum()
        kenin       = sub[sub['trade_type'] == '現引']['quantity'].sum()
        margin_qty  = margin_buy - margin_sell - kenin

        # 平均取得価格（FIFO近似）
        def avg_price(rows, buy_acts, sell_act):
            qty, avg = 0.0, 0.0
            for _, r in rows.sort_values('trade_date').iterrows():
                q = float(r['quantity']); p = float(r['price'])
                if r['action'] in buy_acts:
                    avg = (avg * qty + p * q) / (qty + q) if (qty + q) > 0 else 0
                    qty += q
                elif r['action'] == sell_act:
                    qty = max(0, qty - q)
                    if qty == 0: avg = 0
            return round(avg, 2)

        if spot_qty > 0:
            buy_acts = ['買付', '入庫'] if market == '日本株' else ['買付']
            avg = avg_price(spot, buy_acts, '売付')
            result.append({'ticker': ticker, 'name': name, 'market': market,
                           'type': 'spot', 'quantity': int(spot_qty), 'avg_price': avg})
        if margin_qty > 0:
            avg = avg_price(sub[sub['action'].isin(['買建', '売埋'])], ['買建'], '売埋')
            result.append({'ticker': ticker, 'name': name, 'market': market,
                           'type': 'margin', 'quantity': int(margin_qty), 'avg_price': avg})
    return pd.DataFrame(result) if result else pd.DataFrame()

# ==================== タグ定義 ====================
TAG_TREE = {
    '順張り':     ['新高値ブレイク', 'MAパーフェクトオーダー', '上昇トレンド押し目', '急騰飛び乗り'],
    '逆張り':     ['押し目(節目/MA)', '二番底', '乖離率/オーバーシュート', '窓埋め完了'],
    'イベント':   ['決算後初動', '好決算の売られすぎ', '決算前先回り', '政治・ニュース'],
    'ポジション整理': ['ピラミッティング', 'ナンピン', '現引移行', 'リスクヘッジ'],
}
LARGE_TAGS = list(TAG_TREE.keys())

TAG_COLORS = {
    '順張り': '#00e676', '逆張り': '#42a5f5',
    'イベント': '#ffca28', 'ポジション整理': '#ce93d8',
}

# ==================== 既存ログ読み込み（キャッシュ） ====================
@st.cache_data(ttl=300)
def load_tradelog_cached(sid):
    client = get_sheets_client()
    if not client: return pd.DataFrame(columns=TRADELOG_COLS)
    df = read_sheet(client, sid, TRADELOG_SHEET)
    if len(df) == 0: return pd.DataFrame(columns=TRADELOG_COLS)
    return df

def reload_tradelog():
    load_tradelog_cached.clear()

# ==================== セッションステート初期化 ====================
def init_state():
    defaults = {
        'realized_df': None,        # アップロード済み実現損益（結合）
        'history_df': None,         # アップロード済み取引履歴（結合）
        'pending': [],              # 未保存のタグ付け中レコード
        'tag_state': {},            # {idx: {large, detail, satisfaction, stop_loss, discipline, memo}}
        'positions': None,
        'tab_idx': 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ==================== Google Sheets接続チェック ====================
sheets_client = get_sheets_client()
sid = get_sid()

if sheets_client and sid:
    init_sheets(sheets_client, sid)

# ==================== メインUI ====================
tab_import, tab_tag, tab_dash, tab_pos, tab_settings = st.tabs([
    "📥 取込", "🏷 タグ付け", "📊 分析", "📦 保有", "⚙️ 設定"
])

# ====================================================
# TAB 1: 取込
# ====================================================
with tab_import:
    st.markdown('<div class="section-title">実現損益CSV（分析の主軸）</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.caption("🇯🇵 日本株 実現損益CSV")
        jp_real = st.file_uploader("日本株 実現損益", type='csv', key='jp_real', label_visibility='collapsed')
    with col2:
        st.caption("🇺🇸 米国株 実現損益CSV")
        us_real = st.file_uploader("米国株 実現損益", type='csv', key='us_real', label_visibility='collapsed')

    st.markdown('<div class="section-title">取引履歴CSV（ポジション計算用）</div>', unsafe_allow_html=True)
    col3, col4 = st.columns(2)
    with col3:
        st.caption("🇯🇵 日本株 取引履歴CSV")
        jp_hist = st.file_uploader("日本株 取引履歴", type='csv', key='jp_hist', label_visibility='collapsed')
    with col4:
        st.caption("🇺🇸 米国株 取引履歴CSV")
        us_hist = st.file_uploader("米国株 取引履歴", type='csv', key='us_hist', label_visibility='collapsed')

    # 読み込み処理
    realized_parts, history_parts = [], []

    if jp_real:
        try:
            df = pd.read_csv(jp_real, encoding='cp932')
            realized_parts.append(parse_realized_jp(df))
            st.success(f"日本株 実現損益: {len(df)}件 ✅")
        except Exception as e:
            st.error(f"日本株 実現損益 読み込みエラー: {e}")

    if us_real:
        try:
            df = pd.read_csv(us_real, encoding='cp932')
            realized_parts.append(parse_realized_us(df))
            st.success(f"米国株 実現損益: {len(df)}件 ✅")
        except Exception as e:
            st.error(f"米国株 実現損益 読み込みエラー: {e}")

    if jp_hist:
        try:
            df = pd.read_csv(jp_hist, encoding='cp932')
            history_parts.append(parse_history_jp(df))
            st.success(f"日本株 取引履歴: {len(df)}件 ✅")
        except Exception as e:
            st.error(f"日本株 取引履歴 読み込みエラー: {e}")

    if us_hist:
        try:
            df = pd.read_csv(us_hist, encoding='cp932')
            history_parts.append(parse_history_us(df))
            st.success(f"米国株 取引履歴: {len(df)}件 ✅")
        except Exception as e:
            st.error(f"米国株 取引履歴 読み込みエラー: {e}")

    # 確定ボタン
    if realized_parts or history_parts:
        st.divider()
        col_btn, col_info = st.columns([2, 3])
        with col_btn:
            do_import = st.button("⚡ メモリに読み込む", type="primary", use_container_width=True)
        with col_info:
            if sheets_client and sid:
                st.caption("✅ Sheets接続OK。「タグ付け」タブで分類後、一括保存できます")
            else:
                st.caption("⚠️ Sheets未接続。タグ付けのみ可（保存不可）")

        if do_import:
            if realized_parts:
                combined_r = pd.concat(realized_parts, ignore_index=True)
                combined_r = combined_r.sort_values('trade_date', ascending=False).reset_index(drop=True)

                # 既存ログと照合して未登録分を抽出
                if sheets_client and sid:
                    existing = load_tradelog_cached(sid)
                    if len(existing) > 0 and 'ticker' in existing.columns and 'trade_date' in existing.columns:
                        existing_keys = set(
                            existing['ticker'].astype(str) + '_' + existing['trade_date'].astype(str)
                        )
                        combined_r['_key'] = combined_r['ticker'].astype(str) + '_' + combined_r['trade_date'].astype(str)
                        new_only = combined_r[~combined_r['_key'].isin(existing_keys)].drop('_key', axis=1)
                        dup_cnt  = len(combined_r) - len(new_only)
                        if dup_cnt > 0:
                            st.info(f"既登録 {dup_cnt}件をスキップ → 新規 {len(new_only)}件を追加対象")
                        combined_r = new_only

                st.session_state['realized_df'] = combined_r

                # pending セットアップ
                pending = []
                for i, row in combined_r.iterrows():
                    pending.append({
                        'idx': i,
                        'market': row['market'],
                        'ticker': row['ticker'],
                        'name': row['name'],
                        'trade_date': row['trade_date'],
                        'build_date': row.get('build_date', ''),
                        'quantity': row['quantity'],
                        'sell_price': row['sell_price'],
                        'avg_cost': row['avg_cost'],
                        'realized_pl': row['realized_pl'],
                        'realized_pl_pct': row['realized_pl_pct'],
                    })
                st.session_state['pending'] = pending
                st.session_state['tag_state'] = {}

            if history_parts:
                combined_h = pd.concat(history_parts, ignore_index=True)
                st.session_state['history_df'] = combined_h
                pos = calc_positions(combined_h)
                st.session_state['positions'] = pos

            st.success("✅ 読み込み完了！「🏷 タグ付け」タブへ進んでください")
            st.rerun()

    # 現在のメモリ状態サマリー
    st.divider()
    st.markdown('<div class="section-title">現在のメモリ状態</div>', unsafe_allow_html=True)
    r = st.session_state.get('realized_df')
    h = st.session_state.get('history_df')
    p = st.session_state.get('pending', [])

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
<div class="stat-card">
  <div class="stat-val val-green">{len(r) if r is not None else 0}</div>
  <div class="stat-lbl">実現損益レコード</div>
</div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
<div class="stat-card">
  <div class="stat-val val-yellow">{len(p)}</div>
  <div class="stat-lbl">タグ付け待ち</div>
</div>""", unsafe_allow_html=True)
    with c3:
        h_cnt = len(h) if h is not None else 0
        st.markdown(f"""
<div class="stat-card">
  <div class="stat-val">{h_cnt}</div>
  <div class="stat-lbl">取引履歴レコード</div>
</div>""", unsafe_allow_html=True)

# ====================================================
# TAB 2: タグ付け
# ====================================================
with tab_tag:
    pending = st.session_state.get('pending', [])
    tag_state = st.session_state.get('tag_state', {})

    # 完了・未完了カウント
    tagged_idxs = {i for i, ts in tag_state.items() if ts.get('large')}
    untagged = [p for p in pending if p['idx'] not in tagged_idxs]
    tagged   = [p for p in pending if p['idx'] in tagged_idxs]

    # ヘッダー
    total_cnt = len(pending)
    if total_cnt > 0:
        remain = len(untagged)
        pct    = int((len(tagged) / total_cnt) * 100) if total_cnt > 0 else 0
        col_h1, col_h2 = st.columns([3, 2])
        with col_h1:
            st.markdown(f"""
<div style="padding:10px 0;">
  <span style="font-size:13px;color:var(--text2);">未タグ付け</span>
  <span class="counter-badge" style="margin:0 8px;">{remain}件</span>
  <span style="font-size:12px;color:var(--text2);">{pct}% 完了</span>
</div>""", unsafe_allow_html=True)
        with col_h2:
            # 一括保存ボタン
            can_save = sheets_client and sid and len(tagged) > 0
            if st.button(
                f"💾 {len(tagged)}件を保存",
                disabled=not can_save,
                type="primary" if can_save else "secondary",
                use_container_width=True
            ):
                # tag_state → DataFrame → Sheetsへ書き込み
                save_rows = []
                r_df = st.session_state.get('realized_df')
                for p_item in tagged:
                    idx = p_item['idx']
                    ts  = tag_state[idx]
                    bd  = str(p_item.get('build_date', ''))
                    td  = str(p_item['trade_date'])
                    hold_d = ''
                    if bd and bd not in ('', 'NaT', 'nan'):
                        try:
                            d1 = datetime.strptime(bd[:10], '%Y-%m-%d')
                            d2 = datetime.strptime(td[:10], '%Y-%m-%d')
                            hold_d = str((d2 - d1).days)
                        except: pass
                    save_rows.append({
                        'id': str(uuid.uuid4())[:8],
                        'market': p_item['market'],
                        'ticker': p_item['ticker'],
                        'name': p_item['name'],
                        'trade_date': td,
                        'build_date': bd,
                        'quantity': p_item['quantity'],
                        'sell_price': p_item['sell_price'],
                        'avg_cost': p_item['avg_cost'],
                        'realized_pl': p_item['realized_pl'],
                        'realized_pl_pct': p_item['realized_pl_pct'],
                        'hold_days': hold_d,
                        'tag_large': ts.get('large', ''),
                        'tag_detail': ts.get('detail', ''),
                        'satisfaction': ts.get('satisfaction', ''),
                        'stop_loss_price': ts.get('stop_loss', ''),
                        'discipline': '1' if ts.get('discipline', False) else '0',
                        'memo': ts.get('memo', ''),
                        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    })

                if save_rows:
                    existing = load_tradelog_cached(sid)
                    new_df = pd.DataFrame(save_rows)
                    if len(existing) > 0:
                        combined_save = pd.concat([existing, new_df], ignore_index=True)
                    else:
                        combined_save = new_df
                    ok = write_sheet(sheets_client, sid, TRADELOG_SHEET, combined_save)
                    if ok:
                        reload_tradelog()
                        # 保存済みをpendingから削除
                        saved_idxs = {p_item['idx'] for p_item in tagged}
                        st.session_state['pending'] = [x for x in st.session_state['pending']
                                                       if x['idx'] not in saved_idxs]
                        for idx in saved_idxs:
                            st.session_state['tag_state'].pop(idx, None)
                        st.success(f"✅ {len(save_rows)}件を保存しました！")
                        st.rerun()

        # プログレスバー
        st.progress(pct / 100)
    else:
        st.info("📥 まず「取込」タブでCSVを読み込んでください")

    # --- 未タグ付けカード ---
    if untagged:
        st.markdown('<div class="section-title">未タグ付け</div>', unsafe_allow_html=True)

        for p_item in untagged[:20]:  # 一度に20件まで表示
            idx = p_item['idx']
            ts  = tag_state.get(idx, {})
            pl  = float(p_item['realized_pl'])
            pl_cls = "win" if pl >= 0 else "loss"
            pl_html_cls = "tc-pl-pos" if pl >= 0 else "tc-pl-neg"
            pl_sign = "+" if pl >= 0 else ""
            pl_pct  = float(p_item.get('realized_pl_pct', 0))
            flag    = "🇯🇵" if p_item['market'] == '日本株' else "🇺🇸"

            st.markdown(f"""
<div class="trade-card {pl_cls}">
  <div class="tc-header">
    <div>
      <div class="tc-ticker">{flag} {p_item['ticker']}</div>
      <div class="tc-name">{p_item['name']}</div>
    </div>
    <div style="text-align:right">
      <div class="{pl_html_cls}">{pl_sign}¥{pl:,.0f}</div>
      <div style="font-size:10px;color:var(--text2);font-family:var(--mono);">{pl_pct:+.1f}%</div>
    </div>
  </div>
  <div class="tc-meta">
    <span>📅 {p_item['trade_date']}</span>
    <span>📊 {int(p_item['quantity'])}株</span>
    <span>売 ¥{float(p_item['sell_price']):,.1f}</span>
    <span>取得 ¥{float(p_item['avg_cost']):,.1f}</span>
  </div>
</div>""", unsafe_allow_html=True)

            # 大分類タイル
            st.markdown("**📌 大分類**")
            cols = st.columns(len(LARGE_TAGS))
            for ci, tag in enumerate(LARGE_TAGS):
                with cols[ci]:
                    is_active = ts.get('large') == tag
                    btn_label = f"{'✓ ' if is_active else ''}{tag}"
                    if st.button(btn_label, key=f"lg_{idx}_{tag}", use_container_width=True):
                        if idx not in st.session_state['tag_state']:
                            st.session_state['tag_state'][idx] = {}
                        if st.session_state['tag_state'][idx].get('large') == tag:
                            st.session_state['tag_state'][idx].pop('large', None)
                            st.session_state['tag_state'][idx].pop('detail', None)
                        else:
                            st.session_state['tag_state'][idx]['large'] = tag
                            st.session_state['tag_state'][idx].pop('detail', None)
                        st.rerun()

            # 詳細タイル（大分類選択後）
            if ts.get('large') and ts['large'] in TAG_TREE:
                details = TAG_TREE[ts['large']]
                st.markdown(f"**🔍 詳細理由（{ts['large']}）**")
                d_cols = st.columns(min(len(details), 4))
                for di, dtag in enumerate(details):
                    with d_cols[di % 4]:
                        is_active = ts.get('detail') == dtag
                        btn_label = f"{'✓ ' if is_active else ''}{dtag}"
                        if st.button(btn_label, key=f"dt_{idx}_{dtag}", use_container_width=True):
                            if st.session_state['tag_state'][idx].get('detail') == dtag:
                                st.session_state['tag_state'][idx].pop('detail', None)
                            else:
                                st.session_state['tag_state'][idx]['detail'] = dtag
                            st.rerun()

            # 納得度・損切り・規律
            col_sat, col_sl = st.columns(2)
            with col_sat:
                st.markdown("**⭐ 納得度**")
                s_cols = st.columns(5)
                for si in range(1, 6):
                    with s_cols[si - 1]:
                        is_active = ts.get('satisfaction') == si
                        if st.button(f"{'★' if is_active else '☆'}{si}", key=f"sat_{idx}_{si}", use_container_width=True):
                            if idx not in st.session_state['tag_state']:
                                st.session_state['tag_state'][idx] = {}
                            if st.session_state['tag_state'][idx].get('satisfaction') == si:
                                st.session_state['tag_state'][idx].pop('satisfaction', None)
                            else:
                                st.session_state['tag_state'][idx]['satisfaction'] = si
                            st.rerun()
            with col_sl:
                st.markdown("**🛑 当初損切り価格**")
                cur_sl = ts.get('stop_loss', 0.0)
                new_sl = st.number_input(
                    "損切り", min_value=0.0, value=float(cur_sl), step=1.0, format="%.1f",
                    key=f"sl_{idx}", label_visibility='collapsed'
                )
                if new_sl != cur_sl:
                    if idx not in st.session_state['tag_state']:
                        st.session_state['tag_state'][idx] = {}
                    st.session_state['tag_state'][idx]['stop_loss'] = new_sl

            disc = ts.get('discipline', False)
            new_disc = st.checkbox("✅ 損切りルールを守った", value=disc, key=f"disc_{idx}")
            if new_disc != disc:
                if idx not in st.session_state['tag_state']:
                    st.session_state['tag_state'][idx] = {}
                st.session_state['tag_state'][idx]['discipline'] = new_disc

            cur_memo = ts.get('memo', '')
            new_memo = st.text_input("💬 メモ（任意）", value=cur_memo, key=f"memo_{idx}")
            if new_memo != cur_memo:
                if idx not in st.session_state['tag_state']:
                    st.session_state['tag_state'][idx] = {}
                st.session_state['tag_state'][idx]['memo'] = new_memo

            st.divider()

        if len(untagged) > 20:
            st.caption(f"残り {len(untagged) - 20}件は上の件を保存後に表示されます")

    # --- 入力済みカード ---
    if tagged:
        st.markdown('<div class="section-title">入力済み（未保存）</div>', unsafe_allow_html=True)
        for p_item in tagged:
            idx = p_item['idx']
            ts  = tag_state[idx]
            pl  = float(p_item['realized_pl'])
            pl_cls = "win" if pl >= 0 else "loss"
            pl_html = "tc-pl-pos" if pl >= 0 else "tc-pl-neg"
            flag = "🇯🇵" if p_item['market'] == '日本株' else "🇺🇸"
            color = TAG_COLORS.get(ts.get('large', ''), '#888')
            st.markdown(f"""
<div class="trade-card {pl_cls}" style="opacity:0.75;">
  <div class="tc-header">
    <div>
      <div class="tc-ticker">{flag} {p_item['ticker']}</div>
      <div style="font-size:11px;margin-top:2px;">
        <span class="badge badge-tagged">✓ {ts.get('large','')} / {ts.get('detail','—')}</span>
        {'<span class="badge badge-tagged" style="margin-left:4px;">⭐' + str(ts.get('satisfaction','')) + '</span>' if ts.get('satisfaction') else ''}
      </div>
    </div>
    <div class="{pl_html}" style="font-family:var(--mono);font-size:14px;">
      {"+" if pl >= 0 else ""}¥{pl:,.0f}
    </div>
  </div>
</div>""", unsafe_allow_html=True)

# ====================================================
# TAB 3: 分析ダッシュボード
# ====================================================
with tab_dash:
    # データ読み込み
    if sheets_client and sid:
        df_log = load_tradelog_cached(sid)
    else:
        df_log = pd.DataFrame(columns=TRADELOG_COLS)

    if len(df_log) == 0:
        st.info("分析データがありません。CSVを取込みタグ付け後に保存してください。")
    else:
        # 型変換
        df_log['realized_pl']     = pd.to_numeric(df_log['realized_pl'], errors='coerce').fillna(0)
        df_log['realized_pl_pct'] = pd.to_numeric(df_log['realized_pl_pct'], errors='coerce').fillna(0)
        df_log['quantity']        = pd.to_numeric(df_log['quantity'], errors='coerce').fillna(0)
        df_log['hold_days']       = pd.to_numeric(df_log['hold_days'], errors='coerce')
        df_log['satisfaction']    = pd.to_numeric(df_log['satisfaction'], errors='coerce')
        df_log['trade_date']      = pd.to_datetime(df_log['trade_date'], errors='coerce')
        df_log = df_log.dropna(subset=['trade_date'])

        # 期間フィルター
        period_opt = st.radio("期間", ["全期間", "過去1年", "過去1ヶ月"], horizontal=True)
        today = pd.Timestamp.today()
        if period_opt == "過去1年":
            df_f = df_log[df_log['trade_date'] >= today - timedelta(days=365)]
        elif period_opt == "過去1ヶ月":
            df_f = df_log[df_log['trade_date'] >= today - timedelta(days=30)]
        else:
            df_f = df_log

        df_f = df_f.copy()

        # ==================== KPI ====================
        total_pl    = df_f['realized_pl'].sum()
        total_trades= len(df_f)
        wins        = (df_f['realized_pl'] > 0).sum()
        losses      = (df_f['realized_pl'] < 0).sum()
        win_rate    = wins / total_trades * 100 if total_trades > 0 else 0
        avg_win     = df_f[df_f['realized_pl'] > 0]['realized_pl'].mean() if wins > 0 else 0
        avg_loss    = abs(df_f[df_f['realized_pl'] < 0]['realized_pl'].mean()) if losses > 0 else 1
        pf          = avg_win / avg_loss if avg_loss > 0 else 0

        pl_cls = "val-pos" if total_pl >= 0 else "val-neg"
        sign   = "+" if total_pl >= 0 else ""
        st.markdown(f"""
<div class="stat-grid">
  <div class="stat-card" style="border-color:{'var(--red)' if total_pl >= 0 else 'var(--blue)'}">
    <div class="stat-val {pl_cls}">{sign}¥{total_pl:,.0f}</div>
    <div class="stat-lbl">累積実現損益</div>
  </div>
  <div class="stat-card">
    <div class="stat-val val-green">{win_rate:.1f}%</div>
    <div class="stat-lbl">勝率 ({wins}勝{losses}敗)</div>
  </div>
  <div class="stat-card">
    <div class="stat-val">{pf:.2f}</div>
    <div class="stat-lbl">ペイオフレシオ</div>
  </div>
</div>
""", unsafe_allow_html=True)

        # ==================== 累積損益グラフ ====================
        st.markdown('<div class="section-title">損益推移</div>', unsafe_allow_html=True)
        df_daily = df_f.groupby(df_f['trade_date'].dt.date)['realized_pl'].sum().reset_index()
        df_daily.columns = ['date', 'daily_pl']
        df_daily = df_daily.sort_values('date')
        df_daily['cumulative'] = df_daily['daily_pl'].cumsum()
        df_daily['color'] = df_daily['daily_pl'].apply(lambda x: '#ef5350' if x >= 0 else '#42a5f5')

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_daily['date'], y=df_daily['daily_pl'],
            marker_color=df_daily['color'],
            name='日次損益', opacity=0.7
        ))
        fig.add_trace(go.Scatter(
            x=df_daily['date'], y=df_daily['cumulative'],
            mode='lines', name='累積',
            line=dict(color='#00e676', width=2),
            yaxis='y2'
        ))
        fig.update_layout(
            height=280,
            paper_bgcolor='#161a18', plot_bgcolor='#161a18',
            font=dict(color='#8a9e91', size=10, family='DM Mono'),
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation='h', yanchor='bottom', y=1, font_size=10),
            yaxis=dict(gridcolor='#2a312e', zeroline=False),
            yaxis2=dict(overlaying='y', side='right', gridcolor='transparent', zeroline=False),
            xaxis=dict(gridcolor='#2a312e'),
            hovermode='x unified',
        )
        st.plotly_chart(fig, use_container_width=True)

        # ==================== 銘柄別スタッツ ====================
        st.markdown('<div class="section-title">銘柄別スタッツ</div>', unsafe_allow_html=True)
        ticker_stats = df_f.groupby('ticker').agg(
            名前=('name', 'last'),
            取引数=('realized_pl', 'count'),
            勝率=('realized_pl', lambda x: round((x > 0).mean() * 100, 1)),
            総損益=('realized_pl', 'sum'),
            平均損益=('realized_pl', 'mean'),
            平均利益=('realized_pl', lambda x: round(x[x > 0].mean(), 0) if (x > 0).any() else 0),
            平均損失=('realized_pl', lambda x: round(abs(x[x < 0].mean()), 0) if (x < 0).any() else 0),
            平均保有日=('hold_days', 'mean'),
        ).round(1).sort_values('総損益', ascending=False).reset_index()
        ticker_stats['総損益'] = ticker_stats['総損益'].astype(int)
        ticker_stats['平均損益'] = ticker_stats['平均損益'].round(0).astype(int)
        st.dataframe(ticker_stats, use_container_width=True, height=280)

        # ==================== 曜日別分析 ====================
        st.markdown('<div class="section-title">曜日別 勝率</div>', unsafe_allow_html=True)
        df_f['weekday'] = df_f['trade_date'].dt.day_name()
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        day_jp    = {'Monday': '月', 'Tuesday': '火', 'Wednesday': '水', 'Thursday': '木', 'Friday': '金'}
        wday = df_f.groupby('weekday').agg(
            勝率=('realized_pl', lambda x: round((x > 0).mean() * 100, 1)),
            総損益=('realized_pl', 'sum'),
            件数=('realized_pl', 'count'),
        ).reindex([d for d in day_order if d in df_f['weekday'].unique()]).reset_index()
        wday['曜日'] = wday['weekday'].map(day_jp)
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=wday['曜日'], y=wday['勝率'],
            marker_color='#00e676', opacity=0.8, name='勝率%',
            text=wday['勝率'].apply(lambda x: f"{x:.0f}%"),
            textposition='outside', textfont=dict(size=11, color='#8a9e91'),
        ))
        fig2.update_layout(
            height=220, paper_bgcolor='#161a18', plot_bgcolor='#161a18',
            font=dict(color='#8a9e91', size=10, family='DM Mono'),
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis=dict(gridcolor='#2a312e', range=[0, 110]),
            xaxis=dict(gridcolor='transparent'),
        )
        st.plotly_chart(fig2, use_container_width=True)

        # ==================== タグ別分析 ====================
        tagged_df = df_f[df_f['tag_large'].astype(str).str.strip() != '']
        if len(tagged_df) > 0:
            st.markdown('<div class="section-title">タグ別パフォーマンス</div>', unsafe_allow_html=True)
            tag_stats = tagged_df.groupby('tag_large').agg(
                件数=('realized_pl', 'count'),
                勝率=('realized_pl', lambda x: round((x > 0).mean() * 100, 1)),
                総損益=('realized_pl', 'sum'),
                平均損益=('realized_pl', 'mean'),
                平均納得度=('satisfaction', 'mean'),
            ).round(1).sort_values('総損益', ascending=False).reset_index()
            tag_stats['総損益'] = tag_stats['総損益'].astype(int)

            col_t1, col_t2 = st.columns(2)
            with col_t1:
                fig3 = px.bar(tag_stats, x='tag_large', y='総損益',
                              color='勝率', color_continuous_scale=[[0,'#42a5f5'],[0.5,'#ffca28'],[1,'#ef5350']],
                              title='タグ別 総損益',
                              labels={'tag_large':'タグ','総損益':'損益（円）'})
                fig3.update_layout(height=240, paper_bgcolor='#161a18', plot_bgcolor='#161a18',
                                   font_color='#8a9e91', title_font_size=11,
                                   margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig3, use_container_width=True)
            with col_t2:
                fig4 = px.bar(tag_stats, x='tag_large', y='勝率',
                              title='タグ別 勝率%',
                              labels={'tag_large':'タグ','勝率':'勝率(%)'},
                              color_discrete_sequence=['#00e676'])
                fig4.update_layout(height=240, paper_bgcolor='#161a18', plot_bgcolor='#161a18',
                                   font_color='#8a9e91', title_font_size=11,
                                   margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig4, use_container_width=True)

        # 保有期間分布
        hold_df = df_f.dropna(subset=['hold_days'])
        if len(hold_df) > 0:
            st.markdown('<div class="section-title">保有期間分布</div>', unsafe_allow_html=True)
            avg_hold = hold_df['hold_days'].mean()
            fig5 = px.histogram(hold_df, x='hold_days', nbins=30,
                                title=f'保有期間（平均 {avg_hold:.0f}日）',
                                labels={'hold_days':'保有日数'},
                                color_discrete_sequence=['#00e676'])
            fig5.update_layout(height=220, paper_bgcolor='#161a18', plot_bgcolor='#161a18',
                               font_color='#8a9e91', title_font_size=11,
                               margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig5, use_container_width=True)

# ====================================================
# TAB 4: 保有ポジション
# ====================================================
with tab_pos:
    st.markdown('<div class="section-title">現在の保有ポジション</div>', unsafe_allow_html=True)

    pos_df = st.session_state.get('positions')

    if pos_df is None or len(pos_df) == 0:
        st.info("「取込」タブで取引履歴CSVを読み込むと、現在の保有ポジションが計算されます。")
    else:
        # 株価取得ボタン
        col_pb, col_pi = st.columns([1, 3])
        with col_pb:
            do_fetch = st.button("📡 株価取得", use_container_width=True)
        with col_pi:
            cache_t = st.session_state.get('price_cache_time', '')
            st.caption(f"{'⚠️ yfinance未インストール' if not YFINANCE_AVAILABLE else f'15分遅延　{cache_t}'}")

        if do_fetch and YFINANCE_AVAILABLE:
            with st.spinner("取得中..."):
                cache = {}
                for _, row in pos_df.iterrows():
                    t = f"{row['ticker']}.T" if row['market'] == '日本株' else row['ticker']
                    try:
                        hist = yf.Ticker(t).history(period='2d')
                        cache[row['ticker']] = float(hist['Close'].iloc[-1]) if len(hist) > 0 else None
                    except: cache[row['ticker']] = None
                st.session_state['price_cache'] = cache
                st.session_state['price_cache_time'] = datetime.now().strftime('%H:%M')
            st.rerun()

        price_cache = st.session_state.get('price_cache', {})

        # サマリー
        total_cost  = sum(float(r['avg_price']) * int(r['quantity']) for _, r in pos_df.iterrows())
        total_upnl  = 0.0
        for _, r in pos_df.iterrows():
            cp = price_cache.get(r['ticker'])
            if cp: total_upnl += (cp - float(r['avg_price'])) * int(r['quantity'])

        upnl_cls = "val-pos" if total_upnl >= 0 else "val-neg"
        sign_u   = "+" if total_upnl >= 0 else ""
        upnl_pct = total_upnl / total_cost * 100 if total_cost > 0 else 0

        st.markdown(f"""
<div class="stat-grid">
  <div class="stat-card">
    <div class="stat-val">{len(pos_df)}</div>
    <div class="stat-lbl">保有銘柄数</div>
  </div>
  <div class="stat-card">
    <div class="stat-val">¥{total_cost:,.0f}</div>
    <div class="stat-lbl">評価額（簿価）</div>
  </div>
  <div class="stat-card">
    <div class="stat-val {upnl_cls}">{sign_u}{upnl_pct:.1f}%</div>
    <div class="stat-lbl">含み損益</div>
  </div>
</div>
""", unsafe_allow_html=True)

        # 銘柄別カード
        for _, row in pos_df.sort_values('ticker').iterrows():
            cp  = price_cache.get(row['ticker'])
            avg = float(row['avg_price'])
            qty = int(row['quantity'])
            type_label = "信用" if row['type'] == 'margin' else "現物"
            flag = "🇯🇵" if row['market'] == '日本株' else "🇺🇸"

            if cp and avg > 0:
                upnl     = (cp - avg) * qty
                upnl_pct_r = (cp - avg) / avg * 100
                upnl_str = f"{'+'if upnl>=0 else ''}¥{upnl:,.0f} ({upnl_pct_r:+.1f}%)"
                upnl_color = "var(--red)" if upnl >= 0 else "var(--blue)"
                cp_str = f"¥{cp:,.1f}"
            else:
                upnl_str = "—"
                upnl_color = "var(--text2)"
                cp_str = "取得中..."

            st.markdown(f"""
<div class="pos-row">
  <div>
    <div class="pos-ticker">{flag} {row['ticker']}</div>
    <div class="pos-sub">{row['name']} · {type_label}</div>
  </div>
  <div class="pos-right">
    <div class="pos-qty">{qty}株　取得均 ¥{avg:,.1f}</div>
    <div class="pos-avg" style="color:{upnl_color};">{upnl_str}</div>
    <div class="pos-avg">現在値 {cp_str}</div>
  </div>
</div>""", unsafe_allow_html=True)

# ====================================================
# TAB 5: 設定
# ====================================================
with tab_settings:
    st.markdown('<div class="section-title">接続情報</div>', unsafe_allow_html=True)
    if sid:
        st.code(f"SPREADSHEET_ID: {sid}")
        st.caption(f"Sheets接続: {'✅ OK' if sheets_client else '❌ 未接続'}")
    else:
        st.warning("SPREADSHEET_ID が未設定です。Railwayの環境変数に設定してください。")
        st.markdown("""
**必要な環境変数（Railway）:**
- `GCP_SERVICE_ACCOUNT_JSON` : サービスアカウントJSONの中身
- `SPREADSHEET_ID` : GoogleスプレッドシートのID
""")

    st.markdown('<div class="section-title">データ操作</div>', unsafe_allow_html=True)

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.button("🔄 Sheetsキャッシュをクリア", use_container_width=True):
            reload_tradelog()
            st.success("✅ クリアしました")
    with col_c2:
        if st.button("🗑 メモリをリセット", use_container_width=True):
            for k in ['realized_df', 'history_df', 'pending', 'tag_state', 'positions', 'price_cache']:
                st.session_state.pop(k, None)
            init_state()
            st.success("✅ メモリをリセットしました")

    st.markdown('<div class="section-title">Trade_Log データ一覧</div>', unsafe_allow_html=True)
    if sheets_client and sid:
        df_view = load_tradelog_cached(sid)
        if len(df_view) > 0:
            df_view['realized_pl'] = pd.to_numeric(df_view['realized_pl'], errors='coerce')
            st.caption(f"登録済み: {len(df_view)}件")
            view_cols = ['trade_date','market','ticker','name','realized_pl','tag_large','tag_detail','satisfaction']
            view_cols_exist = [c for c in view_cols if c in df_view.columns]
            st.dataframe(
                df_view[view_cols_exist].sort_values('trade_date', ascending=False).reset_index(drop=True),
                use_container_width=True, height=400
            )

            if st.button("⚠️ 全データ削除（確認してから押す）", use_container_width=True):
                st.warning("本当に削除しますか？")
                if st.checkbox("はい、全データを削除します"):
                    write_sheet(sheets_client, sid, TRADELOG_SHEET, pd.DataFrame(columns=TRADELOG_COLS))
                    reload_tradelog()
                    st.success("✅ 削除しました")
                    st.rerun()
        else:
            st.info("データなし")
    else:
        st.info("Sheets未接続のため表示できません")

    st.divider()
    st.caption("TradeLog v2 — 爆速分析 × 高度なタグ付け")
