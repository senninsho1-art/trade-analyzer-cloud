import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
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
    page_title="トレード分析＆資金管理",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==================== カスタムCSS（モバイルファースト・黒×白×濃緑） ====================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Noto+Sans+JP:wght@300;400;500;700&display=swap');

:root {
    --black: #0a0a0a;
    --white: #f7f7f5;
    --green: #1a4a2e;
    --green-mid: #2d6e47;
    --green-light: #3d9960;
    --green-glow: rgba(26,74,46,0.15);
    --gray-dark: #1c1c1c;
    --gray-mid: #2e2e2e;
    --border: #2a2a2a;
    --yellow: #d4a017;
    --red: #c0392b;
}

html, body, [class*="css"] {
    font-family: 'Noto Sans JP', sans-serif;
    background-color: var(--black) !important;
    color: var(--white) !important;
}

.main .block-container {
    padding-top: 60px !important;
    padding-bottom: 1rem;
    padding-left: 0.75rem;
    padding-right: 0.75rem;
    max-width: 100%;
    background-color: var(--black) !important;
}

/* タブを画面上部に固定 */
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    z-index: 99999 !important;
    background-color: var(--gray-dark) !important;
    padding: 6px 8px 0 8px !important;
    border-bottom: 2px solid var(--green) !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.5) !important;
}
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] button {
    font-size: 11px !important;
    padding: 10px 6px !important;
    min-width: 0 !important;
    font-family: 'Space Mono', monospace !important;
    color: #666 !important;
}
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] button[aria-selected="true"] {
    color: var(--green-light) !important;
    border-bottom: 2px solid var(--green-light) !important;
}
div[data-testid="stTabs"] > div[data-testid="stTabPanel"] {
    padding-top: 52px !important;
}

h1 { font-size: 1.1rem !important; font-family: 'Space Mono', monospace !important; color: var(--green-light) !important; }
h2 { font-size: 1.0rem !important; font-family: 'Space Mono', monospace !important; }
h3 { font-size: 0.95rem !important; }

.stButton button {
    width: 100%;
    height: 44px;
    font-size: 13px;
    margin: 3px 0;
    border-radius: 8px;
    font-family: 'Space Mono', monospace !important;
}
.stButton button[kind="primary"] {
    background-color: var(--green) !important;
    border-color: var(--green-mid) !important;
    color: white !important;
}
.stButton button[kind="primary"]:hover {
    background-color: var(--green-mid) !important;
}

.stTextInput input, .stNumberInput input, .stSelectbox select {
    height: 42px;
    font-size: 14px;
    background-color: var(--gray-dark) !important;
    border-color: var(--border) !important;
    color: var(--white) !important;
    border-radius: 8px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: var(--green-mid) !important;
    box-shadow: 0 0 0 2px var(--green-glow) !important;
}

.stDataFrame { font-size: 12px !important; }

