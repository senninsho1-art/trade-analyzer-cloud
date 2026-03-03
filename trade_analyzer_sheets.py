import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, date
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
    initial_sidebar_state="collapsed"
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
    --purple:   #ce93d8;
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
div[data-testid="stTabs"] > div[data-testid="stTabPanel"] { padding-top: 0 !important; }

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
[data-testid="stMetricValue"] { font-family: var(--mono) !important; font-size: 20px !important; }

.stDataFrame { font-size: 12px !important; }
div[data-testid="stRadio"] label { font-size: 12px !important; }
.stCheckbox label { font-size: 13px !important; }

/* カード類 */
.stat-grid  { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin: 8px 0; }
.stat-grid-4 { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 8px; margin: 8px 0; }
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
.section-title::after { content: ''; flex: 1; height: 1px; background: var(--border); }

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

div[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    background: var(--surface) !important;
}

/* タグ階層ラベル */
.tag-layer-label {
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 3px 8px;
    border-radius: 4px;
    margin-bottom: 6px;
    display: inline-block;
}
.tag-layer-large  { background: rgba(0,230,118,0.1);  color: var(--green);  border: 1px solid rgba(0,230,118,0.3); }
.tag-layer-medium { background: rgba(66,165,245,0.1); color: var(--blue);   border: 1px solid rgba(66,165,245,0.3); }
.tag-layer-small  { background: rgba(206,147,216,0.1);color: var(--purple); border: 1px solid rgba(206,147,216,0.3); }
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
    'trade_date', 'build_date',
    'quantity', 'sell_price', 'avg_cost',
    'realized_pl', 'realized_pl_pct',
    'hold_days',
    'tag_large', 'tag_medium', 'tag_small',
    'satisfaction',
    'stop_loss_price', 'discipline',
    'memo',
    'created_at'
]

# ==================== タグ定義（3階層）====================
# 大分類 → 中分類 → 小分類
TAG_TREE = {
    '順張り': {
        '新高値ブレイク':      ['初動買い', '押し目再エントリー', 'ボックス上抜け'],
        'MAパーフェクトオーダー': ['5MA乗り', '25MA反発', '75MA支持'],
        '上昇トレンド押し目':   ['半値押し', 'フィボ押し目', 'トレンドライン反発'],
        '急騰飛び乗り':        ['寄り天回避失敗', '出来高急増', 'ニュース系急騰'],
    },
    '逆張り': {
        '押し目(節目/MA)':     ['ダブルボトム', '三角保ち合い下限', '節目サポート'],
        '二番底':              ['試し買い', '確認後エントリー', 'ナンピン気味'],
        '乖離率/オーバーシュート': ['RSI売られすぎ', 'ボリバン-2σ', '急落翌日'],
        '窓埋め完了':          ['上窓埋め後反発', '下窓埋め後反落', '窓半分埋め'],
    },
    'イベント': {
        '決算後初動':          ['好決算買い', '悪決算売り', 'サプライズ反応'],
        '好決算の売られすぎ':   ['翌日反発狙い', '機関売り終了待ち', '長期目線追加'],
        '決算前先回り':        ['期待先買い', 'オプション絡み', 'アナリスト注目'],
        '政治・ニュース':      ['政策恩恵', '規制リスク', '地政学'],
    },
    'ポジション整理': {
        'ピラミッティング':    ['利益確定一部', '利乗せ追加', 'リスク調整'],
        'ナンピン':            ['計画的ナンピン', '衝動的ナンピン', '最終ナンピン'],
        '現引移行':            ['信用→現物', 'コスト削減', '長期保有転換'],
        'リスクヘッジ':        ['ポートフォリオ調整', '逆方向ヘッジ', '一時退避'],
    },
}

LARGE_TAGS = list(TAG_TREE.keys())

TAG_COLORS = {
    '順張り':         '#00e676',
    '逆張り':         '#42a5f5',
    'イベント':       '#ffca28',
    'ポジション整理':  '#ce93d8',
}

TODAY = date.today()

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

def read_sheet(client, sid, sheet):
    try:
        r = client.values().get(spreadsheetId=sid, range=f"{sheet}!A:ZZ").execute()
        vals = r.get('values', [])
        if not vals: return pd.DataFrame()
        h = vals[0]; rows = [v + [''] * (len(h) - len(v)) for v in vals[1:]]
        return pd.DataFrame(rows, columns=h)
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

# ==================== CSV ヘルパー ====================
def read_csv_auto(file):
    for enc in ['cp932', 'utf-8-sig', 'utf-8', 'shift_jis', 'latin-1']:
        try:
            file.seek(0)
            return pd.read_csv(file, encoding=enc)
        except: continue
    file.seek(0)
    return pd.read_csv(file, encoding='latin-1')

def _clean_num(s):
    return pd.to_numeric(
        s.astype(str).str.replace(',','').str.replace('−','-').str.strip(),
        errors='coerce'
    ).fillna(0)

def parse_realized_jp(df):
    df = df.copy(); df.columns = df.columns.str.strip()
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
    if '建約定日' in df.columns:
        result['build_date'] = pd.to_datetime(df['建約定日'], format='%Y/%m/%d', errors='coerce').dt.strftime('%Y-%m-%d')
    result['realized_pl_pct'] = np.where(
        result['avg_cost'] > 0,
        (result['realized_pl'] / (result['avg_cost'] * result['quantity']) * 100).round(2), 0.0)
    result['hold_days'] = ''
    return result