/* カスタムコンポーネント */
.pos-table-header {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr 1fr;
    padding: 8px 14px;
    background: var(--green);
    border-radius: 8px 8px 0 0;
    font-family: 'Space Mono', monospace;
    font-size: 9px;
    letter-spacing: 0.08em;
    color: rgba(255,255,255,0.6);
    text-transform: uppercase;
    gap: 4px;
}
.pos-row {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr 1fr;
    padding: 11px 14px;
    gap: 4px;
    border-bottom: 1px solid var(--border);
    background: var(--gray-dark);
    align-items: center;
    cursor: pointer;
    transition: background 0.15s;
    position: relative;
}
.pos-row:last-child { border-radius: 0 0 8px 8px; border-bottom: none; }
.pos-row:hover { background: rgba(255,255,255,0.04); }
.pos-row.selected { background: var(--green-glow) !important; }
.pos-row .left-bar-green::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: var(--green-light);
    border-radius: 0 2px 2px 0;
}
.pos-row .left-bar-yellow::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: var(--yellow);
    border-radius: 0 2px 2px 0;
}
.ticker-name { font-family: 'Space Mono', monospace; font-size: 13px; font-weight: 700; }
.stock-sub { font-size: 10px; color: #888; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.num-cell { font-family: 'Space Mono', monospace; font-size: 11px; text-align: right; color: #999; }
.pnl-pos { font-family: 'Space Mono', monospace; font-size: 12px; font-weight: 700; text-align: right; color: var(--green-light); }
.pnl-neg { font-family: 'Space Mono', monospace; font-size: 12px; font-weight: 700; text-align: right; color: var(--red); }
.badge-done {
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 9px; font-family: 'Space Mono', monospace;
    padding: 2px 6px; border-radius: 4px; letter-spacing: 0.06em;
    background: rgba(61,153,96,0.15); color: var(--green-light);
    border: 1px solid rgba(61,153,96,0.3);
}
.badge-pending {
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 9px; font-family: 'Space Mono', monospace;
    padding: 2px 6px; border-radius: 4px; letter-spacing: 0.06em;
    background: rgba(212,160,23,0.12); color: var(--yellow);
    border: 1px solid rgba(212,160,23,0.3);
}
.form-panel {
    background: var(--gray-mid);
    border: 1px solid var(--green-mid);
    border-radius: 12px;
    padding: 16px;
    margin: 8px 0 16px 0;
}
.form-title {
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.1em;
    color: var(--green-light);
    margin-bottom: 14px;
}
.entered-card {
    background: var(--gray-dark);
    border: 1px solid rgba(26,74,46,0.4);
    border-left: 3px solid var(--green-light);
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 8px;
}
.entered-ticker { font-family: 'Space Mono', monospace; font-size: 14px; font-weight: 700; }
.entered-sub { font-size: 10px; color: #888; margin-top: 2px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 16px; margin-top: 10px; }
.d-label { font-size: 9px; color: #888; font-family: 'Space Mono', monospace; letter-spacing: 0.06em; margin-bottom: 1px; }
.d-val { font-size: 12px; font-family: 'Space Mono', monospace; }
.d-val-green { color: var(--green-light); }
.notif-bar {
    background: rgba(212,160,23,0.08);
    border: 1px solid rgba(212,160,23,0.25);
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
}
.notif-text { font-size: 12px; color: var(--yellow); }
.notif-count {
    font-family: 'Space Mono', monospace; font-size: 11px; font-weight: 700;
    background: var(--yellow); color: var(--black);
    border-radius: 10px; padding: 2px 8px;
}
.summary-grid {
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    gap: 8px; margin-bottom: 16px;
}
.summary-card {
    background: var(--gray-dark);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 10px;
    text-align: center;
}
.summary-card.hl { border-color: var(--green-mid); background: linear-gradient(135deg, var(--gray-dark), rgba(26,74,46,0.2)); }
.s-val { font-family: 'Space Mono', monospace; font-size: 16px; font-weight: 700; line-height: 1.1; margin-bottom: 4px; }
.s-val-pos { color: var(--green-light); }
.s-val-neg { color: var(--red); }
.s-val-yellow { color: var(--yellow); }
.s-lbl { font-size: 10px; color: #888; }
.section-label {
    font-family: 'Space Mono', monospace;
    font-size: 10px; letter-spacing: 0.12em;
    color: var(--green-light); text-transform: uppercase;
    margin-bottom: 10px; margin-top: 4px;
    display: flex; align-items: center; gap: 8px;
}
.import-date { font-size: 0.72rem; color: #666; margin-top: 4px; text-align: center; font-family: 'Space Mono', monospace; }

/* 設定タブ削除ボタン */
.del-btn button { background: rgba(192,57,43,0.15) !important; border-color: rgba(192,57,43,0.4) !important; color: #e74c3c !important; }
</style>
""", unsafe_allow_html=True)

# ==================== Google Sheets ====================
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_google_sheets_client():
    try:
        gcp_json_str = os.environ.get("GCP_SERVICE_ACCOUNT_JSON", "")
        if gcp_json_str:
            service_account_info = json.loads(gcp_json_str)
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info, scopes=SCOPES)
            service = build('sheets', 'v4', credentials=credentials)
            return service.spreadsheets()
        if hasattr(st, 'secrets') and "gcp_service_account" in st.secrets:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"], scopes=SCOPES)
            service = build('sheets', 'v4', credentials=credentials)
            return service.spreadsheets()
        return None
    except Exception as e:
        st.error(f"Google Sheets接続エラー: {str(e)}")
        return None

def get_spreadsheet_id():
    sid = os.environ.get("SPREADSHEET_ID", "")
    if sid:
        return sid
    try:
        return st.secrets.get("spreadsheet_id", "")
    except:
        return ""

def read_sheet(sheets_client, spreadsheet_id, sheet_name, has_header=True):
    try:
        result = sheets_client.values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:Z"
        ).execute()
        values = result.get('values', [])
        if not values:
            return pd.DataFrame()
        if has_header and len(values) > 0:
            headers = values[0]
            rows = values[1:]
            # 列数を揃える
            rows = [r + [''] * (len(headers) - len(r)) for r in rows]
            df = pd.DataFrame(rows, columns=headers)
        else:
            df = pd.DataFrame(values)
        return df
    except HttpError as e:
        if e.resp.status == 404:
            return pd.DataFrame()
        st.error(f"読み込みエラー ({sheet_name}): {str(e)}")
        return pd.DataFrame()

def write_sheet(sheets_client, spreadsheet_id, sheet_name, df, clear_first=True):
    try:
        values = [df.columns.tolist()] + df.fillna('').astype(str).values.tolist()
        if clear_first:
            sheets_client.values().clear(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A:Z"
            ).execute()
        body = {'values': values}
        sheets_client.values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption='RAW',
            body=body
        ).execute()
        return True
    except Exception as e:
        st.error(f"書き込みエラー ({sheet_name}): {str(e)}")
        return False

def append_to_sheet(sheets_client, spreadsheet_id, sheet_name, row_data):
    try:
        if isinstance(row_data, pd.DataFrame):
            values = row_data.fillna('').astype(str).values.tolist()
        elif isinstance(row_data, dict):
            values = [[str(v) for v in row_data.values()]]
        else:
            values = [row_data]
        body = {'values': values}
        sheets_client.values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:Z",
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        return True
    except Exception as e:
        st.error(f"追加エラー ({sheet_name}): {str(e)}")
        return False

def ensure_sheet_exists(sheets_client, spreadsheet_id, sheet_name):
    try:
        result = sheets_client.get(spreadsheetId=spreadsheet_id).execute()
        existing = [s['properties']['title'] for s in result.get('sheets', [])]
        if sheet_name not in existing:
            body = {'requests': [{'addSheet': {'properties': {'title': sheet_name}}}]}
            sheets_client.batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
    except Exception:
        pass

# ==================== v5 trade_reasons カラム定義 ====================
TRADE_REASONS_COLS = [
    'id',
    'ticker_code', 'stock_name',
    'trade_type',          # spot=現物 / margin=信用
    'entry_date', 'entry_price', 'quantity',
    'entry_reason_large', 'entry_reason_medium', 'entry_reason_small',
    'entry_memo',
    'stop_loss_type', 'stop_loss_price',
    'exit_date', 'exit_price',
    'exit_reason_large', 'exit_reason_medium', 'exit_reason_small',
    'exit_memo',
    'profit_loss', 'profit_loss_pct',
    'status',              # active=保有中 / closed=決済済み
    'created_at', 'updated_at'
]

def init_spreadsheet(sheets_client, spreadsheet_id):
    """必要なシートを初期化（active_trades / closed_trades は作らない）"""
    for sheet in ['trades', 'trade_reasons', 'reason_definitions', 'settings', 'manual_positions']:
        ensure_sheet_exists(sheets_client, spreadsheet_id, sheet)

    # settings 初期化
    settings_df = read_sheet(sheets_client, spreadsheet_id, 'settings')
    if len(settings_df) == 0:
        settings_df = pd.DataFrame({
            'id': [1],
            'total_capital': [1000000],
            'risk_per_trade_pct': [0.2],
            'updated_at': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        })
        write_sheet(sheets_client, spreadsheet_id, 'settings', settings_df)

    # trade_reasons ヘッダー初期化
    tr_df = read_sheet(sheets_client, spreadsheet_id, 'trade_reasons')
    if len(tr_df) == 0:
        write_sheet(sheets_client, spreadsheet_id, 'trade_reasons',
                    pd.DataFrame(columns=TRADE_REASONS_COLS))

    # reason_definitions 初期化
    reason_df = read_sheet(sheets_client, spreadsheet_id, 'reason_definitions')
    if len(reason_df) == 0:
        initial_reasons = [
            ('entry','large','','打診買い',1),
            ('entry','large','','追撃買い',1),
            ('entry','large','','ナンピン',1),
            ('entry','large','','ポジション調整',1),
            ('entry','medium','打診買い','順張り',1),
            ('entry','medium','打診買い','逆張り',1),
            ('entry','medium','打診買い','イベント',1),
            ('entry','medium','追撃買い','順張り',1),
            ('entry','medium','追撃買い','逆張り',1),
            ('entry','medium','追撃買い','イベント',1),
            ('entry','medium','ナンピン','逆張り',1),
            ('entry','medium','ポジション調整','順張り',1),
            ('entry','medium','ポジション調整','逆張り',1),
            ('entry','small','順張り','MAブレイク',1),
            ('entry','small','順張り','高値ブレイク',1),
            ('entry','small','順張り','短期MA反発',1),
            ('entry','small','逆張り','MA乖離率',1),
            ('entry','small','逆張り','二番底',1),
            ('entry','small','逆張り','窓埋め',1),
            ('entry','small','逆張り','直近安値',1),
            ('entry','small','逆張り','節目',1),
            ('entry','small','イベント','決算期待',1),
            ('entry','small','イベント','決算後急騰',1),
            ('entry','small','イベント','決算後暴落',1),
            ('entry','small','イベント','材料',1),
            ('entry','small','イベント','ニュース',1),
            ('stop_loss','small','','総資産の0.2%減',1),
            ('stop_loss','small','','買値-5%',1),
            ('stop_loss','small','','買値-10%',1),
            ('stop_loss','small','','直近安値',1),
            ('stop_loss','small','','節目',1),
            ('exit','large','','利確',1),
            ('exit','large','','損切り',1),
            ('exit','large','','調整',1),
            ('exit','medium','利確','目標達成',1),
            ('exit','medium','利確','利益確定',1),
            ('exit','medium','損切り','ルール損切り',1),
            ('exit','medium','損切り','判断損切り',1),
            ('exit','medium','調整','ポジション縮小',1),
            ('exit','small','目標達成','目標株価到達',1),
            ('exit','small','利益確定','高値圏での売り',1),
            ('exit','small','ルール損切り','逆指値',1),
            ('exit','small','ルール損切り','損切りライン到達',1),
            ('exit','small','判断損切り','シナリオ崩れ',1),
            ('exit','small','判断損切り','方向感喪失',1),
            ('exit','small','ポジション縮小','部分利確',1),
            ('exit','small','ポジション縮小','リスク管理',1),
        ]
        reason_df = pd.DataFrame(initial_reasons,
                                  columns=['reason_type','level','parent','name','is_active'])
        write_sheet(sheets_client, spreadsheet_id, 'reason_definitions', reason_df)

def create_spreadsheet_if_needed(sheets_client):
    spreadsheet_id = get_spreadsheet_id()
    if not spreadsheet_id:
        st.warning("スプレッドシートIDが設定されていません。新規作成します。")
        spreadsheet = {
            'properties': {'title': 'トレード分析データ'},
            'sheets': [{'properties': {'title': s}} for s in
                       ['trades', 'trade_reasons', 'reason_definitions', 'settings', 'manual_positions']]
        }
        try:
            result = sheets_client.create(body=spreadsheet).execute()
            new_id = result['spreadsheetId']
            st.success("スプレッドシート作成完了！")
            st.code(f'SPREADSHEET_ID="{new_id}"')
            return new_id
        except Exception as e:
            st.error(f"作成エラー: {str(e)}")
            return None
    return spreadsheet_id

# ==================== 設定 ====================
def load_settings(sheets_client, spreadsheet_id):
    df = read_sheet(sheets_client, spreadsheet_id, 'settings')
    if len(df) > 0:
        return {
            'total_capital': float(df.iloc[0]['total_capital']),
            'risk_per_trade_pct': float(df.iloc[0]['risk_per_trade_pct'])
        }
    return {'total_capital': 1000000, 'risk_per_trade_pct': 0.2}

def save_settings(sheets_client, spreadsheet_id, total_capital, risk_per_trade_pct):
    settings_df = pd.DataFrame({
        'id': [1],
        'total_capital': [int(total_capital)],
        'risk_per_trade_pct': [float(risk_per_trade_pct)],
        'updated_at': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
    })
    return write_sheet(sheets_client, spreadsheet_id, 'settings', settings_df)

# ==================== 理由マスタ ====================
def get_reason_definitions(sheets_client, spreadsheet_id):
    df = read_sheet(sheets_client, spreadsheet_id, 'reason_definitions')
    if len(df) == 0:
        return pd.DataFrame(columns=['reason_type','level','parent','name','is_active'])
    if 'is_active' in df.columns:
        df['is_active'] = df['is_active'].astype(str)
        df = df[df['is_active'] == '1'].reset_index(drop=True)
    return df

def get_large(df_defs, rtype):
    return df_defs[(df_defs['reason_type']==rtype)&(df_defs['level']=='large')]['name'].tolist()

def get_medium(df_defs, rtype, large):
    return df_defs[(df_defs['reason_type']==rtype)&(df_defs['level']=='medium')&(df_defs['parent']==large)]['name'].tolist()

def get_small(df_defs, rtype, medium):
    return df_defs[(df_defs['reason_type']==rtype)&(df_defs['level']=='small')&(df_defs['parent']==medium)]['name'].tolist()

def get_stoploss_items(df_defs):
    return df_defs[(df_defs['reason_type']=='stop_loss')&(df_defs['level']=='small')]['name'].tolist()

def format_reason(large, medium, small):
    parts = [x for x in [large, medium, small] if x and x not in ('', '（なし）', 'nan')]
    return ' / '.join(parts)

# ==================== trade_reasons CRUD (v5) ====================
def load_trade_reasons(sheets_client, spreadsheet_id):
    df = read_sheet(sheets_client, spreadsheet_id, 'trade_reasons')
    if len(df) == 0:
        return pd.DataFrame(columns=TRADE_REASONS_COLS)
    for col in TRADE_REASONS_COLS:
        if col not in df.columns:
            df[col] = ''
    return df

def upsert_trade_reason(sheets_client, spreadsheet_id, record: dict):
    """ticker_code + entry_date + trade_type をキーに UPSERT"""
    df = load_trade_reasons(sheets_client, spreadsheet_id)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    record['updated_at'] = now_str

    mask = (
        (df['ticker_code'].astype(str) == str(record.get('ticker_code', ''))) &
        (df['entry_date'].astype(str).str[:10] == str(record.get('entry_date', ''))[:10]) &
        (df['trade_type'].astype(str) == str(record.get('trade_type', '')))
    )
    if mask.any():
        for col, val in record.items():
            if col not in ('id', 'created_at'):
                df.loc[mask, col] = val
    else:
        if not record.get('id'):
            record['id'] = str(uuid.uuid4())[:8]
        if not record.get('created_at'):
            record['created_at'] = now_str
        # 欠損カラムを補完
        for col in TRADE_REASONS_COLS:
            if col not in record:
                record[col] = ''
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)

    return write_sheet(sheets_client, spreadsheet_id, 'trade_reasons', df)

def detect_and_close_positions(sheets_client, spreadsheet_id, df_trades):
    """CSVインポート後に呼ぶ。売付/売埋を検知して status=closed に更新"""
    df_tr = load_trade_reasons(sheets_client, spreadsheet_id)
    if len(df_tr) == 0:
        return
    active = df_tr[df_tr['status'].astype(str) == 'active']
    if len(active) == 0:
        return

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    changed = False
    for idx, row in active.iterrows():
        ticker = str(row['ticker_code'])
        trade_type = str(row['trade_type'])
        if trade_type == 'margin':
            sell_actions = ['売埋']
        else:
            sell_actions = ['売付']
        sells = df_trades[
            (df_trades['ticker_code'].astype(str) == ticker) &
            (df_trades['trade_action'].isin(sell_actions))
        ].sort_values('trade_date', ascending=False)
        if len(sells) > 0:
            latest_sell = sells.iloc[0]
            ep = float(row['entry_price']) if row['entry_price'] else 0.0
            xp = float(latest_sell['price']) if latest_sell['price'] else 0.0
            qty = float(row['quantity']) if row['quantity'] else 0.0
            pl = (xp - ep) * qty
            pl_pct = ((xp - ep) / ep * 100) if ep > 0 else 0.0
            df_tr.at[idx, 'exit_date'] = str(latest_sell['trade_date'])[:10]
            df_tr.at[idx, 'exit_price'] = str(xp)
            df_tr.at[idx, 'profit_loss'] = str(round(pl, 0))
            df_tr.at[idx, 'profit_loss_pct'] = str(round(pl_pct, 2))
            df_tr.at[idx, 'status'] = 'closed'
            df_tr.at[idx, 'updated_at'] = now_str
            changed = True

    if changed:
        write_sheet(sheets_client, spreadsheet_id, 'trade_reasons', df_tr)

# ==================== CSV パース ====================
def parse_jp_csv(df):
    numeric_columns = ['数量［株］', '単価［円］', '手数料［円］', '税金等［円］', '受渡金額［円］']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '').str.strip()
            df[col] = df[col].replace({'-': None, '': None, 'nan': None})
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    parsed = pd.DataFrame({
        'trade_date': pd.to_datetime(df['約定日'], format='%Y/%m/%d').dt.strftime('%Y-%m-%d'),
        'settlement_date': pd.to_datetime(df['受渡日'], format='%Y/%m/%d', errors='coerce').dt.strftime('%Y-%m-%d'),
        'market': '日本株',
        'ticker_code': df['銘柄コード'].astype(str).str.strip(),
        'stock_name': df['銘柄名'],
        'account_type': df['取引区分'],
        'trade_type': df['口座区分'],
        'trade_action': df['売買区分'],
        'quantity': pd.to_numeric(df['数量［株］'], errors='coerce').fillna(0).astype(int),
        'price': df['単価［円］'],
        'commission': df['手数料［円］'],
        'tax': df['税金等［円］'],
        'total_amount': df['受渡金額［円］'].abs(),
        'exchange_rate': '',
        'currency': 'JPY',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    return parsed

def parse_us_csv(df):
    numeric_columns = ['数量［株］', '単価［USドル］', '為替レート', '手数料［USドル］', '税金［USドル］', '受渡金額［円］']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '').str.strip()
            df[col] = df[col].replace({'-': None, '': None, 'nan': None})
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    parsed = pd.DataFrame({
        'trade_date': pd.to_datetime(df['約定日'], format='%Y/%m/%d').dt.strftime('%Y-%m-%d'),
        'settlement_date': pd.to_datetime(df['受渡日'], format='%Y/%m/%d', errors='coerce').dt.strftime('%Y-%m-%d'),
        'market': '米国株',
        'ticker_code': df['ティッカー'].astype(str).str.strip(),
        'stock_name': df['銘柄名'],
        'account_type': df['取引区分'],
        'trade_type': df['口座'],
        'trade_action': df['売買区分'],
        'quantity': df['数量［株］'].astype(int),
        'price': df['単価［USドル］'],
        'commission': df['手数料［USドル］'],
        'tax': df['税金［USドル］'],
        'total_amount': df['受渡金額［円］'].abs(),
        'exchange_rate': df['為替レート'],
        'currency': 'USD',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    return parsed

# ==================== ポジション計算 ====================
def load_all_trades(sheets_client, spreadsheet_id):
    df = read_sheet(sheets_client, spreadsheet_id, 'trades')
    if len(df) > 0:
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        for col in ['quantity', 'price', 'commission', 'tax', 'total_amount']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        if 'ticker_code' in df.columns:
            df['ticker_code'] = df['ticker_code'].astype(str).str.strip()
            def clean_ticker(t):
                try:
                    f = float(t)
                    if f == int(f):
                        return str(int(f))
                    return t
                except:
                    return t
            df['ticker_code'] = df['ticker_code'].apply(clean_ticker)
    return df

def calc_avg_price(rows_sorted, buy_actions, sell_action, kenin_sell=False):
    qty = 0.0
    avg = 0.0
    for _, row in rows_sorted.iterrows():
        action = str(row.get('trade_action', ''))
        acct   = str(row.get('account_type', ''))
        q = float(row['quantity']) if not pd.isna(row['quantity']) else 0.0
        p = float(row['price']) if not pd.isna(row['price']) else 0.0
        is_kenin = (acct == '現引')
        if action in buy_actions:
            total_cost = avg * qty + p * q
            qty += q
            avg = total_cost / qty if qty > 0 else 0.0
        elif is_kenin and not kenin_sell:
            effective_p = p if p > 0 else avg
            total_cost = avg * qty + effective_p * q
            qty += q
            avg = total_cost / qty if qty > 0 else 0.0
        elif action == sell_action or (is_kenin and kenin_sell):
            qty -= q
            if qty <= 0:
                qty = 0.0
                avg = 0.0
    return avg

def calculate_position_summary(df):
    if len(df) == 0:
        return pd.DataFrame()
    df = df[df['trade_action'] != '売買区分'].copy()
    df = df[df['ticker_code'] != '銘柄コード']
    df = df[df['ticker_code'].notna() & (df['ticker_code'] != '')]
    df['quantity'] = pd.to_numeric(df['quantity'].astype(str).str.replace(',','').str.strip(), errors='coerce').fillna(0)
    df['price']    = pd.to_numeric(df['price'].astype(str).str.replace(',','').str.strip(), errors='coerce').fillna(0)
    df = df.sort_values('trade_date').reset_index(drop=True)
    summary = []
    for ticker in df['ticker_code'].unique():
        r = df[df['ticker_code'] == ticker]
        name_rows  = r[r['stock_name'].notna() & (r['stock_name'] != '')]
        stock_name = name_rows.iloc[0]['stock_name'] if len(name_rows) > 0 else ticker
        market     = name_rows.iloc[0]['market']     if len(name_rows) > 0 else '日本株'
        kenin_rows = r[(r['account_type'] == '現引') & (~r['trade_action'].isin(['買建', '売埋']))]
        kenin_qty  = kenin_rows['quantity'].sum()
        if market == '米国株':
            buy_qty   = r[r['trade_action'] == '買付']['quantity'].sum()
            sell_qty  = r[r['trade_action'] == '売付']['quantity'].sum()
            nyuko_qty = 0
        else:
            spot_rows = r[r['account_type'] == '現物']
            buy_qty   = spot_rows[spot_rows['trade_action'] == '買付']['quantity'].sum()
            sell_qty  = spot_rows[spot_rows['trade_action'] == '売付']['quantity'].sum()
            nyuko_qty = r[r['trade_action'] == '入庫']['quantity'].sum()
        spot_qty   = buy_qty + nyuko_qty + kenin_qty - sell_qty
        mbuy_qty   = r[r['trade_action'] == '買建']['quantity'].sum()
        msell_qty  = r[r['trade_action'] == '売埋']['quantity'].sum()
        margin_qty = mbuy_qty - msell_qty - kenin_qty
        if spot_qty > 0:
            if market == '米国株':
                spot_r = r[r['trade_action'].isin(['買付','売付']) |
                           ((r['account_type'] == '現引') & (~r['trade_action'].isin(['買建','売埋'])))].copy()
            else:
                spot_r = r[((r['account_type'] == '現物') & r['trade_action'].isin(['買付','売付'])) |
                           (r['trade_action'] == '入庫') |
                           ((r['account_type'] == '現引') & (~r['trade_action'].isin(['買建','売埋'])))].copy()
            spot_avg = calc_avg_price(spot_r.sort_values('trade_date'),
                                      buy_actions=['買付','入庫'], sell_action='売付', kenin_sell=False)
            summary.append({'ticker_code': ticker, 'stock_name': stock_name, 'market': market,
                            'trade_type': 'spot', 'quantity': int(round(spot_qty)),
                            'avg_price': round(spot_avg, 2), 'total_cost': round(spot_avg * spot_qty, 0)})
        if margin_qty > 0:
            margin_r = r[r['trade_action'].isin(['買建','売埋']) |
                         ((r['account_type'] == '現引') & (~r['trade_action'].isin(['買建','売埋'])))].copy()
            margin_avg = calc_avg_price(margin_r.sort_values('trade_date'),
                                        buy_actions=['買建'], sell_action='売埋', kenin_sell=True)
            summary.append({'ticker_code': ticker, 'stock_name': stock_name, 'market': market,
                            'trade_type': 'margin', 'quantity': int(round(margin_qty)),
                            'avg_price': round(margin_avg, 2), 'total_cost': round(margin_avg * margin_qty, 0)})
    result = pd.DataFrame(summary)
    if len(result) > 0:
        result = result.sort_values('ticker_code').reset_index(drop=True)
    return result

def apply_manual_positions(df_positions, manual_pos_df):
    if len(df_positions) == 0 or len(manual_pos_df) == 0:
        return df_positions
    manual_pos_df = manual_pos_df.copy()
    manual_pos_df['quantity']  = pd.to_numeric(manual_pos_df['quantity'], errors='coerce').fillna(0)
    manual_pos_df['avg_price'] = pd.to_numeric(manual_pos_df['avg_price'], errors='coerce').fillna(0)
    for _, mrow in manual_pos_df.iterrows():
        mask = ((df_positions['ticker_code'] == mrow['ticker_code']) &
                (df_positions['trade_type'] == mrow['trade_type']))
        if mask.any():
            if float(mrow['quantity']) <= 0:
                df_positions = df_positions[~mask]
            else:
                df_positions.loc[mask, 'quantity']   = int(mrow['quantity'])
                df_positions.loc[mask, 'avg_price']  = float(mrow['avg_price'])
                df_positions.loc[mask, 'total_cost'] = round(float(mrow['avg_price']) * float(mrow['quantity']), 0)
    return df_positions.reset_index(drop=True)

# ==================== 株価取得 ====================
def get_current_price(ticker_code, market):
    if not YFINANCE_AVAILABLE:
        return None
    try:
        symbol = f"{ticker_code}.T" if market == '日本株' else str(ticker_code)
        t = yf.Ticker(symbol)
        hist = t.history(period='2d')
        return float(hist['Close'].iloc[-1]) if len(hist) > 0 else None
    except Exception:
        return None

# ==================== メイン ====================
sheets_client = get_google_sheets_client()
if sheets_client:
    spreadsheet_id = create_spreadsheet_if_needed(sheets_client)
    if spreadsheet_id:
        init_spreadsheet(sheets_client, spreadsheet_id)
        st.markdown("### 📊 トレード分析＆資金管理")

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📥 データ", "🔔 催促", "📊 分析", "💰 資金", "📦 ポジション", "⚙️ 設定"
        ])

        # ==================== タブ1: データ管理 ====================
        with tab1:
            st.subheader("📥 CSVインポート")
            with st.expander("📖 使い方を見る"):
                st.markdown(
                    "1. 楽天証券 → 取引履歴 → **全期間** でCSVダウンロード\n"
                    "2. 日本株・米国株の両方をアップロード\n"
                    "3. 「全件差し替えインポート」を押す\n\n"
                    "⚠️ **全期間**を選ばないと平均取得単価がずれます"
                )
            last_import_date = ""
            df_trades_check = read_sheet(sheets_client, spreadsheet_id, 'trades')
            if len(df_trades_check) > 0 and 'created_at' in df_trades_check.columns:
                last_dates = df_trades_check['created_at'].dropna()
                if len(last_dates) > 0:
                    last_import_date = last_dates.iloc[-1]

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**① 日本株CSV**")
                jp_file = st.file_uploader("日本株CSVをアップロード", type=['csv'], key='jp_csv')
                if jp_file:
                    df_jp = pd.read_csv(jp_file, encoding='cp932')
                    st.success(f"読込: {len(df_jp)}件 ✅")
            with col2:
                st.markdown("**② 米国株CSV**")
                us_file = st.file_uploader("米国株CSVをアップロード", type=['csv'], key='us_csv')
                if us_file:
                    df_us = pd.read_csv(us_file, encoding='cp932')
                    st.success(f"読込: {len(df_us)}件 ✅")

            if jp_file or us_file:
                st.warning("⚠️ 既存の取引データがすべて上書きされます")
                if st.button("🔄 全件差し替えインポート", use_container_width=True, type="primary"):
                    with st.spinner('インポート中...'):
                        parts = []
                        if jp_file:
                            parts.append(parse_jp_csv(df_jp))
                        if us_file:
                            parts.append(parse_us_csv(df_us))
                        combined = pd.concat(parts, ignore_index=True) if len(parts) > 1 else parts[0]
                        if write_sheet(sheets_client, spreadsheet_id, 'trades', combined, clear_first=True):
                            # 決済検知
                            detect_and_close_positions(sheets_client, spreadsheet_id, combined)
                            st.success(f"✅ {len(combined)}件をインポートしました")
                            st.rerun()
            else:
                st.button("🔄 全件差し替えインポート", use_container_width=True, type="primary", disabled=True)

            if last_import_date:
                st.markdown(f'<div class="import-date">最終インポート: {last_import_date}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="import-date">最終インポート: なし</div>', unsafe_allow_html=True)

            st.divider()
            with st.expander("➕ 差分追加インポート（上級者向け・重複注意）"):
                st.warning("⚠️ 同じ期間のCSVを2回追加すると数量が2倍になります。")
                col1, col2 = st.columns(2)
                with col1:
                    jp_add = st.file_uploader("日本株CSV（追加用）", type=['csv'], key='jp_add')
                    if jp_add:
                        df_jp_add = pd.read_csv(jp_add, encoding='cp932')
                        st.info(f"読込: {len(df_jp_add)}件")
                        if st.button("日本株を追加", key='add_jp'):
                            with st.spinner('追加中...'):
                                parsed = parse_jp_csv(df_jp_add)
                                existing = read_sheet(sheets_client, spreadsheet_id, 'trades')
                                combined = pd.concat([existing, parsed], ignore_index=True) if len(existing) > 0 else parsed
                                if write_sheet(sheets_client, spreadsheet_id, 'trades', combined):
                                    detect_and_close_positions(sheets_client, spreadsheet_id, combined)
                                    st.success(f"✅ {len(parsed)}件を追加しました")
                                    st.rerun()
                with col2:
                    us_add = st.file_uploader("米国株CSV（追加用）", type=['csv'], key='us_add')
                    if us_add:
                        df_us_add = pd.read_csv(us_add, encoding='cp932')
                        st.info(f"読込: {len(df_us_add)}件")
                        if st.button("米国株を追加", key='add_us'):
                            with st.spinner('追加中...'):
                                parsed = parse_us_csv(df_us_add)
                                existing = read_sheet(sheets_client, spreadsheet_id, 'trades')
                                combined = pd.concat([existing, parsed], ignore_index=True) if len(existing) > 0 else parsed
                                if write_sheet(sheets_client, spreadsheet_id, 'trades', combined):
                                    detect_and_close_positions(sheets_client, spreadsheet_id, combined)
                                    st.success(f"✅ {len(parsed)}件を追加しました")
                                    st.rerun()

            st.divider()
            st.subheader("📋 全トレード履歴")
            df_all = load_all_trades(sheets_client, spreadsheet_id)
            if len(df_all) > 0:
                st.caption(f"総件数: {len(df_all)}件")
                col1, col2, col3 = st.columns(3)
                with col1:
                    market_filter = st.selectbox("市場", ["全て"] + list(df_all['market'].unique()))
                with col2:
                    action_filter = st.selectbox("売買", ["全て", "買付", "売付"])
                with col3:
                    year_filter = st.selectbox("年", ["全て"] + sorted(df_all['trade_date'].dt.year.unique().tolist(), reverse=True))
                df_filtered = df_all.copy()
                if market_filter != "全て":
                    df_filtered = df_filtered[df_filtered['market'] == market_filter]
                if action_filter != "全て":
                    df_filtered = df_filtered[df_filtered['trade_action'] == action_filter]
                if year_filter != "全て":
                    df_filtered = df_filtered[df_filtered['trade_date'].dt.year == year_filter]
                df_filtered = df_filtered.sort_values('trade_date', ascending=False)
                display_cols = ['trade_date','market','ticker_code','stock_name','trade_action','quantity','price','total_amount']
                st.dataframe(df_filtered[display_cols].rename(columns={
                    'trade_date':'約定日','market':'市場','ticker_code':'コード','stock_name':'銘柄名',
                    'trade_action':'売買','quantity':'数量','price':'単価','total_amount':'金額'
                }).reset_index(drop=True), use_container_width=True, height=400)
            else:
                st.info("データがありません。CSVファイルをインポートしてください。")

        # ==================== タブ2: 🔔 催促（v5新設計） ====================
        with tab2:
            # データ読み込み
            df_all_t2       = load_all_trades(sheets_client, spreadsheet_id)
            df_positions_t2 = calculate_position_summary(df_all_t2)
            manual_pos_t2   = read_sheet(sheets_client, spreadsheet_id, 'manual_positions')
            df_positions_t2 = apply_manual_positions(df_positions_t2, manual_pos_t2)
            df_tr_t2        = load_trade_reasons(sheets_client, spreadsheet_id)
            df_defs         = get_reason_definitions(sheets_client, spreadsheet_id)
            sl_items        = get_stoploss_items(df_defs)

            # --- サマリーカード ---
            active_tr  = df_tr_t2[df_tr_t2['status'].astype(str) == 'active'] if len(df_tr_t2) > 0 else pd.DataFrame()
            filled_cnt = len(active_tr[active_tr['entry_reason_large'].astype(str).str.strip() != '']) if len(active_tr) > 0 else 0
            total_pos  = len(df_positions_t2)
            pending_entry_cnt = total_pos - filled_cnt

            # 決済理由未入力数
            closed_tr  = df_tr_t2[df_tr_t2['status'].astype(str) == 'closed'] if len(df_tr_t2) > 0 else pd.DataFrame()
            exit_pending_cnt = len(closed_tr[closed_tr['exit_reason_large'].astype(str).str.strip() == '']) if len(closed_tr) > 0 else 0

            # 株価キャッシュ
            col_price_btn, col_price_info = st.columns([1, 3])
            with col_price_btn:
                fetch_prices = st.button("📡 株価更新", use_container_width=True, key="t2_fetch")
            with col_price_info:
                cache_time = st.session_state.get('price_cache_time')
                if not YFINANCE_AVAILABLE:
                    st.caption("⚠️ yfinanceが未インストール（株価は非表示）")
                else:
                    st.caption(f"株価は15分遅延　{'取得時刻: ' + cache_time if cache_time else ''}")

            if fetch_prices and YFINANCE_AVAILABLE and len(df_positions_t2) > 0:
                with st.spinner('株価取得中...'):
                    cache = {}
                    for _, pos_row in df_positions_t2.iterrows():
                        key = pos_row['ticker_code']
                        if key not in cache:
                            cache[key] = get_current_price(pos_row['ticker_code'], pos_row['market'])
                    st.session_state['price_cache'] = cache
                    st.session_state['price_cache_time'] = datetime.now().strftime('%H:%M')
                st.rerun()

            price_cache = st.session_state.get('price_cache', {})

            # 含み損益合計
            total_pl = 0.0
            total_cost_sum = 0.0
            for _, pos in df_positions_t2.iterrows():
                cp  = price_cache.get(pos['ticker_code'])
                avg = float(pos['avg_price'])
                qty = int(pos['quantity'])
                if cp and avg > 0:
                    total_pl += (cp - avg) * qty
                    total_cost_sum += avg * qty
            pl_pct_total = (total_pl / total_cost_sum * 100) if total_cost_sum > 0 else 0.0

            # サマリーカード表示
            pl_cls = "s-val-pos" if total_pl >= 0 else "s-val-neg"
            pl_sign = "+" if total_pl >= 0 else ""
            st.markdown(f"""
<div class="summary-grid">
  <div class="summary-card hl">
    <div class="s-val {pl_cls}">{pl_sign}{pl_pct_total:.1f}%</div>
    <div class="s-lbl">含み損益</div>
  </div>
  <div class="summary-card">
    <div class="s-val">{total_pos}</div>
    <div class="s-lbl">保有銘柄</div>
  </div>
  <div class="summary-card">
    <div class="s-val s-val-yellow">{pending_entry_cnt}</div>
    <div class="s-lbl">未入力</div>
  </div>
</div>
""", unsafe_allow_html=True)

            # 決済理由未入力バッジ
            if exit_pending_cnt > 0:
                st.markdown(f"""
<div class="notif-bar">
  <span class="notif-text">⚠️ 決済理由が未入力の取引</span>
  <span class="notif-count">{exit_pending_cnt}件</span>
</div>
""", unsafe_allow_html=True)
                if st.button("決済理由を入力する", key="show_exit_form", use_container_width=False):
                    st.session_state['show_exit_list'] = not st.session_state.get('show_exit_list', False)

                if st.session_state.get('show_exit_list', False) and len(closed_tr) > 0:
                    pending_closed = closed_tr[closed_tr['exit_reason_large'].astype(str).str.strip() == '']
                    for _, crow in pending_closed.iterrows():
                        ep = float(crow['entry_price']) if crow['entry_price'] else 0.0
                        xp = float(crow['exit_price']) if crow['exit_price'] else 0.0
                        pl_disp = float(crow['profit_loss']) if crow['profit_loss'] else (xp - ep) * float(crow['quantity'] if crow['quantity'] else 0)
                        pl_col = "color:#3d9960" if pl_disp >= 0 else "color:#c0392b"
                        st.markdown(f"""
<div class="entered-card" style="border-left-color:#d4a017;">
  <div class="entered-ticker">{crow['ticker_code']} {crow['stock_name']}</div>
  <div class="entered-sub">決済日: {str(crow['exit_date'])[:10]}　損益: <span style="{pl_col}">¥{pl_disp:,.0f}</span></div>
</div>""", unsafe_allow_html=True)
                        with st.form(key=f"exit_form_{crow['id']}_{crow['ticker_code']}"):
                            st.markdown('<div class="form-title">✏ 決済理由を入力</div>', unsafe_allow_html=True)
                            xl_items = get_large(df_defs, 'exit')
                            x_large  = st.selectbox("大項目", xl_items if xl_items else [""], key=f"ex_xl_{crow['id']}")
                            xm_items = get_medium(df_defs, 'exit', x_large)
                            x_medium = st.selectbox("中項目", xm_items if xm_items else ["（なし）"], key=f"ex_xm_{crow['id']}")
                            xs_items = get_small(df_defs, 'exit', x_medium)
                            x_small  = st.selectbox("小項目", xs_items if xs_items else ["（なし）"], key=f"ex_xs_{crow['id']}")
                            ex_memo  = st.text_input("決済メモ（任意）", key=f"ex_memo_{crow['id']}")
                            submitted = st.form_submit_button("💾 保存", use_container_width=True)
                            if submitted:
                                record = dict(crow)
                                record['exit_reason_large']  = x_large
                                record['exit_reason_medium'] = x_medium if x_medium != "（なし）" else ""
                                record['exit_reason_small']  = x_small if x_small != "（なし）" else ""
                                record['exit_memo'] = ex_memo
                                upsert_trade_reason(sheets_client, spreadsheet_id, record)
                                st.success("✅ 保存しました")
                                st.rerun()

            st.divider()

            # --- ① 保有中ポジション一覧テーブル ---
            st.markdown('<div class="section-label">保有中ポジション</div>', unsafe_allow_html=True)

            if total_pos == 0:
                st.info("保有ポジションはありません")
            else:
                # 入力済みキーセット
                filled_keys = set()
                if len(active_tr) > 0:
                    for _, rrow in active_tr.iterrows():
                        if str(rrow.get('entry_reason_large', '')).strip():
                            filled_keys.add(f"{rrow['ticker_code']}_{rrow['trade_type']}")

                # テーブルヘッダー
                st.markdown("""
<div class="pos-table-header">
  <span>銘柄</span>
  <span style="text-align:right">数量</span>
  <span style="text-align:right">損益</span>
  <span style="text-align:right">状況</span>
</div>""", unsafe_allow_html=True)

                selected_key = st.session_state.get('selected_pos_key', None)

                for _, pos in df_positions_t2.iterrows():
                    key = f"{pos['ticker_code']}_{pos['trade_type']}"
                    cp  = price_cache.get(pos['ticker_code'])
                    avg = float(pos['avg_price'])
                    qty = int(pos['quantity'])
                    is_filled = key in filled_keys
                    is_jp     = pos['market'] == '日本株'

                    if cp and avg > 0:
                        pl_pct = (cp - avg) / avg * 100
                        pl_str = f"{pl_pct:+.1f}%"
                        pl_cls = "pnl-pos" if pl_pct >= 0 else "pnl-neg"
                    else:
                        pl_str = "—"
                        pl_cls = "num-cell"

                    badge = '<span class="badge-done">入力済</span>' if is_filled else '<span class="badge-pending">未入力</span>'
                    bar_cls = "left-bar-green" if is_filled else "left-bar-yellow"
                    sel_cls = "selected" if selected_key == key else ""

                    st.markdown(f"""
<div class="pos-row {sel_cls} {bar_cls}">
  <div>
    <div class="ticker-name">{pos['ticker_code']}</div>
    <div class="stock-sub">{pos['stock_name']}{'（信用）' if pos['trade_type']=='margin' else ''}</div>
  </div>
  <div class="num-cell">{qty}</div>
  <div class="{pl_cls}">{pl_str}</div>
  <div style="text-align:right">{badge}</div>
</div>""", unsafe_allow_html=True)

                    # 行ごとの選択ボタン（非表示感にする）
                    if st.button(f"{'▼ 入力中' if selected_key == key else '✏ 入力'}", key=f"sel_{key}", use_container_width=True):
                        if selected_key == key:
                            st.session_state['selected_pos_key'] = None
                        else:
                            st.session_state['selected_pos_key'] = key
                        st.rerun()

                    # ② インラインフォーム（選択行の直下に展開）
                    if selected_key == key:
                        existing_rec = pd.DataFrame()
                        if len(active_tr) > 0:
                            mask_ex = (
                                (active_tr['ticker_code'].astype(str) == str(pos['ticker_code'])) &
                                (active_tr['trade_type'].astype(str) == str(pos['trade_type']))
                            )
                            if mask_ex.any():
                                existing_rec = active_tr[mask_ex].iloc[0]

                        # 既存値のデフォルト
                        def_large  = str(existing_rec.get('entry_reason_large', ''))  if len(existing_rec) > 0 else ''
                        def_medium = str(existing_rec.get('entry_reason_medium', '')) if len(existing_rec) > 0 else ''
                        def_small  = str(existing_rec.get('entry_reason_small', ''))  if len(existing_rec) > 0 else ''
                        def_memo   = str(existing_rec.get('entry_memo', ''))          if len(existing_rec) > 0 else ''
                        def_sl_type= str(existing_rec.get('stop_loss_type', ''))      if len(existing_rec) > 0 else ''
                        def_sl_p   = float(existing_rec['stop_loss_price']) if len(existing_rec) > 0 and existing_rec.get('stop_loss_price') and str(existing_rec.get('stop_loss_price','')) not in ('','nan') else 0.0

                        st.markdown(f'<div class="form-panel"><div class="form-title">✏ {pos["ticker_code"]} {pos["stock_name"]} — エントリー記録</div></div>', unsafe_allow_html=True)

                        with st.form(key=f"entry_form_{key}"):
                            large_items = get_large(df_defs, 'entry')
                            def_large_idx = large_items.index(def_large) if def_large in large_items else 0
                            large_sel = st.selectbox("エントリー理由（大）", large_items if large_items else [""], index=def_large_idx, key=f"f_large_{key}")
                            col_m, col_s = st.columns(2)
                            with col_m:
                                medium_items = get_medium(df_defs, 'entry', large_sel)
                                def_medium_idx = medium_items.index(def_medium) if def_medium in medium_items else 0
                                medium_sel = st.selectbox("理由（中）", medium_items if medium_items else ["（なし）"], index=def_medium_idx, key=f"f_med_{key}")
                            with col_s:
                                small_items = get_small(df_defs, 'entry', medium_sel) if medium_sel and medium_sel != "（なし）" else []
                                def_small_idx = small_items.index(def_small) if def_small in small_items else 0
                                small_sel = st.selectbox("理由（小）", small_items if small_items else ["（なし）"], index=def_small_idx, key=f"f_sml_{key}")
                            col_sl1, col_sl2 = st.columns(2)
                            with col_sl1:
                                sl_opts = ["（選択）"] + sl_items
                                def_sl_idx = sl_opts.index(def_sl_type) if def_sl_type in sl_opts else 0
                                sl_type = st.selectbox("損切り根拠", sl_opts, index=def_sl_idx, key=f"f_sltype_{key}")
                            with col_sl2:
                                sl_price = st.number_input("損切り価格", min_value=0.0, value=def_sl_p, step=1.0, format="%.1f", key=f"f_slp_{key}")
                            entry_memo = st.text_input("メモ（任意）", value=def_memo, key=f"f_memo_{key}")

                            col_save, col_cancel = st.columns(2)
                            with col_save:
                                submitted = st.form_submit_button("💾 保存する", use_container_width=True)
                            with col_cancel:
                                cancelled = st.form_submit_button("キャンセル", use_container_width=True)

                            if submitted:
                                if sl_price <= 0:
                                    st.error("損切り価格を入力してください")
                                else:
                                    # entry_date と entry_price を trades から取得
                                    entry_date_val = ''
                                    entry_price_val = avg
                                    if len(df_all_t2) > 0:
                                        buy_acts = ['買建'] if pos['trade_type'] == 'margin' else ['買付', '入庫']
                                        t_rows = df_all_t2[
                                            (df_all_t2['ticker_code'].astype(str) == str(pos['ticker_code'])) &
                                            (df_all_t2['trade_action'].isin(buy_acts))
                                        ].sort_values('trade_date')
                                        if len(t_rows) > 0:
                                            entry_date_val = str(t_rows.iloc[0]['trade_date'])[:10]

                                    record = {
                                        'ticker_code': str(pos['ticker_code']),
                                        'stock_name': str(pos['stock_name']),
                                        'trade_type': str(pos['trade_type']),
                                        'entry_date': entry_date_val,
                                        'entry_price': str(avg),
                                        'quantity': str(qty),
                                        'entry_reason_large': large_sel,
                                        'entry_reason_medium': medium_sel if medium_sel != "（なし）" else "",
                                        'entry_reason_small': small_sel if small_sel != "（なし）" else "",
                                        'entry_memo': entry_memo,
                                        'stop_loss_type': sl_type if sl_type != "（選択）" else "",
                                        'stop_loss_price': str(sl_price),
                                        'status': 'active',
                                    }
                                    upsert_trade_reason(sheets_client, spreadsheet_id, record)
                                    st.session_state['selected_pos_key'] = None
                                    st.success("✅ 保存しました")
                                    st.rerun()

                            if cancelled:
                                st.session_state['selected_pos_key'] = None
                                st.rerun()

                st.divider()

                # ③ 入力済みポジション詳細セクション
                filled_records = active_tr[active_tr['entry_reason_large'].astype(str).str.strip() != ''] if len(active_tr) > 0 else pd.DataFrame()
                if len(filled_records) > 0:
                    st.markdown('<div class="section-label">入力済みポジション詳細</div>', unsafe_allow_html=True)
                    for _, rec in filled_records.iterrows():
                        tt_label = "信用" if str(rec['trade_type']) == 'margin' else "現物"
                        sl_p = str(rec.get('stop_loss_price',''))
                        sl_disp = f"¥{float(sl_p):,.0f}" if sl_p and sl_p not in ('','nan') else "—"
                        st.markdown(f"""
<div class="entered-card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div class="entered-ticker">{rec['ticker_code']} {rec['stock_name']}</div>
      <div class="entered-sub">{tt_label} / {rec['quantity']}株 / 取得 ¥{float(rec['entry_price']):,.0f}</div>
    </div>
    <span class="badge-done">入力済</span>
  </div>
  <div class="detail-grid">
    <div><div class="d-label">理由（大）</div><div class="d-val">{rec.get('entry_reason_large','—')}</div></div>
    <div><div class="d-label">理由（中）</div><div class="d-val">{rec.get('entry_reason_medium','—') or '—'}</div></div>
    <div><div class="d-label">理由（小）</div><div class="d-val">{rec.get('entry_reason_small','—') or '—'}</div></div>
    <div><div class="d-label">損切り価格</div><div class="d-val d-val-green">{sl_disp}</div></div>
  </div>
</div>""", unsafe_allow_html=True)

        # ==================== タブ3: 分析（trade_reasons 単一参照） ====================
        with tab3:
            st.subheader("📊 トレード分析")
            df_tr_analysis = load_trade_reasons(sheets_client, spreadsheet_id)

            closed_analysis = df_tr_analysis[df_tr_analysis['status'].astype(str) == 'closed'].copy() if len(df_tr_analysis) > 0 else pd.DataFrame()

            if len(closed_analysis) > 0:
                for col in ['entry_price', 'exit_price', 'profit_loss', 'profit_loss_pct', 'quantity']:
                    closed_analysis[col] = pd.to_numeric(closed_analysis[col], errors='coerce')
                closed_analysis['entry_date'] = pd.to_datetime(closed_analysis['entry_date'], errors='coerce')
                closed_analysis['exit_date']  = pd.to_datetime(closed_analysis['exit_date'],  errors='coerce')
                closed_analysis['hold_days']  = (closed_analysis['exit_date'] - closed_analysis['entry_date']).dt.days

                # --- パフォーマンスサマリー ---
                st.markdown('<div class="section-label">パフォーマンス</div>', unsafe_allow_html=True)
                total_trades   = len(closed_analysis)
                winning_trades = len(closed_analysis[closed_analysis['profit_loss'] > 0])
                losing_trades  = len(closed_analysis[closed_analysis['profit_loss'] < 0])
                win_rate       = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                total_pl_sum   = closed_analysis['profit_loss'].sum()
                avg_win  = closed_analysis[closed_analysis['profit_loss'] > 0]['profit_loss'].mean() if winning_trades > 0 else 0
                avg_loss = abs(closed_analysis[closed_analysis['profit_loss'] < 0]['profit_loss'].mean()) if losing_trades > 0 else 1
                pf       = avg_win / avg_loss if avg_loss > 0 else 0

                # 統計カードをグリッドで表示
                pl_cls2 = "s-val-pos" if total_pl_sum >= 0 else "s-val-neg"
                st.markdown(f"""
<div class="summary-grid" style="grid-template-columns:1fr 1fr 1fr;">
  <div class="summary-card hl">
    <div class="s-val {pl_cls2}">¥{total_pl_sum:,.0f}</div>
    <div class="s-lbl">累積損益</div>
  </div>
  <div class="summary-card">
    <div class="s-val">{win_rate:.1f}%</div>
    <div class="s-lbl">勝率</div>
  </div>
  <div class="summary-card">
    <div class="s-val">{pf:.2f}</div>
    <div class="s-lbl">PF</div>
  </div>
</div>
<div class="summary-grid" style="grid-template-columns:1fr 1fr 1fr;margin-top:0;">
  <div class="summary-card">
    <div class="s-val">{total_trades}</div>
    <div class="s-lbl">総トレード数</div>
  </div>
  <div class="summary-card">
    <div class="s-val s-val-pos">¥{closed_analysis['profit_loss'].max():,.0f}</div>
    <div class="s-lbl">最大利益</div>
  </div>
  <div class="summary-card">
    <div class="s-val s-val-neg">¥{closed_analysis['profit_loss'].min():,.0f}</div>
    <div class="s-lbl">最大損失</div>
  </div>
</div>
""", unsafe_allow_html=True)

                st.divider()

                # 累積損益グラフ
                col1, col2 = st.columns(2)
                with col1:
                    df_cs = closed_analysis.sort_values('exit_date')
                    df_cs['cumulative_pl'] = df_cs['profit_loss'].cumsum()
                    fig = px.line(df_cs, x='exit_date', y='cumulative_pl',
                                  title='累積損益推移',
                                  labels={'exit_date': '決済日', 'cumulative_pl': '累積損益（円）'},
                                  color_discrete_sequence=['#3d9960'])
                    fig.update_layout(height=280, paper_bgcolor='#1c1c1c', plot_bgcolor='#1c1c1c',
                                     font_color='#f7f7f5', title_font_size=12)
                    fig.update_xaxes(gridcolor='#2a2a2a')
                    fig.update_yaxes(gridcolor='#2a2a2a')
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    wl_data = pd.DataFrame({'結果': ['勝ち', '負け'], '件数': [winning_trades, losing_trades]})
                    fig = px.pie(wl_data, values='件数', names='結果', title='勝敗分布',
                                 color='結果',
                                 color_discrete_map={'勝ち': '#3d9960', '負け': '#c0392b'})
                    fig.update_layout(height=280, paper_bgcolor='#1c1c1c', font_color='#f7f7f5', title_font_size=12)
                    st.plotly_chart(fig, use_container_width=True)

                st.divider()

                # エントリー理由別分析
                st.markdown('<div class="section-label">エントリー理由別 勝率</div>', unsafe_allow_html=True)
                valid_reason = closed_analysis[closed_analysis['entry_reason_large'].astype(str).str.strip() != ''].copy()
                if len(valid_reason) > 0:
                    valid_reason['reason_full'] = valid_reason.apply(
                        lambda r: format_reason(
                            str(r.get('entry_reason_large', '')),
                            str(r.get('entry_reason_medium', '')),
                            str(r.get('entry_reason_small', ''))
                        ), axis=1)
                    rstats = valid_reason.groupby('reason_full').agg(
                        トレード数=('profit_loss', 'count'),
                        勝率=('profit_loss', lambda x: round((x > 0).mean() * 100, 1)),
                        平均損益=('profit_loss', lambda x: round(x.mean(), 0)),
                        合計損益=('profit_loss', lambda x: round(x.sum(), 0))
                    ).sort_values('合計損益', ascending=False)
                    st.dataframe(rstats, use_container_width=True)

                st.divider()

                # 銘柄別分析
                st.markdown('<div class="section-label">銘柄別分析</div>', unsafe_allow_html=True)
                ts = closed_analysis.groupby('ticker_code').agg(
                    {'profit_loss': ['sum', 'mean', 'count'], 'profit_loss_pct': 'mean'}
                ).round(2)
                ts.columns = ['総損益', '平均損益', 'トレード数', '平均利益率%']
                st.dataframe(ts.sort_values('総損益', ascending=False), use_container_width=True)

                st.divider()

                # トレード履歴
                st.markdown('<div class="section-label">トレード履歴</div>', unsafe_allow_html=True)
                col1, col2 = st.columns(2)
                with col1:
                    date_from = st.date_input("開始日", value=closed_analysis['exit_date'].min())
                with col2:
                    date_to = st.date_input("終了日", value=closed_analysis['exit_date'].max())
                df_fc = closed_analysis[
                    (closed_analysis['exit_date'] >= pd.Timestamp(date_from)) &
                    (closed_analysis['exit_date'] <= pd.Timestamp(date_to))
                ]
                dcols = ['exit_date', 'ticker_code', 'stock_name', 'entry_price', 'exit_price',
                         'quantity', 'profit_loss', 'profit_loss_pct',
                         'entry_reason_large', 'exit_reason_large']
                dcols_exist = [c for c in dcols if c in df_fc.columns]
                st.dataframe(df_fc[dcols_exist].rename(columns={
                    'exit_date': '決済日', 'ticker_code': 'コード', 'stock_name': '銘柄名',
                    'entry_price': 'IN価格', 'exit_price': 'OUT価格', 'quantity': '数量',
                    'profit_loss': '損益', 'profit_loss_pct': '損益率%',
                    'entry_reason_large': 'IN根拠(大)', 'exit_reason_large': 'OUT根拠(大)'
                }), use_container_width=True, height=400)

                # 月別損益
                st.divider()
                st.markdown('<div class="section-label">月別損益</div>', unsafe_allow_html=True)
                if len(closed_analysis) > 0:
                    monthly = closed_analysis.copy()
                    monthly['month'] = monthly['exit_date'].dt.to_period('M').astype(str)
                    monthly_stats = monthly.groupby('month').agg(
                        損益合計=('profit_loss', 'sum'),
                        トレード数=('profit_loss', 'count')
                    ).reset_index()
                    monthly_stats['色'] = monthly_stats['損益合計'].apply(lambda x: '#3d9960' if x >= 0 else '#c0392b')
                    fig = go.Figure(go.Bar(
                        x=monthly_stats['month'],
                        y=monthly_stats['損益合計'],
                        marker_color=monthly_stats['色'],
                        text=monthly_stats['損益合計'].apply(lambda x: f"¥{x:,.0f}"),
                        textposition='outside'
                    ))
                    fig.update_layout(
                        height=280, title='月別損益（円）', title_font_size=12,
                        paper_bgcolor='#1c1c1c', plot_bgcolor='#1c1c1c',
                        font_color='#f7f7f5'
                    )
                    fig.update_xaxes(gridcolor='#2a2a2a')
                    fig.update_yaxes(gridcolor='#2a2a2a', zeroline=True, zerolinecolor='#444')
                    st.plotly_chart(fig, use_container_width=True)

            else:
                st.info("決済済みトレードがありません。ポジションを決済して決済理由を入力すると分析が表示されます。")

        # ==================== タブ4: 資金管理 ====================
        with tab4:
            st.subheader("💰 資金管理")
            settings = load_settings(sheets_client, spreadsheet_id)

            st.markdown('<div class="section-label">総資産設定</div>', unsafe_allow_html=True)
            col1, col2 = st.columns([2, 1])
            with col1:
                total_capital = st.number_input("現在の総資産（円）", min_value=0.0,
                                                value=float(settings['total_capital']), step=10000.0, format="%.0f")
            with col2:
                st.metric("総資産", f"¥{total_capital:,.0f}")

            st.markdown('<div class="section-label">リスク設定</div>', unsafe_allow_html=True)
            risk_pct = st.slider("1トレードの許容リスク（%）", min_value=0.1, max_value=5.0,
                                 value=float(settings['risk_per_trade_pct']), step=0.1, format="%.1f%%")
            risk_amount = total_capital * (risk_pct / 100)
            st.metric("1トレードの許容損失額", f"¥{risk_amount:,.0f}")

            if st.button("💾 設定を保存", use_container_width=True, type="primary"):
                ok = save_settings(sheets_client, spreadsheet_id, total_capital, risk_pct)
                if ok:
                    st.success(f"✅ 保存しました（総資産: ¥{total_capital:,.0f} / リスク: {risk_pct:.1f}%）")
                    st.rerun()

            st.divider()
            st.markdown('<div class="section-label">適正株数計算機</div>', unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                calc_current_price = st.number_input("現在価格（円）", min_value=0.0, step=0.01, format="%.2f")
            with col2:
                calc_stop_loss = st.number_input("損切り価格（円）", min_value=0.0, step=0.01, format="%.2f")

            if calc_current_price > 0 and calc_stop_loss > 0 and calc_current_price > calc_stop_loss:
                loss_per_share   = calc_current_price - calc_stop_loss
                max_shares       = int(risk_amount / loss_per_share)
                total_investment = calc_current_price * max_shares
                st.success(f"### 🎯 エントリー可能株数: **{max_shares}株**")
                col1, col2, col3 = st.columns(3)
                with col1: st.metric("投資額", f"¥{total_investment:,.0f}")
                with col2: st.metric("1株あたり損失", f"¥{loss_per_share:,.2f}")
                with col3: st.metric("最大損失額", f"¥{risk_amount:,.0f}")
                st.info(f"損切り幅: {(loss_per_share/calc_current_price*100):.2f}% | 資産比率: {(total_investment/total_capital*100):.2f}%")
            elif calc_current_price > 0 and calc_stop_loss >= calc_current_price:
                st.warning("⚠️ 損切り価格は現在価格より低く設定してください")

        # ==================== タブ5: 保有ポジション（詳細・編集） ====================
        with tab5:
            st.subheader("📦 保有ポジション（詳細・編集）")
            df_all_t6 = load_all_trades(sheets_client, spreadsheet_id)

            if len(df_all_t6) > 0:
                with st.expander("🔍 デバッグ：銘柄別の取引生データ確認"):
                    debug_ticker = st.selectbox("確認する銘柄コード",
                                                sorted(df_all_t6["ticker_code"].unique().tolist()),
                                                key="debug_ticker")
                    debug_r = df_all_t6[df_all_t6["ticker_code"] == debug_ticker].sort_values("trade_date")
                    st.dataframe(debug_r[["trade_date","market","account_type","trade_type","trade_action","quantity","price"]],
                                 use_container_width=True, height=300)

            df_positions_t6 = calculate_position_summary(df_all_t6)
            manual_pos_df_t6 = read_sheet(sheets_client, spreadsheet_id, 'manual_positions')
            if len(df_positions_t6) > 0 and len(manual_pos_df_t6) > 0:
                manual_pos_df_t6['quantity']  = pd.to_numeric(manual_pos_df_t6['quantity'], errors='coerce').fillna(0)
                manual_pos_df_t6['avg_price'] = pd.to_numeric(manual_pos_df_t6['avg_price'], errors='coerce').fillna(0)
                for _, mrow in manual_pos_df_t6.iterrows():
                    mask = ((df_positions_t6['ticker_code'] == mrow['ticker_code']) &
                            (df_positions_t6['trade_type'] == mrow['trade_type']))
                    if mask.any():
                        if float(mrow['quantity']) <= 0:
                            df_positions_t6 = df_positions_t6[~mask]
                        else:
                            df_positions_t6.loc[mask, 'quantity']   = int(mrow['quantity'])
                            df_positions_t6.loc[mask, 'avg_price']  = float(mrow['avg_price'])
                            df_positions_t6.loc[mask, 'total_cost'] = round(float(mrow['avg_price']) * float(mrow['quantity']), 0)
                df_positions_t6 = df_positions_t6.sort_values('ticker_code').reset_index(drop=True)

            if len(df_positions_t6) > 0:
                spot_jp_t6   = df_positions_t6[(df_positions_t6['market'] == '日本株') & (df_positions_t6['trade_type'] == 'spot')].copy()
                margin_jp_t6 = df_positions_t6[(df_positions_t6['market'] == '日本株') & (df_positions_t6['trade_type'] == 'margin')].copy()
                us_stocks_t6 = df_positions_t6[df_positions_t6['market'] == '米国株'].copy()
                st.caption(f"保有銘柄数: {len(df_positions_t6)}件　（現物 {len(spot_jp_t6)} ／ 信用 {len(margin_jp_t6)} ／ 米国株 {len(us_stocks_t6)}）　💡 数量を0にすると削除")

                pos_tab1, pos_tab2, pos_tab3 = st.tabs([
                    f"🇯🇵 現物 {len(spot_jp_t6)}",
                    f"📊 信用 {len(margin_jp_t6)}",
                    f"🇺🇸 米国 {len(us_stocks_t6)}"
                ])

                def render_editable_positions(sub_df, tab_key):
                    if len(sub_df) == 0:
                        st.info("このカテゴリの保有はありません")
                        return
                    display_df = sub_df[['ticker_code','stock_name','quantity','avg_price','total_cost']].rename(columns={
                        'ticker_code':'コード','stock_name':'銘柄名','quantity':'数量',
                        'avg_price':'平均単価','total_cost':'総額'
                    }).reset_index(drop=True)
                    edited = st.data_editor(display_df, use_container_width=True, num_rows="dynamic",
                        column_config={
                            "コード":   st.column_config.TextColumn("コード", width="small"),
                            "銘柄名":   st.column_config.TextColumn("銘柄名"),
                            "数量":     st.column_config.NumberColumn("数量", min_value=0, step=1, width="small"),
                            "平均単価": st.column_config.NumberColumn("平均単価", min_value=0, format="%.2f"),
                            "総額":     st.column_config.NumberColumn("総額", disabled=True),
                        }, key=f"editor_{tab_key}")
                    st.session_state[f"edited_{tab_key}"] = edited

                with pos_tab1: render_editable_positions(spot_jp_t6, "spot_jp")
                with pos_tab2: render_editable_positions(margin_jp_t6, "margin_jp")
                with pos_tab3: render_editable_positions(us_stocks_t6, "us_stocks")

                st.divider()
                if st.button("💾 変更を保存", use_container_width=True, type="primary"):
                    save_rows = []
                    for tab_key, trade_type_default, orig_df in [
                        ("spot_jp",   "spot",   spot_jp_t6),
                        ("margin_jp", "margin", margin_jp_t6),
                        ("us_stocks", "spot",   us_stocks_t6)
                    ]:
                        edited_df = st.session_state.get(f"edited_{tab_key}")
                        if edited_df is None:
                            continue
                        for _, erow in edited_df.iterrows():
                            code = str(erow.get("コード", "")).strip()
                            if not code:
                                continue
                            orig_match    = orig_df[orig_df['ticker_code'] == code]
                            market_val    = orig_match.iloc[0]['market']     if len(orig_match) > 0 else '日本株'
                            tradetype_val = orig_match.iloc[0]['trade_type'] if len(orig_match) > 0 else trade_type_default
                            save_rows.append({
                                'ticker_code': code,
                                'stock_name':  str(erow.get("銘柄名", code)),
                                'market':      market_val,
                                'trade_type':  tradetype_val,
                                'quantity':    float(erow.get("数量", 0)),
                                'avg_price':   float(erow.get("平均単価", 0)),
                                'updated_at':  datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                    if save_rows:
                        if write_sheet(sheets_client, spreadsheet_id, 'manual_positions', pd.DataFrame(save_rows)):
                            st.success("✅ 保存しました")
                            st.rerun()
                    else:
                        st.warning("保存するデータがありません")
            else:
                st.info("現在保有中のポジションはありません")

            # 決済入力（ポジションタブに移動）
            st.divider()
            st.markdown('<div class="section-label">決済記録</div>', unsafe_allow_html=True)
            st.caption("保有中ポジションの決済を記録します")
            df_tr_t5 = load_trade_reasons(sheets_client, spreadsheet_id)
            active_for_close = df_tr_t5[df_tr_t5['status'].astype(str) == 'active'] if len(df_tr_t5) > 0 else pd.DataFrame()

            if len(active_for_close) > 0:
                close_opts = [f"{r['ticker_code']} {r['stock_name']} ({r['trade_type']})"
                              for _, r in active_for_close.iterrows()]
                close_sel = st.selectbox("決済するポジションを選択", close_opts, key="close_sel")
                close_idx = close_opts.index(close_sel)
                close_row = active_for_close.iloc[close_idx]

                df_defs_close = get_reason_definitions(sheets_client, spreadsheet_id)
                ep = float(close_row['entry_price']) if close_row.get('entry_price') and str(close_row.get('entry_price', '')) not in ('', 'nan') else 0.0
                qty_close = int(float(close_row['quantity'])) if close_row.get('quantity') and str(close_row.get('quantity', '')) not in ('', 'nan') else 0

                with st.form("close_form_t5"):
                    col1, col2 = st.columns(2)
                    with col1:
                        exit_date  = st.date_input("決済日", value=datetime.now())
                        exit_price = st.number_input("決済価格", min_value=0.0, step=1.0, value=ep, format="%.1f")
                    with col2:
                        pl_preview = (exit_price - ep) * qty_close if ep > 0 and exit_price > 0 else 0
                        pl_pct_pre = ((exit_price - ep) / ep * 100) if ep > 0 and exit_price > 0 else 0
                        pl_col = "#3d9960" if pl_preview >= 0 else "#c0392b"
                        st.markdown(f"""
<div style="text-align:center;padding:16px;background:var(--gray-dark);border-radius:8px;margin-top:8px;">
  <div style="font-size:10px;color:#888;font-family:'Space Mono',monospace;">損益プレビュー</div>
  <div style="font-size:20px;font-weight:700;color:{pl_col};">¥{pl_preview:,.0f}</div>
  <div style="font-size:12px;color:{pl_col};">{pl_pct_pre:+.2f}%</div>
</div>""", unsafe_allow_html=True)

                    st.markdown("**決済理由**")
                    xl_items = get_large(df_defs_close, 'exit')
                    x_large  = st.selectbox("大項目", xl_items if xl_items else [""], key="cl_xl_t5")
                    xm_items = get_medium(df_defs_close, 'exit', x_large)
                    x_medium = st.selectbox("中項目", xm_items if xm_items else ["（なし）"], key="cl_xm_t5")
                    xs_items = get_small(df_defs_close, 'exit', x_medium)
                    x_small  = st.selectbox("小項目", xs_items if xs_items else ["（なし）"], key="cl_xs_t5")
                    close_notes = st.text_area("決済メモ", height=60, key="cl_notes_t5")

                    submitted = st.form_submit_button("✅ 決済完了", use_container_width=True)
                    if submitted and exit_price > 0:
                        pl_final     = (exit_price - ep) * qty_close
                        pl_pct_final = ((exit_price - ep) / ep * 100) if ep > 0 else 0
                        record = dict(close_row)
                        record['exit_date']          = str(exit_date)
                        record['exit_price']         = str(exit_price)
                        record['exit_reason_large']  = x_large
                        record['exit_reason_medium'] = x_medium if x_medium != "（なし）" else ""
                        record['exit_reason_small']  = x_small if x_small != "（なし）" else ""
                        record['exit_memo']          = close_notes
                        record['profit_loss']        = str(round(pl_final, 0))
                        record['profit_loss_pct']    = str(round(pl_pct_final, 2))
                        record['status']             = 'closed'
                        upsert_trade_reason(sheets_client, spreadsheet_id, record)
                        color = "🟢" if pl_final >= 0 else "🔴"
                        st.success(f"{color} 決済完了　損益: ¥{pl_final:,.0f} ({pl_pct_final:+.2f}%)")
                        st.rerun()
            else:
                st.info("決済できるポジションがありません（催促タブでエントリー理由を登録してください）")

        # ==================== タブ6: 設定 ====================
        with tab7_placeholder := tab6:
            st.subheader("⚙️ 設定")

            # --- 理由マスタ管理UI（追加・削除） ---
            st.markdown('<div class="section-label">理由マスタ管理</div>', unsafe_allow_html=True)
            df_defs_t7     = get_reason_definitions(sheets_client, spreadsheet_id)
            df_all_defs_t7 = read_sheet(sheets_client, spreadsheet_id, 'reason_definitions')

            reason_type_sel = st.selectbox("対象", ["entry", "exit", "stop_loss"],
                format_func=lambda x: {"entry": "エントリー理由", "exit": "決済理由", "stop_loss": "損切り根拠"}[x])

            if reason_type_sel == "stop_loss":
                st.markdown("**損切り根拠一覧**")
                sl_df = df_defs_t7[df_defs_t7['reason_type'] == 'stop_loss'][['name']].rename(columns={'name': '損切り根拠'})
                st.dataframe(sl_df.reset_index(drop=True), use_container_width=True)

                col_add, col_del = st.columns(2)
                with col_add:
                    with st.expander("➕ 追加"):
                        new_sl = st.text_input("損切り根拠名", key="new_sl_name")
                        if st.button("追加", key="add_sl", type="primary"):
                            if new_sl:
                                new_row = {'reason_type': 'stop_loss', 'level': 'small',
                                           'parent': '', 'name': new_sl, 'is_active': '1'}
                                if len(df_all_defs_t7) == 0:
                                    write_sheet(sheets_client, spreadsheet_id, 'reason_definitions', pd.DataFrame([new_row]))
                                else:
                                    append_to_sheet(sheets_client, spreadsheet_id, 'reason_definitions', new_row)
                                st.success("✅ 追加しました")
                                st.rerun()
                with col_del:
                    with st.expander("🗑 削除"):
                        sl_names = df_defs_t7[df_defs_t7['reason_type'] == 'stop_loss']['name'].tolist()
                        del_sl = st.selectbox("削除する項目", sl_names if sl_names else ["（なし）"], key="del_sl_sel")
                        if st.button("削除", key="del_sl_btn"):
                            if del_sl and del_sl != "（なし）":
                                df_all_defs_t7 = df_all_defs_t7[
                                    ~((df_all_defs_t7['reason_type'] == 'stop_loss') &
                                      (df_all_defs_t7['name'] == del_sl))
                                ]
                                write_sheet(sheets_client, spreadsheet_id, 'reason_definitions', df_all_defs_t7)
                                st.success(f"✅ 「{del_sl}」を削除しました")
                                st.rerun()
            else:
                col_l, col_m, col_s = st.columns(3)

                with col_l:
                    st.markdown("**大項目**")
                    large_df = df_defs_t7[
                        (df_defs_t7['reason_type'] == reason_type_sel) & (df_defs_t7['level'] == 'large')
                    ][['name']].rename(columns={'name': '大項目'})
                    st.dataframe(large_df.reset_index(drop=True), use_container_width=True)
                    with st.expander("➕ 追加"):
                        new_large = st.text_input("大項目名", key=f"new_large_{reason_type_sel}")
                        if st.button("追加", key=f"add_large_{reason_type_sel}", type="primary"):
                            if new_large:
                                new_row = {'reason_type': reason_type_sel, 'level': 'large',
                                           'parent': '', 'name': new_large, 'is_active': '1'}
                                if len(df_all_defs_t7) == 0:
                                    write_sheet(sheets_client, spreadsheet_id, 'reason_definitions', pd.DataFrame([new_row]))
                                else:
                                    append_to_sheet(sheets_client, spreadsheet_id, 'reason_definitions', new_row)
                                st.success("✅ 追加しました")
                                st.rerun()
                    with st.expander("🗑 削除"):
                        large_names = df_defs_t7[
                            (df_defs_t7['reason_type'] == reason_type_sel) & (df_defs_t7['level'] == 'large')
                        ]['name'].tolist()
                        del_large = st.selectbox("削除", large_names if large_names else ["（なし）"], key=f"del_large_{reason_type_sel}")
                        if st.button("削除", key=f"del_large_btn_{reason_type_sel}"):
                            if del_large and del_large != "（なし）":
                                # 大項目とその配下の中・小項目もすべて削除
                                medium_children = df_all_defs_t7[
                                    (df_all_defs_t7['reason_type'] == reason_type_sel) &
                                    (df_all_defs_t7['level'] == 'medium') &
                                    (df_all_defs_t7['parent'] == del_large)
                                ]['name'].tolist()
                                df_all_defs_t7 = df_all_defs_t7[
                                    ~((df_all_defs_t7['reason_type'] == reason_type_sel) &
                                      (df_all_defs_t7['level'] == 'large') &
                                      (df_all_defs_t7['name'] == del_large))
                                ]
                                df_all_defs_t7 = df_all_defs_t7[
                                    ~((df_all_defs_t7['reason_type'] == reason_type_sel) &
                                      (df_all_defs_t7['level'] == 'medium') &
                                      (df_all_defs_t7['parent'] == del_large))
                                ]
                                for mc in medium_children:
                                    df_all_defs_t7 = df_all_defs_t7[
                                        ~((df_all_defs_t7['reason_type'] == reason_type_sel) &
                                          (df_all_defs_t7['level'] == 'small') &
                                          (df_all_defs_t7['parent'] == mc))
                                    ]
                                write_sheet(sheets_client, spreadsheet_id, 'reason_definitions', df_all_defs_t7)
                                st.success(f"✅ 「{del_large}」とその配下を削除しました")
                                st.rerun()

                with col_m:
                    st.markdown("**中項目**")
                    large_items_t7   = get_large(df_defs_t7, reason_type_sel)
                    parent_for_medium = st.selectbox("大項目を選択",
                        large_items_t7 if large_items_t7 else ["（大項目なし）"],
                        key=f"par_med_{reason_type_sel}")
                    medium_df = df_defs_t7[
                        (df_defs_t7['reason_type'] == reason_type_sel) &
                        (df_defs_t7['level'] == 'medium') &
                        (df_defs_t7['parent'] == parent_for_medium)
                    ][['name']].rename(columns={'name': '中項目'})
                    st.dataframe(medium_df.reset_index(drop=True), use_container_width=True)
                    with st.expander("➕ 追加"):
                        new_medium = st.text_input("中項目名", key=f"new_medium_{reason_type_sel}")
                        if st.button("追加", key=f"add_medium_{reason_type_sel}", type="primary"):
                            if new_medium and parent_for_medium and parent_for_medium != "（大項目なし）":
                                new_row = {'reason_type': reason_type_sel, 'level': 'medium',
                                           'parent': parent_for_medium, 'name': new_medium, 'is_active': '1'}
                                if len(df_all_defs_t7) == 0:
                                    write_sheet(sheets_client, spreadsheet_id, 'reason_definitions', pd.DataFrame([new_row]))
                                else:
                                    append_to_sheet(sheets_client, spreadsheet_id, 'reason_definitions', new_row)
                                st.success("✅ 追加しました")
                                st.rerun()
                    with st.expander("🗑 削除"):
                        medium_names = df_defs_t7[
                            (df_defs_t7['reason_type'] == reason_type_sel) &
                            (df_defs_t7['level'] == 'medium') &
                            (df_defs_t7['parent'] == parent_for_medium)
                        ]['name'].tolist()
                        del_medium = st.selectbox("削除", medium_names if medium_names else ["（なし）"], key=f"del_medium_{reason_type_sel}")
                        if st.button("削除", key=f"del_medium_btn_{reason_type_sel}"):
                            if del_medium and del_medium != "（なし）":
                                df_all_defs_t7 = df_all_defs_t7[
                                    ~((df_all_defs_t7['reason_type'] == reason_type_sel) &
                                      (df_all_defs_t7['level'] == 'medium') &
                                      (df_all_defs_t7['name'] == del_medium))
                                ]
                                df_all_defs_t7 = df_all_defs_t7[
                                    ~((df_all_defs_t7['reason_type'] == reason_type_sel) &
                                      (df_all_defs_t7['level'] == 'small') &
                                      (df_all_defs_t7['parent'] == del_medium))
                                ]
                                write_sheet(sheets_client, spreadsheet_id, 'reason_definitions', df_all_defs_t7)
                                st.success(f"✅ 「{del_medium}」とその配下を削除しました")
                                st.rerun()

                with col_s:
                    st.markdown("**小項目**")
                    medium_items_t7  = get_medium(df_defs_t7, reason_type_sel, parent_for_medium)
                    parent_for_small = st.selectbox("中項目を選択",
                        medium_items_t7 if medium_items_t7 else ["（中項目なし）"],
                        key=f"par_sml_{reason_type_sel}")
                    small_df = df_defs_t7[
                        (df_defs_t7['reason_type'] == reason_type_sel) &
                        (df_defs_t7['level'] == 'small') &
                        (df_defs_t7['parent'] == parent_for_small)
                    ][['name']].rename(columns={'name': '小項目'})
                    st.dataframe(small_df.reset_index(drop=True), use_container_width=True)
                    with st.expander("➕ 追加"):
                        new_small = st.text_input("小項目名", key=f"new_small_{reason_type_sel}")
                        if st.button("追加", key=f"add_small_{reason_type_sel}", type="primary"):
                            if new_small and parent_for_small and parent_for_small != "（中項目なし）":
                                new_row = {'reason_type': reason_type_sel, 'level': 'small',
                                           'parent': parent_for_small, 'name': new_small, 'is_active': '1'}
                                if len(df_all_defs_t7) == 0:
                                    write_sheet(sheets_client, spreadsheet_id, 'reason_definitions', pd.DataFrame([new_row]))
                                else:
                                    append_to_sheet(sheets_client, spreadsheet_id, 'reason_definitions', new_row)
                                st.success("✅ 追加しました")
                                st.rerun()
                    with st.expander("🗑 削除"):
                        small_names = df_defs_t7[
                            (df_defs_t7['reason_type'] == reason_type_sel) &
                            (df_defs_t7['level'] == 'small') &
                            (df_defs_t7['parent'] == parent_for_small)
                        ]['name'].tolist()
                        del_small = st.selectbox("削除", small_names if small_names else ["（なし）"], key=f"del_small_{reason_type_sel}")
                        if st.button("削除", key=f"del_small_btn_{reason_type_sel}"):
                            if del_small and del_small != "（なし）":
                                df_all_defs_t7 = df_all_defs_t7[
                                    ~((df_all_defs_t7['reason_type'] == reason_type_sel) &
                                      (df_all_defs_t7['level'] == 'small') &
                                      (df_all_defs_t7['name'] == del_small))
                                ]
                                write_sheet(sheets_client, spreadsheet_id, 'reason_definitions', df_all_defs_t7)
                                st.success(f"✅ 「{del_small}」を削除しました")
                                st.rerun()

            st.divider()

            # --- データ管理 ---
            st.markdown('<div class="section-label">データ管理</div>', unsafe_allow_html=True)
            st.warning("⚠️ v5移行時は以下の手順を実施してください\n1. Googleスプレッドシートから `active_trades` `closed_trades` シートを削除\n2. `trade_reasons` シートを全行削除（ヘッダーは残す）\n3. アプリを再起動して催促タブからポジションを手入力")

            if st.button("🗑 全データをリセット", use_container_width=True):
                if st.checkbox("本当にリセットしますか？（取消不可）"):
                    for sheet_name, cols in [
                        ('trades', ['trade_date','settlement_date','market','ticker_code','stock_name',
                                    'account_type','trade_type','trade_action','quantity','price',
                                    'commission','tax','total_amount','exchange_rate','currency','created_at']),
                        ('trade_reasons', TRADE_REASONS_COLS),
                    ]:
                        write_sheet(sheets_client, spreadsheet_id, sheet_name, pd.DataFrame(columns=cols))
                    st.success("✅ データをリセットしました")
                    st.rerun()

            st.divider()
            st.markdown('<div class="section-label">接続情報</div>', unsafe_allow_html=True)
            st.code(f"Spreadsheet ID: {spreadsheet_id}")
            st.caption("Railwayの環境変数 SPREADSHEET_ID に設定されているIDです")

        st.divider()
        st.caption("© 2026 トレード分析＆資金管理アプリ (v5 Google Sheets版)")

    else:
        st.error("スプレッドシートIDの設定が必要です")

else:
    st.error("""
### ⚠️ Google Sheets認証が必要です

| 変数名 | 内容 |
|--------|------|
| `GCP_SERVICE_ACCOUNT_JSON` | サービスアカウントJSONの中身 |
| `SPREADSHEET_ID` | GoogleスプレッドシートのID |
""")