def parse_realized_us(df):
    df = df.copy(); df.columns = df.columns.str.strip()
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
        (result['realized_pl'] / result['avg_cost'] / result['quantity'] * 100).round(2), 0.0)
    result['hold_days'] = ''
    return result

def parse_history_jp(df):
    df = df.copy(); df.columns = df.columns.str.strip()
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
    df = df.copy(); df.columns = df.columns.str.strip()
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

def calc_positions(df_hist):
    if len(df_hist) == 0: return pd.DataFrame()
    result = []
    for ticker in df_hist['ticker'].unique():
        sub = df_hist[df_hist['ticker'] == ticker].sort_values('trade_date')
        name = sub['name'].iloc[-1]; market = sub['market'].iloc[-1]
        spot = sub[sub['trade_type'].isin(['現物','現引']) | (sub['market']=='米国株')]
        spot_qty = spot[spot['action'].isin(['買付','入庫'])]['quantity'].sum() - spot[spot['action']=='売付']['quantity'].sum()
        kenin = sub[sub['trade_type']=='現引']['quantity'].sum()
        margin_qty = sub[sub['action']=='買建']['quantity'].sum() - sub[sub['action']=='売埋']['quantity'].sum() - kenin

        def avg_price(rows, buy_acts, sell_act):
            qty, avg = 0.0, 0.0
            for _, r in rows.sort_values('trade_date').iterrows():
                q = float(r['quantity']); p = float(r['price'])
                if r['action'] in buy_acts:
                    avg = (avg*qty + p*q)/(qty+q) if (qty+q)>0 else 0; qty += q
                elif r['action'] == sell_act:
                    qty = max(0, qty-q)
                    if qty == 0: avg = 0
            return round(avg, 2)

        if spot_qty > 0:
            buy_acts = ['買付','入庫'] if market=='日本株' else ['買付']
            result.append({'ticker':ticker,'name':name,'market':market,'type':'spot',
                           'quantity':int(spot_qty),'avg_price':avg_price(spot,buy_acts,'売付')})
        if margin_qty > 0:
            result.append({'ticker':ticker,'name':name,'market':market,'type':'margin',
                           'quantity':int(margin_qty),
                           'avg_price':avg_price(sub[sub['action'].isin(['買建','売埋'])],['買建'],'売埋')})
    return pd.DataFrame(result) if result else pd.DataFrame()

# ==================== Sheets キャッシュ ====================
@st.cache_data(ttl=300)
def load_tradelog_cached(sid):
    client = get_sheets_client()
    if not client: return pd.DataFrame(columns=TRADELOG_COLS)
    df = read_sheet(client, sid, TRADELOG_SHEET)
    if len(df) == 0: return pd.DataFrame(columns=TRADELOG_COLS)
    # 旧カラム互換（tag_detail → tag_medium へ移行）
    if 'tag_detail' in df.columns and 'tag_medium' not in df.columns:
        df = df.rename(columns={'tag_detail': 'tag_medium'})
    for col in TRADELOG_COLS:
        if col not in df.columns:
            df[col] = ''
    return df

def reload_tradelog():
    load_tradelog_cached.clear()

# ==================== セッションステート ====================
def init_state():
    defaults = {
        'realized_df': None,
        'history_df': None,
        'pending': [],
        'tag_state': {},
        'positions': None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

sheets_client = get_sheets_client()
sid = get_sid()
if sheets_client and sid:
    init_sheets(sheets_client, sid)

# ==================== ユーティリティ ====================
def hex_to_rgb(h):
    h = h.lstrip('#')
    return ','.join(str(int(h[i:i+2],16)) for i in (0,2,4))

def is_new_trade(trade_date_str):
    """今日以降の取引かどうか"""
    try:
        td = datetime.strptime(str(trade_date_str)[:10], '%Y-%m-%d').date()
        return td >= TODAY
    except:
        return False

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

    realized_parts, history_parts = [], []

    for f, parser, label in [
        (jp_real, parse_realized_jp, "日本株 実現損益"),
        (us_real, parse_realized_us, "米国株 実現損益"),
    ]:
        if f:
            try:
                df = read_csv_auto(f)
                realized_parts.append(parser(df))
                st.success(f"{label}: {len(df)}件 ✅")
            except Exception as e:
                st.error(f"{label} 読み込みエラー: {e}")

    for f, parser, label in [
        (jp_hist, parse_history_jp, "日本株 取引履歴"),
        (us_hist, parse_history_us, "米国株 取引履歴"),
    ]:
        if f:
            try:
                df = read_csv_auto(f)
                history_parts.append(parser(df))
                st.success(f"{label}: {len(df)}件 ✅")
            except Exception as e:
                st.error(f"{label} 読み込みエラー: {e}")

    if realized_parts or history_parts:
        st.divider()
        col_btn, col_info = st.columns([2, 3])
        with col_btn:
            do_import = st.button("⚡ メモリに読み込む", type="primary", use_container_width=True)
        with col_info:
            st.caption("✅ Sheets接続OK" if (sheets_client and sid) else "⚠️ Sheets未接続")

        if do_import:
            if realized_parts:
                combined_r = pd.concat(realized_parts, ignore_index=True)
                combined_r = combined_r.sort_values('trade_date', ascending=False).reset_index(drop=True)

                # 既存ログと差分チェック
                new_trades = []    # 今日以降 → タグ付け対象
                old_trades = []    # 今日より前 → タグなし即保存対象

                if sheets_client and sid:
                    existing = load_tradelog_cached(sid)
                    if len(existing) > 0 and 'ticker' in existing.columns:
                        existing_keys = set(existing['ticker'].astype(str) + '_' + existing['trade_date'].astype(str))
                        combined_r['_key'] = combined_r['ticker'].astype(str) + '_' + combined_r['trade_date'].astype(str)
                        dup_cnt = (combined_r['_key'].isin(existing_keys)).sum()
                        combined_r = combined_r[~combined_r['_key'].isin(existing_keys)].drop('_key', axis=1)
                        if dup_cnt > 0:
                            st.info(f"既登録 {dup_cnt}件をスキップ → 新規 {len(combined_r)}件")

                for _, row in combined_r.iterrows():
                    item = {
                        'idx': int(row.name),
                        'market': row['market'], 'ticker': row['ticker'], 'name': row['name'],
                        'trade_date': row['trade_date'], 'build_date': row.get('build_date',''),
                        'quantity': row['quantity'], 'sell_price': row['sell_price'],
                        'avg_cost': row['avg_cost'], 'realized_pl': row['realized_pl'],
                        'realized_pl_pct': row['realized_pl_pct'],
                    }
                    if is_new_trade(row['trade_date']):
                        new_trades.append(item)
                    else:
                        old_trades.append(item)

                # 過去分はタグなしで即Sheetsへ保存
                if old_trades and sheets_client and sid:
                    save_rows = []
                    for item in old_trades:
                        bd = str(item.get('build_date',''))
                        td = str(item['trade_date'])
                        hold_d = ''
                        if bd and bd not in ('','NaT','nan'):
                            try:
                                hold_d = str((datetime.strptime(td[:10],'%Y-%m-%d') - datetime.strptime(bd[:10],'%Y-%m-%d')).days)
                            except: pass
                        save_rows.append({
                            'id': str(uuid.uuid4())[:8], 'market': item['market'],
                            'ticker': item['ticker'], 'name': item['name'],
                            'trade_date': td, 'build_date': bd,
                            'quantity': item['quantity'], 'sell_price': item['sell_price'],
                            'avg_cost': item['avg_cost'], 'realized_pl': item['realized_pl'],
                            'realized_pl_pct': item['realized_pl_pct'], 'hold_days': hold_d,
                            'tag_large':'', 'tag_medium':'', 'tag_small':'',
                            'satisfaction':'', 'stop_loss_price':'', 'discipline':'0',
                            'memo':'', 'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        })
                    existing = load_tradelog_cached(sid)
                    new_df = pd.DataFrame(save_rows)
                    combined_save = pd.concat([existing, new_df], ignore_index=True) if len(existing)>0 else new_df
                    ok = write_sheet(sheets_client, sid, TRADELOG_SHEET, combined_save)
                    if ok:
                        reload_tradelog()
                        st.success(f"📦 過去分 {len(old_trades)}件をタグなしで保存しました")

                # 今日以降分はタグ付けキューへ
                st.session_state['pending'] = new_trades
                st.session_state['tag_state'] = {}
                st.session_state['realized_df'] = combined_r

                if new_trades:
                    st.info(f"🏷 今日以降の新規取引 {len(new_trades)}件 → タグ付けタブへ")
                else:
                    st.info("今日以降の新規取引はありません（全件タグなし保存済み）")

            if history_parts:
                combined_h = pd.concat(history_parts, ignore_index=True)
                st.session_state['history_df'] = combined_h
                st.session_state['positions'] = calc_positions(combined_h)

            st.rerun()

    # メモリ状態
    st.divider()
    st.markdown('<div class="section-title">現在のメモリ状態</div>', unsafe_allow_html=True)
    r = st.session_state.get('realized_df')
    p = st.session_state.get('pending', [])
    h = st.session_state.get('history_df')
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="stat-card"><div class="stat-val val-green">{len(r) if r is not None else 0}</div><div class="stat-lbl">実現損益レコード</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-card"><div class="stat-val val-yellow">{len(p)}</div><div class="stat-lbl">タグ付け待ち（今日以降）</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="stat-card"><div class="stat-val">{len(h) if h is not None else 0}</div><div class="stat-lbl">取引履歴レコード</div></div>', unsafe_allow_html=True)

# ====================================================
# TAB 2: タグ付け（今日以降の取引のみ）
# ====================================================
with tab_tag:
    pending_list = st.session_state.get('pending', [])
    tag_state    = st.session_state.get('tag_state', {})
    has_pending  = len(pending_list) > 0

    tagged_idxs   = {i for i, ts in tag_state.items() if ts.get('large')}
    untagged_list = [p for p in pending_list if p['idx'] not in tagged_idxs]
    tagged_list   = [p for p in pending_list if p['idx'] in tagged_idxs]
    total_cnt = len(pending_list)

    if not has_pending:
        st.info("🏷 タグ付けするデータがありません。\n\n今日以降の新規取引をCSV取込すると、ここでタグ付けできます。\n（過去分はタグなしで自動保存されます）")
    else:
        remain = len(untagged_list)
        done   = len(tagged_list)
        pct    = int(done / total_cnt * 100) if total_cnt > 0 else 0

        col_h1, col_h2 = st.columns([3, 2])
        with col_h1:
            st.markdown(f"""
<div style="padding:8px 0 4px;">
  <span style="font-size:12px;color:var(--text2);">未タグ付け</span>
  <span class="counter-badge" style="margin:0 8px;">{remain}件</span>
  <span style="font-size:11px;color:var(--text2);">完了 {done}/{total_cnt}件</span>
</div>""", unsafe_allow_html=True)
        with col_h2:
            can_save = bool(sheets_client and sid and done > 0)
            if st.button(f"💾 {done}件をSheetsへ保存",
                         disabled=not can_save,
                         type="primary" if can_save else "secondary",
                         use_container_width=True, key="bulk_save_btn"):
                save_rows = []
                for p_item in tagged_list:
                    idx = p_item['idx']; ts = tag_state[idx]
                    bd = str(p_item.get('build_date','')); td = str(p_item['trade_date'])
                    hold_d = ''
                    if bd and bd not in ('','NaT','nan'):
                        try: hold_d = str((datetime.strptime(td[:10],'%Y-%m-%d') - datetime.strptime(bd[:10],'%Y-%m-%d')).days)
                        except: pass
                    save_rows.append({
                        'id': str(uuid.uuid4())[:8], 'market': p_item['market'],
                        'ticker': p_item['ticker'], 'name': p_item['name'],
                        'trade_date': td, 'build_date': bd,
                        'quantity': p_item['quantity'], 'sell_price': p_item['sell_price'],
                        'avg_cost': p_item['avg_cost'], 'realized_pl': p_item['realized_pl'],
                        'realized_pl_pct': p_item['realized_pl_pct'], 'hold_days': hold_d,
                        'tag_large': ts.get('large',''), 'tag_medium': ts.get('medium',''),
                        'tag_small': ts.get('small',''),
                        'satisfaction': ts.get('satisfaction',''),
                        'stop_loss_price': ts.get('stop_loss',''),
                        'discipline': '1' if ts.get('discipline',False) else '0',
                        'memo': ts.get('memo',''),
                        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    })
                if save_rows:
                    existing = load_tradelog_cached(sid)
                    new_df = pd.DataFrame(save_rows)
                    combined_save = pd.concat([existing, new_df], ignore_index=True) if len(existing)>0 else new_df
                    ok = write_sheet(sheets_client, sid, TRADELOG_SHEET, combined_save)
                    if ok:
                        reload_tradelog()
                        saved_idxs = {p['idx'] for p in tagged_list}
                        st.session_state['pending']   = [x for x in st.session_state['pending'] if x['idx'] not in saved_idxs]
                        st.session_state['tag_state'] = {k:v for k,v in st.session_state['tag_state'].items() if k not in saved_idxs}
                        st.success(f"✅ {len(save_rows)}件を保存しました！")
                        st.rerun()

        st.progress(pct / 100)

        # ── 未タグ付けカード ──
        if untagged_list:
            st.markdown('<div class="section-title">未タグ付け</div>', unsafe_allow_html=True)

            for p_item in untagged_list[:15]:
                idx = p_item['idx']
                ts  = tag_state.get(idx, {})
                pl  = float(p_item['realized_pl'])
                pl_pct = float(p_item.get('realized_pl_pct', 0))
                flag = "🇯🇵" if p_item['market'] == '日本株' else "🇺🇸"

                # カード色
                if pl >= 0:
                    card_border = "#ef5350"; card_bg = "rgba(239,83,80,0.06)"; pl_color = "#ef5350"
                else:
                    card_border = "#42a5f5"; card_bg = "rgba(66,165,245,0.06)"; pl_color = "#42a5f5"

                sel_large = ts.get('large', '')
                if sel_large and sel_large in TAG_COLORS:
                    tc = TAG_COLORS[sel_large]
                    card_border = tc
                    card_bg = f"rgba({hex_to_rgb(tc)},0.08)"

                pl_sign = "+" if pl >= 0 else ""

                st.markdown(f"""
<div style="background:{card_bg};border:1px solid #2a312e;border-left:4px solid {card_border};
     border-radius:10px;padding:14px 16px 8px;margin-bottom:4px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
    <div>
      <div style="font-family:var(--mono);font-size:15px;font-weight:600;">{flag} {p_item['ticker']}</div>
      <div style="font-size:11px;color:var(--text2);margin-top:2px;">{p_item['name']}</div>
    </div>
    <div style="text-align:right;">
      <div style="font-family:var(--mono);font-size:18px;font-weight:700;color:{pl_color};">{pl_sign}¥{pl:,.0f}</div>
      <div style="font-size:11px;color:{pl_color};font-family:var(--mono);">{pl_pct:+.1f}%</div>
    </div>
  </div>
  <div style="display:flex;gap:10px;flex-wrap:wrap;">
    <span style="font-size:10px;color:var(--text2);font-family:var(--mono);">📅 {p_item['trade_date']}</span>
    <span style="font-size:10px;color:var(--text2);font-family:var(--mono);">📊 {int(p_item['quantity'])}株</span>
    <span style="font-size:10px;color:var(--text2);font-family:var(--mono);">売 ¥{float(p_item['sell_price']):,.1f}</span>
    <span style="font-size:10px;color:var(--text2);font-family:var(--mono);">取得 ¥{float(p_item['avg_cost']):,.1f}</span>
  </div>
</div>""", unsafe_allow_html=True)

                # ── 大分類 ──
                st.markdown('<span class="tag-layer-label tag-layer-large">大分類</span>', unsafe_allow_html=True)
                lg_cols = st.columns(len(LARGE_TAGS))
                for ci, tag in enumerate(LARGE_TAGS):
                    with lg_cols[ci]:
                        is_sel = ts.get('large') == tag
                        label  = f"✓ {tag}" if is_sel else tag
                        if st.button(label, key=f"lg_{idx}_{tag}", use_container_width=True):
                            if idx not in st.session_state['tag_state']:
                                st.session_state['tag_state'][idx] = {}
                            if st.session_state['tag_state'][idx].get('large') == tag:
                                # 選択解除 → 中・小も消す
                                for k in ('large','medium','small'): st.session_state['tag_state'][idx].pop(k, None)
                            else:
                                st.session_state['tag_state'][idx]['large'] = tag
                                for k in ('medium','small'): st.session_state['tag_state'][idx].pop(k, None)
                            st.rerun()

                # ── 中分類（大分類選択後）──
                if ts.get('large') and ts['large'] in TAG_TREE:
                    mediums = list(TAG_TREE[ts['large']].keys())
                    st.markdown(f'<span class="tag-layer-label tag-layer-medium">中分類（{ts["large"]}）</span>', unsafe_allow_html=True)
                    m_cols = st.columns(min(len(mediums), 4))
                    for mi, mtag in enumerate(mediums):
                        with m_cols[mi % 4]:
                            is_sel = ts.get('medium') == mtag
                            label  = f"✓ {mtag}" if is_sel else mtag
                            if st.button(label, key=f"md_{idx}_{mtag}", use_container_width=True):
                                if st.session_state['tag_state'][idx].get('medium') == mtag:
                                    for k in ('medium','small'): st.session_state['tag_state'][idx].pop(k, None)
                                else:
                                    st.session_state['tag_state'][idx]['medium'] = mtag
                                    st.session_state['tag_state'][idx].pop('small', None)
                                st.rerun()

                    # ── 小分類（中分類選択後）──
                    sel_medium = ts.get('medium','')
                    if sel_medium and sel_medium in TAG_TREE.get(ts['large'], {}):
                        smalls = TAG_TREE[ts['large']][sel_medium]
                        st.markdown(f'<span class="tag-layer-label tag-layer-small">小分類（{sel_medium}）</span>', unsafe_allow_html=True)
                        s_cols = st.columns(min(len(smalls), 4))
                        for si, stag in enumerate(smalls):
                            with s_cols[si % 4]:
                                is_sel = ts.get('small') == stag
                                label  = f"✓ {stag}" if is_sel else stag
                                if st.button(label, key=f"sm_{idx}_{stag}", use_container_width=True):
                                    if st.session_state['tag_state'][idx].get('small') == stag:
                                        st.session_state['tag_state'][idx].pop('small', None)
                                    else:
                                        st.session_state['tag_state'][idx]['small'] = stag
                                    st.rerun()

                # ── 納得度・損切り・規律・メモ（フォーム）──
                with st.form(key=f"form_{idx}", clear_on_submit=False):
                    col_sat, col_sl = st.columns(2)
                    with col_sat:
                        st.markdown('<div style="font-size:11px;color:var(--text2);margin-bottom:4px;">⭐ 納得度</div>', unsafe_allow_html=True)
                        cur_sat = ts.get('satisfaction', 3)
                        sat_val = st.select_slider("納得度", options=[1,2,3,4,5],
                            value=cur_sat if cur_sat else 3,
                            format_func=lambda x: "★"*x + "☆"*(5-x),
                            key=f"sat_sl_{idx}", label_visibility='collapsed')
                    with col_sl:
                        st.markdown('<div style="font-size:11px;color:var(--text2);margin-bottom:4px;">🛑 当初損切り価格</div>', unsafe_allow_html=True)
                        cur_sl_val = ts.get('stop_loss', 0.0)
                        sl_val = st.number_input("損切り", min_value=0.0,
                            value=float(cur_sl_val) if cur_sl_val else 0.0,
                            step=1.0, format="%.1f", key=f"sl_f_{idx}", label_visibility='collapsed')
                    disc_val = st.checkbox("✅ 損切りルールを守った", value=ts.get('discipline',False), key=f"disc_f_{idx}")
                    memo_val = st.text_input("💬 メモ（任意）", value=ts.get('memo',''), key=f"memo_f_{idx}")

                    submitted = st.form_submit_button("✔ この件を確定", use_container_width=True)
                    if submitted:
                        if idx not in st.session_state['tag_state']:
                            st.session_state['tag_state'][idx] = {}
                        st.session_state['tag_state'][idx].update({
                            'satisfaction': sat_val, 'stop_loss': sl_val,
                            'discipline': disc_val, 'memo': memo_val,
                        })
                        if not st.session_state['tag_state'][idx].get('large'):
                            st.warning("大分類を選択してください")
                        else:
                            st.rerun()

                st.markdown('<div style="height:12px;border-bottom:1px solid #2a312e;margin-bottom:12px;"></div>', unsafe_allow_html=True)

            if len(untagged_list) > 15:
                st.caption(f"残り {len(untagged_list) - 15}件は確定後に表示されます")

        # ── 確定済み（未保存）一覧 ──
        if tagged_list:
            st.markdown('<div class="section-title">確定済み（Sheets未保存）</div>', unsafe_allow_html=True)
            for p_item in tagged_list:
                idx = p_item['idx']; ts = tag_state[idx]
                pl  = float(p_item['realized_pl'])
                pl_color = "#ef5350" if pl >= 0 else "#42a5f5"
                flag = "🇯🇵" if p_item['market'] == '日本株' else "🇺🇸"
                tag_c = TAG_COLORS.get(ts.get('large',''), '#00e676')
                sign  = "+" if pl >= 0 else ""
                sat_stars = "★" * int(ts.get('satisfaction') or 0)

                badges = f'<span class="badge" style="background:rgba({hex_to_rgb(tag_c)},0.15);color:{tag_c};border:1px solid {tag_c}40;">{ts.get("large","")}</span>'
                if ts.get('medium'): badges += f' <span class="badge badge-tagged">{ts["medium"]}</span>'
                if ts.get('small'):  badges += f' <span class="badge badge-pending">{ts["small"]}</span>'
                if sat_stars:        badges += f' <span style="font-size:11px;color:#ffca28;">{sat_stars}</span>'

                st.markdown(f"""
<div style="background:var(--surface);border:1px solid #2a312e;border-left:4px solid {tag_c};
     border-radius:8px;padding:10px 14px;margin-bottom:6px;
     display:flex;justify-content:space-between;align-items:center;opacity:0.85;">
  <div>
    <div style="font-family:var(--mono);font-size:13px;font-weight:600;">{flag} {p_item['ticker']}</div>
    <div style="margin-top:4px;display:flex;gap:6px;flex-wrap:wrap;">{badges}</div>
  </div>
  <div style="font-family:var(--mono);font-size:15px;font-weight:700;color:{pl_color};">{sign}¥{pl:,.0f}</div>
</div>""", unsafe_allow_html=True)

# ====================================================
# TAB 3: 分析ダッシュボード
# ====================================================
with tab_dash:
    if sheets_client and sid:
        df_log = load_tradelog_cached(sid)
    else:
        df_log = pd.DataFrame(columns=TRADELOG_COLS)

    if len(df_log) == 0:
        st.info("分析データがありません。CSVを取込んでください。")
    else:
        df_log['realized_pl']     = pd.to_numeric(df_log['realized_pl'], errors='coerce').fillna(0)
        df_log['realized_pl_pct'] = pd.to_numeric(df_log['realized_pl_pct'], errors='coerce').fillna(0)
        df_log['quantity']        = pd.to_numeric(df_log['quantity'], errors='coerce').fillna(0)
        df_log['hold_days']       = pd.to_numeric(df_log['hold_days'], errors='coerce')
        df_log['satisfaction']    = pd.to_numeric(df_log['satisfaction'], errors='coerce')
        df_log['trade_date']      = pd.to_datetime(df_log['trade_date'], errors='coerce')
        df_log = df_log.dropna(subset=['trade_date'])

        # 期間フィルター
        period_opt = st.radio("期間", ["全期間", "過去1年", "過去1ヶ月"], horizontal=True)
        today_ts = pd.Timestamp.today()
        if period_opt == "過去1年":
            df_f = df_log[df_log['trade_date'] >= today_ts - timedelta(days=365)]
        elif period_opt == "過去1ヶ月":
            df_f = df_log[df_log['trade_date'] >= today_ts - timedelta(days=30)]
        else:
            df_f = df_log.copy()

        df_f = df_f.copy()

        # ==================== KPI ====================
        total_pl     = df_f['realized_pl'].sum()
        total_trades = len(df_f)
        wins         = (df_f['realized_pl'] > 0).sum()
        losses       = (df_f['realized_pl'] < 0).sum()
        win_rate     = wins / total_trades * 100 if total_trades > 0 else 0
        avg_win      = df_f[df_f['realized_pl'] > 0]['realized_pl'].mean() if wins > 0 else 0
        avg_loss     = abs(df_f[df_f['realized_pl'] < 0]['realized_pl'].mean()) if losses > 0 else 1
        pf           = avg_win / avg_loss if avg_loss > 0 else 0
        tagged_cnt   = df_f['tag_large'].astype(str).str.strip().ne('').sum()

        pl_cls = "val-pos" if total_pl >= 0 else "val-neg"
        sign   = "+" if total_pl >= 0 else ""

        st.markdown(f"""
<div class="stat-grid-4">
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
  <div class="stat-card">
    <div class="stat-val val-yellow">{tagged_cnt}/{total_trades}</div>
    <div class="stat-lbl">タグ付き件数</div>
  </div>
</div>
""", unsafe_allow_html=True)

        # ==================== 損益推移 ====================
        st.markdown('<div class="section-title">損益推移</div>', unsafe_allow_html=True)
        df_daily = df_f.groupby(df_f['trade_date'].dt.date)['realized_pl'].sum().reset_index()
        df_daily.columns = ['date','daily_pl']
        df_daily = df_daily.sort_values('date')
        df_daily['cumulative'] = df_daily['daily_pl'].cumsum()
        df_daily['color'] = df_daily['daily_pl'].apply(lambda x: '#ef5350' if x >= 0 else '#42a5f5')

        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_daily['date'], y=df_daily['daily_pl'],
                             marker_color=df_daily['color'], name='日次損益', opacity=0.7))
        fig.add_trace(go.Scatter(x=df_daily['date'], y=df_daily['cumulative'],
                                 mode='lines', name='累積',
                                 line=dict(color='#00e676', width=2), yaxis='y2'))
        fig.update_layout(
            height=280, paper_bgcolor='#161a18', plot_bgcolor='#161a18',
            font=dict(color='#8a9e91', size=10, family='DM Mono'),
            margin=dict(l=0,r=0,t=10,b=0),
            legend=dict(orientation='h', yanchor='bottom', y=1, font_size=10),
            yaxis=dict(gridcolor='#2a312e', zeroline=False),
            yaxis2=dict(overlaying='y', side='right', gridcolor='rgba(0,0,0,0)', zeroline=False),
            xaxis=dict(gridcolor='#2a312e'),
            hovermode='x unified',
        )
        st.plotly_chart(fig, use_container_width=True)

        # ==================== 銘柄別スタッツ ====================
        st.markdown('<div class="section-title">銘柄別スタッツ</div>', unsafe_allow_html=True)
        ticker_stats = df_f.groupby('ticker').agg(
            名前=('name','last'), 取引数=('realized_pl','count'),
            勝率=('realized_pl', lambda x: round((x>0).mean()*100,1)),
            総損益=('realized_pl','sum'), 平均損益=('realized_pl','mean'),
            平均利益=('realized_pl', lambda x: round(x[x>0].mean(),0) if (x>0).any() else 0),
            平均損失=('realized_pl', lambda x: round(abs(x[x<0].mean()),0) if (x<0).any() else 0),
            平均保有日=('hold_days','mean'),
        ).round(1).sort_values('総損益', ascending=False).reset_index()
        ticker_stats['総損益']  = ticker_stats['総損益'].astype(int)
        ticker_stats['平均損益'] = ticker_stats['平均損益'].round(0).astype(int)
        st.dataframe(ticker_stats, use_container_width=True, height=280)

        # ==================== 曜日別 ====================
        st.markdown('<div class="section-title">曜日別 勝率</div>', unsafe_allow_html=True)
        df_f['weekday'] = df_f['trade_date'].dt.day_name()
        day_order = ['Monday','Tuesday','Wednesday','Thursday','Friday']
        day_jp    = {'Monday':'月','Tuesday':'火','Wednesday':'水','Thursday':'木','Friday':'金'}
        wday = df_f.groupby('weekday').agg(
            勝率=('realized_pl', lambda x: round((x>0).mean()*100,1)),
            総損益=('realized_pl','sum'), 件数=('realized_pl','count'),
        ).reindex([d for d in day_order if d in df_f['weekday'].unique()]).reset_index()
        wday['曜日'] = wday['weekday'].map(day_jp)
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=wday['曜日'], y=wday['勝率'], marker_color='#00e676', opacity=0.8,
                              text=wday['勝率'].apply(lambda x: f"{x:.0f}%"),
                              textposition='outside', textfont=dict(size=11,color='#8a9e91')))
        fig2.update_layout(height=220, paper_bgcolor='#161a18', plot_bgcolor='#161a18',
                           font=dict(color='#8a9e91',size=10,family='DM Mono'),
                           margin=dict(l=0,r=0,t=10,b=0),
                           yaxis=dict(gridcolor='#2a312e', range=[0,110]),
                           xaxis=dict(gridcolor='rgba(0,0,0,0)'))
        st.plotly_chart(fig2, use_container_width=True)

        # ==================== タグ別（タグありデータのみ）====================
        tagged_df = df_f[df_f['tag_large'].astype(str).str.strip() != '']
        if len(tagged_df) > 0:
            st.markdown('<div class="section-title">タグ別パフォーマンス（タグ付き取引のみ）</div>', unsafe_allow_html=True)

            # 大分類別
            tag_stats = tagged_df.groupby('tag_large').agg(
                件数=('realized_pl','count'),
                勝率=('realized_pl', lambda x: round((x>0).mean()*100,1)),
                総損益=('realized_pl','sum'), 平均損益=('realized_pl','mean'),
                平均納得度=('satisfaction','mean'),
            ).round(1).sort_values('総損益', ascending=False).reset_index()
            tag_stats['総損益'] = tag_stats['総損益'].astype(int)

            col_t1, col_t2 = st.columns(2)
            with col_t1:
                fig3 = px.bar(tag_stats, x='tag_large', y='総損益',
                              color='勝率', color_continuous_scale=[[0,'#42a5f5'],[0.5,'#ffca28'],[1,'#ef5350']],
                              title='大分類別 総損益', labels={'tag_large':'タグ','総損益':'損益（円）'})
                fig3.update_layout(height=240, paper_bgcolor='#161a18', plot_bgcolor='#161a18',
                                   font_color='#8a9e91', title_font_size=11, margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig3, use_container_width=True)
            with col_t2:
                fig4 = px.bar(tag_stats, x='tag_large', y='勝率', title='大分類別 勝率%',
                              labels={'tag_large':'タグ','勝率':'勝率(%)'},
                              color_discrete_sequence=['#00e676'])
                fig4.update_layout(height=240, paper_bgcolor='#161a18', plot_bgcolor='#161a18',
                                   font_color='#8a9e91', title_font_size=11, margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig4, use_container_width=True)

            # 中分類別（データがあれば）
            if 'tag_medium' in tagged_df.columns:
                med_df = tagged_df[tagged_df['tag_medium'].astype(str).str.strip() != '']
                if len(med_df) > 0:
                    st.markdown('<div class="section-title">中分類別 損益</div>', unsafe_allow_html=True)
                    med_stats = med_df.groupby(['tag_large','tag_medium']).agg(
                        件数=('realized_pl','count'),
                        勝率=('realized_pl', lambda x: round((x>0).mean()*100,1)),
                        総損益=('realized_pl','sum'),
                    ).reset_index()
                    med_stats['総損益'] = med_stats['総損益'].astype(int)
                    med_stats['ラベル'] = med_stats['tag_large'] + '/' + med_stats['tag_medium']
                    fig_med = px.bar(med_stats.sort_values('総損益'), x='総損益', y='ラベル',
                                     orientation='h', color='勝率',
                                     color_continuous_scale=[[0,'#42a5f5'],[0.5,'#ffca28'],[1,'#ef5350']],
                                     title='中分類別 総損益')
                    fig_med.update_layout(height=max(240, len(med_stats)*28),
                                          paper_bgcolor='#161a18', plot_bgcolor='#161a18',
                                          font_color='#8a9e91', title_font_size=11,
                                          margin=dict(l=0,r=0,t=30,b=0))
                    st.plotly_chart(fig_med, use_container_width=True)

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
        col_pb, col_pi = st.columns([1,3])
        with col_pb:
            do_fetch = st.button("📡 株価取得", use_container_width=True)
        with col_pi:
            cache_t = st.session_state.get('price_cache_time','')
            st.caption(f"{'⚠️ yfinance未インストール' if not YFINANCE_AVAILABLE else f'15分遅延　{cache_t}'}")

        if do_fetch and YFINANCE_AVAILABLE:
            with st.spinner("取得中..."):
                cache = {}
                for _, row in pos_df.iterrows():
                    t = f"{row['ticker']}.T" if row['market']=='日本株' else row['ticker']
                    try:
                        hist = yf.Ticker(t).history(period='2d')
                        cache[row['ticker']] = float(hist['Close'].iloc[-1]) if len(hist)>0 else None
                    except: cache[row['ticker']] = None
                st.session_state['price_cache'] = cache
                st.session_state['price_cache_time'] = datetime.now().strftime('%H:%M')
            st.rerun()

        price_cache = st.session_state.get('price_cache', {})
        total_cost  = sum(float(r['avg_price'])*int(r['quantity']) for _,r in pos_df.iterrows())
        total_upnl  = sum((price_cache.get(r['ticker'],0) or 0 - float(r['avg_price']))*int(r['quantity'])
                          for _,r in pos_df.iterrows() if price_cache.get(r['ticker']))

        upnl_cls = "val-pos" if total_upnl >= 0 else "val-neg"
        sign_u   = "+" if total_upnl >= 0 else ""
        upnl_pct = total_upnl / total_cost * 100 if total_cost > 0 else 0

        st.markdown(f"""
<div class="stat-grid">
  <div class="stat-card"><div class="stat-val">{len(pos_df)}</div><div class="stat-lbl">保有銘柄数</div></div>
  <div class="stat-card"><div class="stat-val">¥{total_cost:,.0f}</div><div class="stat-lbl">評価額（簿価）</div></div>
  <div class="stat-card"><div class="stat-val {upnl_cls}">{sign_u}{upnl_pct:.1f}%</div><div class="stat-lbl">含み損益</div></div>
</div>""", unsafe_allow_html=True)

        for _, row in pos_df.sort_values('ticker').iterrows():
            cp  = price_cache.get(row['ticker'])
            avg = float(row['avg_price']); qty = int(row['quantity'])
            type_label = "信用" if row['type']=='margin' else "現物"
            flag = "🇯🇵" if row['market']=='日本株' else "🇺🇸"
            if cp and avg > 0:
                upnl = (cp-avg)*qty; upnl_pct_r = (cp-avg)/avg*100
                upnl_str = f"{'+'if upnl>=0 else ''}¥{upnl:,.0f} ({upnl_pct_r:+.1f}%)"
                upnl_color = "var(--red)" if upnl>=0 else "var(--blue)"
                cp_str = f"¥{cp:,.1f}"
            else:
                upnl_str = "—"; upnl_color = "var(--text2)"; cp_str = "取得中..."

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
        st.warning("SPREADSHEET_ID が未設定です。")
        st.markdown("**必要な環境変数（Railway）:**\n- `GCP_SERVICE_ACCOUNT_JSON`\n- `SPREADSHEET_ID`")

    st.markdown('<div class="section-title">データ操作</div>', unsafe_allow_html=True)
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.button("🔄 Sheetsキャッシュをクリア", use_container_width=True):
            reload_tradelog(); st.success("✅ クリアしました")
    with col_c2:
        if st.button("🗑 メモリをリセット", use_container_width=True):
            for k in ['realized_df','history_df','pending','tag_state','positions','price_cache']:
                st.session_state.pop(k, None)
            init_state(); st.success("✅ リセットしました")

    st.markdown('<div class="section-title">Trade_Log データ一覧</div>', unsafe_allow_html=True)
    if sheets_client and sid:
        df_view = load_tradelog_cached(sid)
        if len(df_view) > 0:
            df_view['realized_pl'] = pd.to_numeric(df_view['realized_pl'], errors='coerce')
            st.caption(f"登録済み: {len(df_view)}件（うちタグ付き: {df_view['tag_large'].astype(str).str.strip().ne('').sum()}件）")
            view_cols = ['trade_date','market','ticker','name','realized_pl','tag_large','tag_medium','tag_small','satisfaction']
            view_cols_exist = [c for c in view_cols if c in df_view.columns]
            st.dataframe(
                df_view[view_cols_exist].sort_values('trade_date',ascending=False).reset_index(drop=True),
                use_container_width=True, height=400
            )
            if st.button("⚠️ 全データ削除（確認してから押す）", use_container_width=True):
                st.warning("本当に削除しますか？")
                if st.checkbox("はい、全データを削除します"):
                    write_sheet(sheets_client, sid, TRADELOG_SHEET, pd.DataFrame(columns=TRADELOG_COLS))
                    reload_tradelog(); st.success("✅ 削除しました"); st.rerun()
        else:
            st.info("データなし")
    else:
        st.info("Sheets未接続のため表示できません")

    st.divider()
    st.caption("TradeLog v2 — 爆速分析 × 高度なタグ付け")
