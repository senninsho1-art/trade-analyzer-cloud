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

# yfinance（株価取得用）
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

# ページ設定（モバイルファースト）
st.set_page_config(
    page_title="トレード分析＆資金管理",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# カスタムCSS（スマホ最適化）
st.markdown("""
<style>
.main .block-container {
    padding-top: 0.5rem;
    padding-bottom: 1rem;
    padding-left: 0.75rem;
    padding-right: 0.75rem;
    max-width: 100%;
}
h1 { font-size: 1.2rem !important; margin-bottom: 0 !important; padding-bottom: 0 !important; }
.stCaption { margin-top: 0 !important; font-size: 0.7rem !important; }
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] {
    position: sticky !important;
    top: 0 !important;
    z-index: 1000 !important;
    background-color: #0e1117 !important;
    padding: 4px 0 !important;
    border-bottom: 1px solid #333 !important;
}
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] button {
    font-size: 12px !important;
    padding: 10px 6px !important;
    min-width: 0 !important;
}
.trade-card {
    background-color: #1a1f2e;
    border: 1px solid #2d3348;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 10px;
}
.stButton button {
    width: 100%;
    height: 48px;
    font-size: 15px;
    margin: 4px 0;
    border-radius: 8px;
}
.stTextInput input, .stNumberInput input { height: 46px; font-size: 15px; }
.dataframe { font-size: 13px; }
.import-date { font-size: 0.72rem; color: #888; margin-top: 4px; text-align: center; }
h2 { font-size: 1.1rem !important; }
h3 { font-size: 1.0rem !important; }

/* 催促カード */
.prompt-card {
    background: #1a1f2e;
    border: 1px solid #3a4060;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 10px;
}
.prompt-card.exit-card {
    border-left: 3px solid #ffa500;
}
.prompt-card.entry-card {
    border-left: 3px solid #00aaff;
}
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

def create_spreadsheet_if_needed(sheets_client):
    spreadsheet_id = get_spreadsheet_id()
    if not spreadsheet_id:
        st.warning("📝 スプレッドシートIDが設定されていません。新規作成します。")
        spreadsheet = {
            'properties': {'title': 'トレード分析データ'},
            'sheets': [
                {'properties': {'title': 'trades'}},
                {'properties': {'title': 'active_trades'}},
                {'properties': {'title': 'closed_trades'}},
                {'properties': {'title': 'settings'}},
                {'properties': {'title': 'reason_definitions'}},
                {'properties': {'title': 'trade_reasons'}},
            ]
        }
        try:
            result = sheets_client.create(body=spreadsheet).execute()
            new_id = result['spreadsheetId']
            st.success("✅ スプレッドシート作成完了！")
            st.code(f'SPREADSHEET_ID="{new_id}"')
            st.info("👆 このIDをRailwayの環境変数 SPREADSHEET_ID に追加してください")
            return new_id
        except Exception as e:
            st.error(f"作成エラー: {str(e)}")
            return None
    return spreadsheet_id

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
            df = pd.DataFrame(values[1:], columns=values[0])
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

def init_spreadsheet(sheets_client, spreadsheet_id):
    ensure_sheet_exists(sheets_client, spreadsheet_id, 'manual_positions')
    ensure_sheet_exists(sheets_client, spreadsheet_id, 'trade_reasons')

    settings_df = read_sheet(sheets_client, spreadsheet_id, 'settings')
    if len(settings_df) == 0:
        settings_df = pd.DataFrame({
            'id': [1],
            'total_capital': [1000000],
            'risk_per_trade_pct': [0.2],
            'updated_at': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        })
        write_sheet(sheets_client, spreadsheet_id, 'settings', settings_df)

    reason_df = read_sheet(sheets_client, spreadsheet_id, 'reason_definitions')
    if len(reason_df) == 0:
        initial_reasons = [
            ('entry_category', '打診買い', '打診買い', 1),
            ('entry_category', '追撃買い', '追撃買い', 1),
            ('entry_category', 'ナンピン', 'ナンピン', 1),
            ('entry_category', 'ポジション調整', 'ポジション調整', 1),
            ('entry_detail', '順張り', 'MAブレイク', 1),
            ('entry_detail', '順張り', '高値ブレイク', 1),
            ('entry_detail', '順張り', '短期MA反発', 1),
            ('entry_detail', '逆張り', 'MA乖離率', 1),
            ('entry_detail', '逆張り', '二番底', 1),
            ('entry_detail', '逆張り', '窓埋め', 1),
            ('entry_detail', '逆張り', '直近安値', 1),
            ('entry_detail', '逆張り', '節目', 1),
            ('entry_detail', 'イベント', '決算期待', 1),
            ('entry_detail', 'イベント', '決算後急騰', 1),
            ('entry_detail', 'イベント', '決算後暴落', 1),
            ('entry_detail', 'イベント', '材料', 1),
            ('entry_detail', 'イベント', 'ニュース', 1),
            ('stop_loss', '損切り', '総資産の0.2%減', 1),
            ('stop_loss', '損切り', '買値-5%', 1),
            ('stop_loss', '損切り', '買値-10%', 1),
            ('stop_loss', '損切り', '直近安値', 1),
            ('stop_loss', '損切り', '節目', 1),
            ('exit_category', '利確', '利確', 1),
            ('exit_category', '損切り', '損切り', 1),
            ('exit_category', '調整', '調整', 1),
            ('exit_detail', '利確', '目標達成', 1),
            ('exit_detail', '利確', '利益確定', 1),
            ('exit_detail', '損切り', '逆指値', 1),
            ('exit_detail', '損切り', 'シナリオ崩れ', 1),
            ('exit_detail', '調整', 'ポジション縮小', 1),
        ]
        reason_df = pd.DataFrame(initial_reasons, columns=['reason_type', 'category', 'detail', 'is_active'])
        write_sheet(sheets_client, spreadsheet_id, 'reason_definitions', reason_df)

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
        'id': [1], 'total_capital': [total_capital],
        'risk_per_trade_pct': [risk_per_trade_pct],
        'updated_at': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
    })
    write_sheet(sheets_client, spreadsheet_id, 'settings', settings_df)

def get_reason_list(sheets_client, spreadsheet_id, reason_type):
    df = read_sheet(sheets_client, spreadsheet_id, 'reason_definitions')
    if len(df) > 0:
        df = df[df['reason_type'] == reason_type]
        df = df[df['is_active'] == '1']
        return df[['category', 'detail']].drop_duplicates()
    return pd.DataFrame(columns=['category', 'detail'])

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
        numeric_cols = ['quantity', 'price', 'commission', 'tax', 'total_amount']
        for col in numeric_cols:
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

    df['quantity'] = pd.to_numeric(
        df['quantity'].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
    df['price'] = pd.to_numeric(
        df['price'].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
    df = df.sort_values('trade_date').reset_index(drop=True)

    summary = []
    for ticker in df['ticker_code'].unique():
        r = df[df['ticker_code'] == ticker]
        name_rows  = r[r['stock_name'].notna() & (r['stock_name'] != '')]
        stock_name = name_rows.iloc[0]['stock_name'] if len(name_rows) > 0 else ticker
        market     = name_rows.iloc[0]['market']     if len(name_rows) > 0 else '日本株'

        kenin_rows = r[(r['account_type'] == '現引') & (~r['trade_action'].isin(['買建', '売埋']))]
        kenin_qty = kenin_rows['quantity'].sum()

        if market == '米国株':
            buy_qty   = r[r['trade_action'] == '買付']['quantity'].sum()
            sell_qty  = r[r['trade_action'] == '売付']['quantity'].sum()
            nyuko_qty = 0
        else:
            spot_rows  = r[r['account_type'] == '現物']
            buy_qty    = spot_rows[spot_rows['trade_action'] == '買付']['quantity'].sum()
            sell_qty   = spot_rows[spot_rows['trade_action'] == '売付']['quantity'].sum()
            nyuko_qty  = r[r['trade_action'] == '入庫']['quantity'].sum()

        spot_qty   = buy_qty + nyuko_qty + kenin_qty - sell_qty
        mbuy_qty   = r[r['trade_action'] == '買建']['quantity'].sum()
        msell_qty  = r[r['trade_action'] == '売埋']['quantity'].sum()
        margin_qty = mbuy_qty - msell_qty - kenin_qty

        if spot_qty > 0:
            if market == '米国株':
                spot_r = r[
                    r['trade_action'].isin(['買付', '売付']) |
                    ((r['account_type'] == '現引') & (~r['trade_action'].isin(['買建', '売埋'])))
                ].copy()
            else:
                spot_r = r[
                    ((r['account_type'] == '現物') & r['trade_action'].isin(['買付', '売付'])) |
                    (r['trade_action'] == '入庫') |
                    ((r['account_type'] == '現引') & (~r['trade_action'].isin(['買建', '売埋'])))
                ].copy()
            spot_avg = calc_avg_price(
                spot_r.sort_values('trade_date'),
                buy_actions=['買付', '入庫'], sell_action='売付', kenin_sell=False)
            summary.append({
                'ticker_code': ticker, 'stock_name': stock_name,
                'market': market, 'trade_type': '現物',
                'quantity': int(round(spot_qty)), 'avg_price': round(spot_avg, 2),
                'total_cost': round(spot_avg * spot_qty, 0)
            })

        if margin_qty > 0:
            margin_r = r[
                r['trade_action'].isin(['買建', '売埋']) |
                ((r['account_type'] == '現引') & (~r['trade_action'].isin(['買建', '売埋'])))
            ].copy()
            margin_avg = calc_avg_price(
                margin_r.sort_values('trade_date'),
                buy_actions=['買建'], sell_action='売埋', kenin_sell=True)
            summary.append({
                'ticker_code': ticker, 'stock_name': stock_name,
                'market': market, 'trade_type': '信用買',
                'quantity': int(round(margin_qty)), 'avg_price': round(margin_avg, 2),
                'total_cost': round(margin_avg * margin_qty, 0)
            })

    result = pd.DataFrame(summary)
    if len(result) > 0:
        result = result.sort_values('ticker_code').reset_index(drop=True)
    return result

# ==================== trade_reasons CRUD ====================
TRADE_REASONS_COLS = [
    'ticker_code', 'trade_date', 'trade_action',
    'entry_reason', 'entry_memo', 'stop_loss_price',
    'exit_reason', 'exit_memo',
    'skipped', 'created_at', 'updated_at'
]

def load_trade_reasons(sheets_client, spreadsheet_id):
    df = read_sheet(sheets_client, spreadsheet_id, 'trade_reasons')
    if len(df) == 0:
        return pd.DataFrame(columns=TRADE_REASONS_COLS)
    for col in TRADE_REASONS_COLS:
        if col not in df.columns:
            df[col] = ''
    return df

def save_trade_reason(sheets_client, spreadsheet_id, ticker_code, trade_date, trade_action,
                      entry_reason='', entry_memo='', stop_loss_price='',
                      exit_reason='', exit_memo='', skipped=False):
    """指定キーのレコードをupsert（なければ追加、あれば更新）"""
    df = load_trade_reasons(sheets_client, spreadsheet_id)
    trade_date_str = str(trade_date)[:10] if trade_date else ''

    mask = (
        (df['ticker_code'].astype(str) == str(ticker_code)) &
        (df['trade_date'].astype(str).str[:10] == trade_date_str) &
        (df['trade_action'].astype(str) == str(trade_action))
    )

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_row = {
        'ticker_code': str(ticker_code),
        'trade_date': trade_date_str,
        'trade_action': str(trade_action),
        'entry_reason': entry_reason,
        'entry_memo': entry_memo,
        'stop_loss_price': str(stop_loss_price),
        'exit_reason': exit_reason,
        'exit_memo': exit_memo,
        'skipped': 'True' if skipped else '',
        'created_at': now_str,
        'updated_at': now_str,
    }

    if mask.any():
        for col, val in new_row.items():
            if col != 'created_at':
                df.loc[mask, col] = val
    else:
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    write_sheet(sheets_client, spreadsheet_id, 'trade_reasons', df)

def get_reason_key(row):
    """trade_reasonsのキー文字列を生成"""
    td = str(row.get('trade_date', ''))[:10]
    return f"{row['ticker_code']}_{td}_{row.get('trade_action','')}"

# ==================== 株価取得 ====================
def get_current_price(ticker_code, market):
    """yfinanceで現在株価を取得（15分遅延）"""
    if not YFINANCE_AVAILABLE:
        return None
    try:
        if market == '日本株':
            symbol = f"{ticker_code}.T"
        else:
            symbol = str(ticker_code)
        t = yf.Ticker(symbol)
        hist = t.history(period='2d')
        if len(hist) > 0:
            return float(hist['Close'].iloc[-1])
        return None
    except Exception:
        return None

# ==================== メイン ====================
sheets_client = get_google_sheets_client()
if sheets_client:
    spreadsheet_id = create_spreadsheet_if_needed(sheets_client)
    if spreadsheet_id:
        init_spreadsheet(sheets_client, spreadsheet_id)

        st.markdown("### 📊 トレード分析＆資金管理")

        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "📥 データ",
            "🔔 未入力催促",
            "📈 アクティブ",
            "📊 分析",
            "💰 資金",
            "📦 ポジション",
            "⚙️ 設定"
        ])

        # ========== タブ1: データ管理 ==========
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
                    year_filter = st.selectbox("年", ["全て"] +
                                               sorted(df_all['trade_date'].dt.year.unique().tolist(), reverse=True))

                df_filtered = df_all.copy()
                if market_filter != "全て":
                    df_filtered = df_filtered[df_filtered['market'] == market_filter]
                if action_filter != "全て":
                    df_filtered = df_filtered[df_filtered['trade_action'] == action_filter]
                if year_filter != "全て":
                    df_filtered = df_filtered[df_filtered['trade_date'].dt.year == year_filter]

                df_filtered = df_filtered.sort_values('trade_date', ascending=False)
                display_cols = ['trade_date', 'market', 'ticker_code', 'stock_name', 'trade_action',
                                'quantity', 'price', 'total_amount']
                st.dataframe(
                    df_filtered[display_cols].rename(columns={
                        'trade_date': '約定日', 'market': '市場', 'ticker_code': 'コード',
                        'stock_name': '銘柄名', 'trade_action': '売買',
                        'quantity': '数量', 'price': '単価', 'total_amount': '金額'
                    }).reset_index(drop=True),
                    use_container_width=True, height=400
                )
            else:
                st.info("データがありません。CSVファイルをインポートしてください。")

        # ========== タブ2: 🔔 未入力催促 ==========
        with tab2:
            df_all_t2 = load_all_trades(sheets_client, spreadsheet_id)
            df_positions_t2 = calculate_position_summary(df_all_t2)

            # manual_positions適用
            manual_pos_df_t2 = read_sheet(sheets_client, spreadsheet_id, 'manual_positions')
            if len(df_positions_t2) > 0 and len(manual_pos_df_t2) > 0:
                manual_pos_df_t2['quantity'] = pd.to_numeric(manual_pos_df_t2['quantity'], errors='coerce').fillna(0)
                manual_pos_df_t2['avg_price'] = pd.to_numeric(manual_pos_df_t2['avg_price'], errors='coerce').fillna(0)
                for _, mrow in manual_pos_df_t2.iterrows():
                    mask = (
                        (df_positions_t2['ticker_code'] == mrow['ticker_code']) &
                        (df_positions_t2['trade_type'] == mrow['trade_type'])
                    )
                    if mask.any():
                        if float(mrow['quantity']) <= 0:
                            df_positions_t2 = df_positions_t2[~mask]
                        else:
                            df_positions_t2.loc[mask, 'quantity'] = int(mrow['quantity'])
                            df_positions_t2.loc[mask, 'avg_price'] = float(mrow['avg_price'])
                            df_positions_t2.loc[mask, 'total_cost'] = round(float(mrow['avg_price']) * float(mrow['quantity']), 0)

            # trade_reasonsを読み込み
            df_reasons = load_trade_reasons(sheets_client, spreadsheet_id)

            # --- 上部：保有ポジション一覧 ---
            st.subheader("📦 保有ポジション")

            # 株価更新ボタン
            col_price_btn, col_price_info = st.columns([1, 3])
            with col_price_btn:
                fetch_prices = st.button("📡 株価更新", use_container_width=True,
                                         help="yfinanceで現在株価を取得（15分遅延）" if YFINANCE_AVAILABLE else "yfinanceが未インストールです")
            with col_price_info:
                if not YFINANCE_AVAILABLE:
                    st.caption("⚠️ yfinanceが未インストール。`pip install yfinance`で有効化できます")
                else:
                    st.caption("株価は15分遅延です")

            if len(df_positions_t2) > 0:
                # 株価キャッシュ
                if 'price_cache' not in st.session_state:
                    st.session_state['price_cache'] = {}
                if 'price_cache_time' not in st.session_state:
                    st.session_state['price_cache_time'] = None

                if fetch_prices and YFINANCE_AVAILABLE:
                    with st.spinner('株価取得中...'):
                        cache = {}
                        for _, pos_row in df_positions_t2.iterrows():
                            key = pos_row['ticker_code']
                            if key not in cache:
                                p = get_current_price(pos_row['ticker_code'], pos_row['market'])
                                cache[key] = p
                        st.session_state['price_cache'] = cache
                        st.session_state['price_cache_time'] = datetime.now().strftime('%H:%M')
                    st.rerun()

                price_cache = st.session_state.get('price_cache', {})
                cache_time  = st.session_state.get('price_cache_time')

                if cache_time:
                    st.caption(f"株価取得時刻: {cache_time}")

                # ポジション一覧テーブル
                display_rows = []
                for _, pos_row in df_positions_t2.iterrows():
                    current_price = price_cache.get(pos_row['ticker_code'])
                    avg_p = float(pos_row['avg_price'])
                    qty   = int(pos_row['quantity'])

                    if current_price and avg_p > 0:
                        unrealized_pl = (current_price - avg_p) * qty
                        unrealized_pct = (current_price - avg_p) / avg_p * 100
                        price_str = f"¥{current_price:,.1f}" if pos_row['market'] == '日本株' else f"${current_price:,.2f}"
                        pl_str = f"¥{unrealized_pl:+,.0f} ({unrealized_pct:+.1f}%)"
                    else:
                        price_str = "-"
                        pl_str = "-"

                    display_rows.append({
                        'コード': pos_row['ticker_code'],
                        '銘柄名': pos_row['stock_name'],
                        '種別': pos_row['trade_type'],
                        '数量': qty,
                        '平均単価': f"¥{avg_p:,.1f}" if pos_row['market'] == '日本株' else f"${avg_p:,.2f}",
                        '現在値': price_str,
                        '含み損益': pl_str,
                    })

                st.dataframe(pd.DataFrame(display_rows), use_container_width=True, height=300)
            else:
                st.info("保有ポジションはありません")

            st.divider()

            # --- 下部：未入力催促カード ---
            st.subheader("🔔 理由の入力をお願いします")

            # 催促対象を抽出
            # ① 保有中ポジション → エントリー理由未入力
            # ② 直近1ヶ月の決済（売付/売埋）→ 決済理由未入力

            today = pd.Timestamp.today()
            one_month_ago = today - pd.Timedelta(days=31)

            # skipped済み・入力済みのキーセット
            skipped_or_filled_buy  = set()
            skipped_or_filled_sell = set()
            if len(df_reasons) > 0:
                for _, rrow in df_reasons.iterrows():
                    key = f"{rrow['ticker_code']}_{str(rrow['trade_date'])[:10]}_{rrow['trade_action']}"
                    if rrow.get('skipped') == 'True':
                        skipped_or_filled_buy.add(key)
                        skipped_or_filled_sell.add(key)
                    else:
                        if rrow.get('entry_reason'):
                            skipped_or_filled_buy.add(key)
                        if rrow.get('exit_reason'):
                            skipped_or_filled_sell.add(key)

            # 保有中銘柄の最初の買付を催促（エントリー理由）
            prompt_entries = []
            if len(df_positions_t2) > 0 and len(df_all_t2) > 0:
                holding_tickers = df_positions_t2['ticker_code'].tolist()
                buy_actions = ['買付', '買建']
                for ticker in holding_tickers:
                    ticker_trades = df_all_t2[
                        (df_all_t2['ticker_code'] == ticker) &
                        (df_all_t2['trade_action'].isin(buy_actions))
                    ].sort_values('trade_date')
                    for _, tr in ticker_trades.iterrows():
                        key = f"{ticker}_{str(tr['trade_date'])[:10]}_{tr['trade_action']}"
                        if key not in skipped_or_filled_buy:
                            prompt_entries.append(tr)
                        # 同銘柄の最新買付まで全て催促（ナンピン等も含む）

            # 直近1ヶ月の決済を催促（決済理由）
            prompt_exits = []
            if len(df_all_t2) > 0:
                sell_actions = ['売付', '売埋']
                recent_sells = df_all_t2[
                    (df_all_t2['trade_action'].isin(sell_actions)) &
                    (df_all_t2['trade_date'] >= one_month_ago)
                ].sort_values('trade_date', ascending=False)
                for _, tr in recent_sells.iterrows():
                    key = f"{tr['ticker_code']}_{str(tr['trade_date'])[:10]}_{tr['trade_action']}"
                    if key not in skipped_or_filled_sell:
                        prompt_exits.append(tr)

            total_prompts = len(prompt_entries) + len(prompt_exits)
            if total_prompts == 0:
                st.success("✅ 未入力の取引はありません！")
            else:
                st.caption(f"未入力: エントリー {len(prompt_entries)}件 ／ 決済 {len(prompt_exits)}件")

                # reason_definitionsから選択肢を取得
                entry_categories = get_reason_list(sheets_client, spreadsheet_id, 'entry_category')
                entry_details    = get_reason_list(sheets_client, spreadsheet_id, 'entry_detail')
                exit_categories  = get_reason_list(sheets_client, spreadsheet_id, 'exit_category')
                exit_details     = get_reason_list(sheets_client, spreadsheet_id, 'exit_detail')

                entry_reason_options = []
                if len(entry_categories) > 0 and len(entry_details) > 0:
                    for _, ec in entry_categories.iterrows():
                        for _, ed in entry_details.iterrows():
                            entry_reason_options.append(f"{ec['detail']} / {ed['category']} / {ed['detail']}")
                if not entry_reason_options:
                    entry_reason_options = ["（選択肢未設定）"]

                exit_reason_options = []
                if len(exit_categories) > 0 and len(exit_details) > 0:
                    for _, ec in exit_categories.iterrows():
                        for _, ed in exit_details.iterrows():
                            exit_reason_options.append(f"{ec['detail']} / {ed['category']} / {ed['detail']}")
                if not exit_reason_options:
                    exit_reason_options = ["（選択肢未設定）"]

                # --- エントリー理由カード ---
                if prompt_entries:
                    st.markdown("#### 🟦 エントリー理由")
                    for i, tr in enumerate(prompt_entries):
                        ticker    = str(tr['ticker_code'])
                        name      = str(tr.get('stock_name', ticker))
                        trade_date_str = str(tr['trade_date'])[:10]
                        action    = str(tr.get('trade_action', '買付'))
                        price_val = float(tr['price']) if pd.notna(tr['price']) else 0.0
                        qty_val   = int(tr['quantity']) if pd.notna(tr['quantity']) else 0
                        currency  = '¥' if tr.get('market') == '日本株' else '$'

                        card_key = f"entry_{ticker}_{trade_date_str}_{i}"

                        st.markdown(f"""
<div class="prompt-card entry-card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
    <span style="font-size:1.05rem;font-weight:bold;color:#fff;">{ticker}　<span style="font-size:0.82rem;color:#ccc;font-weight:normal;">{name}</span></span>
    <span style="font-size:0.78rem;color:#aaa;">{trade_date_str}　{action}</span>
  </div>
  <div style="font-size:0.88rem;color:#ddd;">{currency}{price_val:,.1f} × {qty_val}株　合計: {currency}{price_val*qty_val:,.0f}</div>
</div>
""", unsafe_allow_html=True)

                        with st.container():
                            col_r, col_m = st.columns([2, 2])
                            with col_r:
                                selected_entry_reason = st.selectbox(
                                    "エントリー理由", entry_reason_options,
                                    key=f"er_{card_key}"
                                )
                            with col_m:
                                entry_memo_val = st.text_input("メモ（任意）", key=f"em_{card_key}", placeholder="自由記述")

                            stop_loss_val = st.number_input(
                                "損切りポイント（円/ドル）※必須",
                                min_value=0.0, step=1.0, format="%.1f",
                                key=f"sl_{card_key}"
                            )

                            col_save, col_skip = st.columns(2)
                            with col_save:
                                if st.button("✅ 保存", key=f"save_{card_key}", use_container_width=True):
                                    if stop_loss_val <= 0:
                                        st.error("損切りポイントは必須です")
                                    else:
                                        save_trade_reason(
                                            sheets_client, spreadsheet_id,
                                            ticker_code=ticker,
                                            trade_date=trade_date_str,
                                            trade_action=action,
                                            entry_reason=selected_entry_reason,
                                            entry_memo=entry_memo_val,
                                            stop_loss_price=stop_loss_val,
                                        )
                                        st.success("保存しました")
                                        st.rerun()
                            with col_skip:
                                if st.button("⏭ スキップ（入力不要）", key=f"skip_{card_key}", use_container_width=True):
                                    save_trade_reason(
                                        sheets_client, spreadsheet_id,
                                        ticker_code=ticker,
                                        trade_date=trade_date_str,
                                        trade_action=action,
                                        skipped=True,
                                    )
                                    st.rerun()

                        st.markdown("---")

                # --- 決済理由カード ---
                if prompt_exits:
                    st.markdown("#### 🟧 決済理由")
                    for i, tr in enumerate(prompt_exits):
                        ticker         = str(tr['ticker_code'])
                        name           = str(tr.get('stock_name', ticker))
                        trade_date_str = str(tr['trade_date'])[:10]
                        action         = str(tr.get('trade_action', '売付'))
                        price_val      = float(tr['price']) if pd.notna(tr['price']) else 0.0
                        qty_val        = int(tr['quantity']) if pd.notna(tr['quantity']) else 0
                        currency       = '¥' if tr.get('market') == '日本株' else '$'

                        card_key = f"exit_{ticker}_{trade_date_str}_{i}"

                        st.markdown(f"""
<div class="prompt-card exit-card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
    <span style="font-size:1.05rem;font-weight:bold;color:#fff;">{ticker}　<span style="font-size:0.82rem;color:#ccc;font-weight:normal;">{name}</span></span>
    <span style="font-size:0.78rem;color:#aaa;">{trade_date_str}　{action}</span>
  </div>
  <div style="font-size:0.88rem;color:#ddd;">{currency}{price_val:,.1f} × {qty_val}株　合計: {currency}{price_val*qty_val:,.0f}</div>
</div>
""", unsafe_allow_html=True)

                        with st.container():
                            col_r, col_m = st.columns([2, 2])
                            with col_r:
                                selected_exit_reason = st.selectbox(
                                    "決済理由", exit_reason_options,
                                    key=f"xr_{card_key}"
                                )
                            with col_m:
                                exit_memo_val = st.text_input("メモ（任意）", key=f"xm_{card_key}", placeholder="自由記述")

                            col_save, col_skip = st.columns(2)
                            with col_save:
                                if st.button("✅ 保存", key=f"xsave_{card_key}", use_container_width=True):
                                    save_trade_reason(
                                        sheets_client, spreadsheet_id,
                                        ticker_code=ticker,
                                        trade_date=trade_date_str,
                                        trade_action=action,
                                        exit_reason=selected_exit_reason,
                                        exit_memo=exit_memo_val,
                                    )
                                    st.success("保存しました")
                                    st.rerun()
                            with col_skip:
                                if st.button("⏭ スキップ（入力不要）", key=f"xskip_{card_key}", use_container_width=True):
                                    save_trade_reason(
                                        sheets_client, spreadsheet_id,
                                        ticker_code=ticker,
                                        trade_date=trade_date_str,
                                        trade_action=action,
                                        skipped=True,
                                    )
                                    st.rerun()

                        st.markdown("---")

        # ========== タブ3: アクティブトレード ==========
        with tab3:
            st.subheader("📈 アクティブトレード")

            # ポジションタブからの自動遷移フラグ
            prefill = {}
            if st.session_state.get('goto_active_register'):
                prefill = {
                    'ticker': st.session_state.pop('prefill_ticker', ''),
                    'name':   st.session_state.pop('prefill_name', ''),
                    'price':  st.session_state.pop('prefill_price', 0.0),
                    'qty':    st.session_state.pop('prefill_qty', 1),
                    'date':   st.session_state.pop('prefill_date', ''),
                }
                st.session_state.pop('goto_active_register', None)
                st.info(f"📝 {prefill['ticker']} {prefill['name']} の登録フォームを開きました")

            with st.expander("➕ 新規ポジション登録", expanded=bool(prefill)):
                col1, col2 = st.columns(2)
                with col1:
                    entry_ticker = st.text_input("銘柄コード", value=prefill.get('ticker',''), key="entry_ticker")
                    entry_name   = st.text_input("銘柄名",     value=prefill.get('name',''),   key="entry_name")
                    entry_date   = st.date_input("エントリー日", key="entry_date")
                with col2:
                    entry_price     = st.number_input("エントリー価格（円）", min_value=0.0, value=float(prefill.get('price', 0.0)), step=1.0, format="%.1f", key="entry_price")
                    entry_qty       = st.number_input("数量（株）", min_value=1, value=int(prefill.get('qty', 1)), step=1, key="entry_qty")
                    stop_loss_price = st.number_input("損切り価格（円）※必須", min_value=0.0, step=1.0, format="%.1f", key="stop_loss_price")

                st.markdown("**エントリー根拠**")
                entry_categories_t3 = get_reason_list(sheets_client, spreadsheet_id, 'entry_category')
                col1, col2 = st.columns(2)
                with col1:
                    entry_category = st.selectbox("種別", entry_categories_t3['detail'].tolist() if len(entry_categories_t3) > 0 else [""], key="entry_cat")
                with col2:
                    entry_details_t3 = get_reason_list(sheets_client, spreadsheet_id, 'entry_detail')
                    if len(entry_details_t3) > 0:
                        entry_groups = entry_details_t3.groupby('category')['detail'].apply(list).to_dict()
                        entry_group  = st.selectbox("カテゴリ", list(entry_groups.keys()), key="entry_group")
                        entry_detail = st.selectbox("詳細", entry_groups[entry_group], key="entry_detail_sel")
                    else:
                        entry_group  = st.text_input("カテゴリ", key="entry_group")
                        entry_detail = st.text_input("詳細", key="entry_detail_sel")

                stop_loss_reasons_t3 = get_reason_list(sheets_client, spreadsheet_id, 'stop_loss')
                stop_loss_reason = st.selectbox("損切り根拠", stop_loss_reasons_t3['detail'].tolist() if len(stop_loss_reasons_t3) > 0 else [""], key="sl_reason")
                entry_notes = st.text_area("メモ", key="entry_notes", height=70)

                if st.button("✅ 登録する", use_container_width=True, type="primary", key="save_entry"):
                    if entry_ticker and entry_price > 0 and entry_qty > 0:
                        if stop_loss_price <= 0:
                            st.error("⚠️ 損切り価格は必須です")
                        else:
                            new_row = {
                                'ticker_code': entry_ticker,
                                'stock_name': entry_name,
                                'entry_date': str(entry_date),
                                'entry_price': entry_price,
                                'quantity': entry_qty,
                                'entry_reason_category': entry_category,
                                'entry_reason_detail': f"{entry_group}/{entry_detail}",
                                'stop_loss_price': stop_loss_price,
                                'stop_loss_reason': stop_loss_reason,
                                'notes': entry_notes,
                                'is_active': 1,
                                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            df_active_w = read_sheet(sheets_client, spreadsheet_id, 'active_trades')
                            if len(df_active_w) == 0:
                                write_sheet(sheets_client, spreadsheet_id, 'active_trades', pd.DataFrame([new_row]))
                            else:
                                append_to_sheet(sheets_client, spreadsheet_id, 'active_trades', new_row)
                            st.success("✅ 登録しました")
                            st.rerun()
                    else:
                        st.error("銘柄コード・価格・数量は必須です")

            st.divider()

            # アクティブ一覧（株価更新付き）
            df_active = read_sheet(sheets_client, spreadsheet_id, 'active_trades')
            if len(df_active) > 0:
                df_active = df_active[df_active['is_active'] == '1'].reset_index(drop=True)

            if len(df_active) == 0:
                st.info("アクティブなポジションはありません")
            else:
                # 株価更新ボタン（アクティブタブ用）
                col_abtn, col_ainfo = st.columns([1, 3])
                with col_abtn:
                    fetch_active_prices = st.button("📡 株価更新", key="fetch_active", use_container_width=True)
                with col_ainfo:
                    cache_time_active = st.session_state.get('active_price_cache_time')
                    if cache_time_active:
                        st.caption(f"取得時刻: {cache_time_active}")
                    else:
                        st.caption("株価更新で含み損益を表示します")

                if fetch_active_prices and YFINANCE_AVAILABLE:
                    with st.spinner('株価取得中...'):
                        active_cache = {}
                        for _, row_a in df_active.iterrows():
                            tc = str(row_a['ticker_code'])
                            if tc not in active_cache:
                                # market判定（active_tradesにmarketがない場合、数字ならJP）
                                try:
                                    int(tc)
                                    mkt = '日本株'
                                except:
                                    mkt = '米国株'
                                active_cache[tc] = get_current_price(tc, mkt)
                        st.session_state['active_price_cache'] = active_cache
                        st.session_state['active_price_cache_time'] = datetime.now().strftime('%H:%M')
                    st.rerun()

                active_price_cache = st.session_state.get('active_price_cache', {})

                st.caption(f"保有中: {len(df_active)}件")
                for idx, row in df_active.iterrows():
                    entry_p  = float(row['entry_price'])
                    stop_p   = float(row['stop_loss_price']) if row.get('stop_loss_price') else 0.0
                    qty      = int(row['quantity'])
                    loss_per = entry_p - stop_p if stop_p > 0 else 0
                    max_loss = loss_per * qty

                    current_p = active_price_cache.get(str(row['ticker_code']))
                    if current_p:
                        unrealized = (current_p - entry_p) * qty
                        unreal_pct = (current_p - entry_p) / entry_p * 100
                        pl_color   = "#00cc96" if unrealized >= 0 else "#ef553b"
                        pl_html    = f'<div style="flex:1.5;padding:8px 4px;border-right:1px solid #3a3f55;"><div style="font-size:0.62rem;color:#aaaaaa;">含み損益</div><div style="font-size:1.0rem;font-weight:700;color:{pl_color};">¥{unrealized:+,.0f}<br><span style="font-size:0.72rem;">({unreal_pct:+.1f}%)</span></div></div>'
                        sl_dist    = ((current_p - stop_p) / current_p * 100) if stop_p > 0 else 0
                        sl_html    = f'<div style="flex:1.5;padding:8px 4px;"><div style="font-size:0.62rem;color:#aaaaaa;">損切まで</div><div style="font-size:1.0rem;font-weight:700;color:#ffa500;">{sl_dist:.1f}%</div></div>'
                        extra_cols = pl_html + sl_html
                        current_price_html = f'<div style="flex:1.5;padding:8px 4px;border-right:1px solid #3a3f55;"><div style="font-size:0.62rem;color:#aaaaaa;">現在値</div><div style="font-size:1.0rem;font-weight:700;color:#ffffff;">¥{current_p:,.1f}</div></div>'
                    else:
                        extra_cols = ''
                        current_price_html = ''

                    st.markdown(f"""
<div style="background:#1a1f2e;border:1px solid #2d3348;border-radius:10px;padding:12px 14px;margin-bottom:8px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
    <div>
      <span style="font-size:1.1rem;font-weight:bold;color:#ffffff;">{row['ticker_code']}</span>
      <span style="font-size:0.82rem;color:#cccccc;margin-left:8px;">{row['stock_name']}</span>
    </div>
    <span style="font-size:0.75rem;color:#bbbbbb;">{row['entry_date']}</span>
  </div>
  <div style="display:flex;gap:0;border:1px solid #3a3f55;border-radius:8px;overflow:hidden;text-align:center;flex-wrap:wrap;">
    <div style="flex:1;padding:8px 4px;border-right:1px solid #3a3f55;">
      <div style="font-size:0.62rem;color:#aaaaaa;">建数量</div>
      <div style="font-size:1.0rem;font-weight:700;color:#ffffff;">{qty}<span style="font-size:0.65rem;color:#cccccc;">株</span></div>
    </div>
    <div style="flex:1.5;padding:8px 4px;border-right:1px solid #3a3f55;">
      <div style="font-size:0.62rem;color:#aaaaaa;">建単価</div>
      <div style="font-size:1.0rem;font-weight:700;color:#ffffff;">¥{entry_p:,.1f}</div>
    </div>
    {current_price_html}
    <div style="flex:1.5;padding:8px 4px;border-right:1px solid #3a3f55;">
      <div style="font-size:0.62rem;color:#aaaaaa;">損切価格</div>
      <div style="font-size:1.0rem;font-weight:700;color:#ff8080;">¥{stop_p:,.1f}</div>
    </div>
    <div style="flex:1.5;padding:8px 4px;border-right:1px solid #3a3f55;">
      <div style="font-size:0.62rem;color:#aaaaaa;">最大損失</div>
      <div style="font-size:1.0rem;font-weight:700;color:#ff6060;">¥{max_loss:,.0f}</div>
    </div>
    {extra_cols}
  </div>
  <div style="font-size:0.7rem;color:#bbbbbb;margin-top:6px;border-top:1px solid #2d3348;padding-top:4px;">
    📌 {row['entry_reason_category']} / {row['entry_reason_detail']}　　✂️ {row['stop_loss_reason']}
  </div>
</div>
""", unsafe_allow_html=True)

                    col_close, col_dummy = st.columns([1, 3])
                    with col_close:
                        if st.button("💴 決済", key=f"close_{idx}", use_container_width=True):
                            st.session_state[f"closing_{idx}"] = True
                            st.rerun()

                    if st.session_state.get(f"closing_{idx}", False):
                        with st.form(f"close_form_{idx}"):
                            st.markdown("**決済入力**")
                            col1, col2 = st.columns(2)
                            with col1:
                                exit_date  = st.date_input("決済日", value=datetime.now())
                                exit_price = st.number_input("決済価格", min_value=0.0, step=1.0, value=entry_p, format="%.1f")
                            with col2:
                                max_profit_val = st.number_input("最大含み益", value=0.0, step=1.0)
                                max_loss_val   = st.number_input("最大含み損", value=0.0, step=1.0)

                            exit_categories_t3 = get_reason_list(sheets_client, spreadsheet_id, 'exit_category')
                            exit_category = st.selectbox("決済種別", exit_categories_t3['detail'].tolist() if len(exit_categories_t3) > 0 else [""])

                            exit_details_t3 = get_reason_list(sheets_client, spreadsheet_id, 'exit_detail')
                            if len(exit_details_t3) > 0:
                                exit_groups = exit_details_t3.groupby('category')['detail'].apply(list).to_dict()
                                exit_group  = st.selectbox("決済理由カテゴリ", list(exit_groups.keys()))
                                exit_detail = st.selectbox("決済理由詳細", exit_groups[exit_group])
                            else:
                                exit_group  = st.text_input("決済理由カテゴリ")
                                exit_detail = st.text_input("決済理由詳細")

                            close_notes = st.text_area("決済メモ", height=60)
                            col1, col2 = st.columns(2)
                            with col1:
                                submit = st.form_submit_button("✅ 決済完了", use_container_width=True)
                            with col2:
                                cancel = st.form_submit_button("❌ キャンセル", use_container_width=True)

                            if submit and exit_price > 0:
                                profit_loss     = (exit_price - entry_p) * qty
                                profit_loss_pct = ((exit_price - entry_p) / entry_p) * 100
                                closed_row = {
                                    'ticker_code': row['ticker_code'],
                                    'stock_name': row['stock_name'],
                                    'entry_date': row['entry_date'],
                                    'entry_price': entry_p,
                                    'exit_date': str(exit_date),
                                    'exit_price': exit_price,
                                    'quantity': qty,
                                    'profit_loss': profit_loss,
                                    'profit_loss_pct': profit_loss_pct,
                                    'entry_reason_category': row['entry_reason_category'],
                                    'entry_reason_detail': row['entry_reason_detail'],
                                    'exit_reason_category': exit_category,
                                    'exit_reason_detail': f"{exit_group}/{exit_detail}",
                                    'stop_loss_price': stop_p,
                                    'max_profit': max_profit_val,
                                    'max_loss': max_loss_val,
                                    'price_3days_later': '',
                                    'price_1week_later': '',
                                    'price_1month_later': '',
                                    'exit_evaluation': '',
                                    'notes': f"{row.get('notes', '')}\n決済メモ: {close_notes}" if close_notes else row.get('notes', ''),
                                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                }
                                df_closed_sheet = read_sheet(sheets_client, spreadsheet_id, 'closed_trades')
                                if len(df_closed_sheet) == 0:
                                    write_sheet(sheets_client, spreadsheet_id, 'closed_trades', pd.DataFrame([closed_row]))
                                else:
                                    append_to_sheet(sheets_client, spreadsheet_id, 'closed_trades', closed_row)
                                df_active.loc[idx, 'is_active'] = 0
                                write_sheet(sheets_client, spreadsheet_id, 'active_trades', df_active)
                                color = "🟢" if profit_loss >= 0 else "🔴"
                                st.success(f"{color} 決済完了　損益: ¥{profit_loss:,.0f} ({profit_loss_pct:+.2f}%)")
                                del st.session_state[f"closing_{idx}"]
                                st.rerun()

                            if cancel:
                                del st.session_state[f"closing_{idx}"]
                                st.rerun()

        # ========== タブ4: 分析 ==========
        with tab4:
            st.subheader("📊 トレード分析")
            df_closed = read_sheet(sheets_client, spreadsheet_id, 'closed_trades')
            if len(df_closed) > 0:
                df_closed['entry_date']   = pd.to_datetime(df_closed['entry_date'])
                df_closed['exit_date']    = pd.to_datetime(df_closed['exit_date'])
                df_closed['hold_days']    = (df_closed['exit_date'] - df_closed['entry_date']).dt.days
                df_closed['profit_loss']  = pd.to_numeric(df_closed['profit_loss'], errors='coerce')
                df_closed['profit_loss_pct'] = pd.to_numeric(df_closed['profit_loss_pct'], errors='coerce')

                st.subheader("📈 パフォーマンスサマリー")
                col1, col2, col3, col4 = st.columns(4)
                total_trades   = len(df_closed)
                winning_trades = len(df_closed[df_closed['profit_loss'] > 0])
                losing_trades  = len(df_closed[df_closed['profit_loss'] < 0])
                win_rate       = (winning_trades / total_trades * 100) if total_trades > 0 else 0

                with col1:
                    st.metric("総トレード数", total_trades)
                    st.metric("勝率", f"{win_rate:.1f}%")
                with col2:
                    total_profit = df_closed['profit_loss'].sum()
                    avg_profit   = df_closed['profit_loss'].mean()
                    st.metric("総損益", f"¥{total_profit:,.0f}")
                    st.metric("平均損益", f"¥{avg_profit:,.0f}")
                with col3:
                    max_profit = df_closed['profit_loss'].max()
                    max_loss   = df_closed['profit_loss'].min()
                    st.metric("最大利益", f"¥{max_profit:,.0f}")
                    st.metric("最大損失", f"¥{max_loss:,.0f}")
                with col4:
                    avg_win  = df_closed[df_closed['profit_loss'] > 0]['profit_loss'].mean() if winning_trades > 0 else 0
                    avg_loss = abs(df_closed[df_closed['profit_loss'] < 0]['profit_loss'].mean()) if losing_trades > 0 else 0
                    pf       = avg_win / avg_loss if avg_loss > 0 else 0
                    st.metric("PF", f"{pf:.2f}")
                    st.metric("平均保有日数", f"{df_closed['hold_days'].mean():.1f}日")

                st.divider()

                # 理由別分析（trade_reasonsが溜まってきたら有効活用）
                df_reasons_analysis = load_trade_reasons(sheets_client, spreadsheet_id)
                if len(df_reasons_analysis) > 0 and len(df_reasons_analysis[df_reasons_analysis['entry_reason'] != '']) > 0:
                    st.subheader("📌 エントリー理由別 勝率")
                    # trade_reasonsとclosed_tradesを結合（簡易：ticker + dateで照合）
                    df_reasons_analysis['join_key'] = df_reasons_analysis['ticker_code'].astype(str) + '_' + df_reasons_analysis['trade_date'].astype(str).str[:10]
                    df_closed['join_key'] = df_closed['ticker_code'].astype(str) + '_' + df_closed['entry_date'].astype(str).str[:10]
                    merged = pd.merge(df_closed, df_reasons_analysis[['join_key','entry_reason']], on='join_key', how='left')
                    if len(merged[merged['entry_reason'].notna()]) > 0:
                        reason_stats = merged[merged['entry_reason'].notna()].groupby('entry_reason').agg(
                            トレード数=('profit_loss', 'count'),
                            勝率=('profit_loss', lambda x: (x > 0).mean() * 100),
                            平均損益=('profit_loss', 'mean'),
                            合計損益=('profit_loss', 'sum')
                        ).round(1).sort_values('合計損益', ascending=False)
                        st.dataframe(reason_stats, use_container_width=True)
                    st.divider()

                col1, col2 = st.columns(2)
                with col1:
                    df_closed_sorted = df_closed.sort_values('exit_date')
                    df_closed_sorted['cumulative_pl'] = df_closed_sorted['profit_loss'].cumsum()
                    fig = px.line(df_closed_sorted, x='exit_date', y='cumulative_pl',
                                  title='累積損益推移',
                                  labels={'exit_date': '決済日', 'cumulative_pl': '累積損益（円）'})
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    win_loss_data = pd.DataFrame({'結果': ['勝ち', '負け'], '件数': [winning_trades, losing_trades]})
                    fig = px.pie(win_loss_data, values='件数', names='結果', title='勝敗分布',
                                 color='結果', color_discrete_map={'勝ち': '#00CC96', '負け': '#EF553B'})
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)

                st.divider()
                st.subheader("📋 銘柄別分析")
                ticker_stats = df_closed.groupby('ticker_code').agg({
                    'profit_loss': ['sum', 'mean', 'count'],
                    'profit_loss_pct': 'mean'
                }).round(2)
                ticker_stats.columns = ['総損益', '平均損益', 'トレード数', '平均利益率%']
                ticker_stats = ticker_stats.sort_values('総損益', ascending=False)
                st.dataframe(ticker_stats, use_container_width=True)

                st.divider()
                st.subheader("📜 トレード履歴")
                col1, col2 = st.columns(2)
                with col1:
                    date_from = st.date_input("開始日", value=df_closed['exit_date'].min())
                with col2:
                    date_to = st.date_input("終了日", value=df_closed['exit_date'].max())

                df_filtered_closed = df_closed[
                    (df_closed['exit_date'] >= pd.Timestamp(date_from)) &
                    (df_closed['exit_date'] <= pd.Timestamp(date_to))
                ]
                display_cols = ['exit_date', 'ticker_code', 'stock_name', 'entry_price',
                                'exit_price', 'quantity', 'profit_loss', 'profit_loss_pct',
                                'entry_reason_category', 'exit_reason_category']
                st.dataframe(
                    df_filtered_closed[display_cols].rename(columns={
                        'exit_date': '決済日', 'ticker_code': 'コード', 'stock_name': '銘柄名',
                        'entry_price': 'IN価格', 'exit_price': 'OUT価格', 'quantity': '数量',
                        'profit_loss': '損益', 'profit_loss_pct': '損益率%',
                        'entry_reason_category': 'IN根拠', 'exit_reason_category': 'OUT根拠'
                    }),
                    use_container_width=True, height=400
                )
            else:
                st.info("決済済みトレードがありません")

        # ========== タブ5: 資金管理 ==========
        with tab5:
            st.subheader("💰 資金管理")
            settings = load_settings(sheets_client, spreadsheet_id)

            st.subheader("総資産設定")
            col1, col2 = st.columns([2, 1])
            with col1:
                total_capital = st.number_input("現在の総資産（円）", min_value=0.0,
                                                value=float(settings['total_capital']), step=10000.0, format="%.0f")
            with col2:
                st.metric("総資産", f"¥{total_capital:,.0f}")

            st.subheader("リスク設定")
            risk_pct = st.slider("1トレードの許容リスク（%）", min_value=0.1, max_value=5.0,
                                 value=float(settings['risk_per_trade_pct']), step=0.1, format="%.1f%%")
            risk_amount = total_capital * (risk_pct / 100)
            st.metric("1トレードの許容損失額", f"¥{risk_amount:,.0f}")

            if st.button("💾 設定を保存", use_container_width=True):
                save_settings(sheets_client, spreadsheet_id, total_capital, risk_pct)
                st.success("✅ 設定を保存しました")
                st.rerun()

            st.divider()
            st.subheader("🔢 適正株数計算機")
            col1, col2 = st.columns(2)
            with col1:
                calc_ticker        = st.text_input("銘柄コード", placeholder="例: 7203")
                calc_current_price = st.number_input("現在価格（円）", min_value=0.0, step=0.01, format="%.2f")
            with col2:
                calc_stop_loss = st.number_input("損切り価格（円）", min_value=0.0, step=0.01, format="%.2f")

            if calc_current_price > 0 and calc_stop_loss > 0 and calc_current_price > calc_stop_loss:
                loss_per_share   = calc_current_price - calc_stop_loss
                max_shares       = int(risk_amount / loss_per_share)
                total_investment = calc_current_price * max_shares
                st.success(f"### 🎯 エントリー可能株数: **{max_shares}株**")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("投資額", f"¥{total_investment:,.0f}")
                with col2:
                    st.metric("1株あたり損失", f"¥{loss_per_share:,.2f}")
                with col3:
                    st.metric("最大損失額", f"¥{risk_amount:,.0f}")
                loss_pct = (loss_per_share / calc_current_price) * 100
                st.info(f"損切り幅: {loss_pct:.2f}% | 資産比率: {(total_investment/total_capital)*100:.2f}%")
            elif calc_current_price > 0 and calc_stop_loss >= calc_current_price:
                st.warning("⚠️ 損切り価格は現在価格より低く設定してください")

        # ========== タブ6: 保有ポジション（詳細・編集） ==========
        with tab6:
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
                    st.markdown("**account_type / trade_action の組み合わせ:**")
                    st.dataframe(debug_r.groupby(["account_type","trade_action"], dropna=False)["quantity"].sum().reset_index(),
                                 use_container_width=True)

            df_positions_t6 = calculate_position_summary(df_all_t6)
            manual_pos_df_t6 = read_sheet(sheets_client, spreadsheet_id, 'manual_positions')

            if len(df_positions_t6) > 0 and len(manual_pos_df_t6) > 0:
                manual_pos_df_t6['quantity']  = pd.to_numeric(manual_pos_df_t6['quantity'], errors='coerce').fillna(0)
                manual_pos_df_t6['avg_price'] = pd.to_numeric(manual_pos_df_t6['avg_price'], errors='coerce').fillna(0)
                for _, mrow in manual_pos_df_t6.iterrows():
                    mask = (
                        (df_positions_t6['ticker_code'] == mrow['ticker_code']) &
                        (df_positions_t6['trade_type'] == mrow['trade_type'])
                    )
                    if mask.any():
                        if float(mrow['quantity']) <= 0:
                            df_positions_t6 = df_positions_t6[~mask]
                        else:
                            df_positions_t6.loc[mask, 'quantity']   = int(mrow['quantity'])
                            df_positions_t6.loc[mask, 'avg_price']  = float(mrow['avg_price'])
                            df_positions_t6.loc[mask, 'total_cost'] = round(float(mrow['avg_price']) * float(mrow['quantity']), 0)
                    else:
                        if float(mrow['quantity']) > 0:
                            df_positions_t6 = pd.concat([df_positions_t6, pd.DataFrame([{
                                'ticker_code': mrow['ticker_code'],
                                'stock_name':  mrow.get('stock_name', mrow['ticker_code']),
                                'market':      mrow.get('market', '日本株'),
                                'trade_type':  mrow['trade_type'],
                                'quantity':    int(mrow['quantity']),
                                'avg_price':   float(mrow['avg_price']),
                                'total_cost':  round(float(mrow['avg_price']) * float(mrow['quantity']), 0)
                            }])], ignore_index=True)
                df_positions_t6 = df_positions_t6.sort_values('ticker_code').reset_index(drop=True)

            if len(df_positions_t6) > 0:
                st.caption(f"保有銘柄数: {len(df_positions_t6)}件　💡 数量を0にすると削除")

                spot_jp_t6   = df_positions_t6[(df_positions_t6['market'] == '日本株') & (df_positions_t6['trade_type'] == '現物')].copy()
                margin_jp_t6 = df_positions_t6[(df_positions_t6['market'] == '日本株') & (df_positions_t6['trade_type'] == '信用買')].copy()
                us_stocks_t6 = df_positions_t6[df_positions_t6['market'] == '米国株'].copy()

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
                        'ticker_code': 'コード', 'stock_name': '銘柄名',
                        'quantity': '数量', 'avg_price': '平均単価', 'total_cost': '総額'
                    }).reset_index(drop=True)
                    edited = st.data_editor(
                        display_df, use_container_width=True, num_rows="dynamic",
                        column_config={
                            "コード":   st.column_config.TextColumn("コード", width="small"),
                            "銘柄名":   st.column_config.TextColumn("銘柄名"),
                            "数量":     st.column_config.NumberColumn("数量", min_value=0, step=1, width="small"),
                            "平均単価": st.column_config.NumberColumn("平均単価", min_value=0, format="%.2f"),
                            "総額":     st.column_config.NumberColumn("総額", disabled=True),
                        },
                        key=f"editor_{tab_key}"
                    )
                    st.session_state[f"edited_{tab_key}"] = edited

                with pos_tab1:
                    render_editable_positions(spot_jp_t6, "spot_jp")
                with pos_tab2:
                    render_editable_positions(margin_jp_t6, "margin_jp")
                with pos_tab3:
                    render_editable_positions(us_stocks_t6, "us_stocks")

                st.divider()
                if st.button("💾 変更を保存", use_container_width=True, type="primary"):
                    save_rows = []
                    tab_configs = [
                        ("spot_jp",   "現物",  spot_jp_t6),
                        ("margin_jp", "信用買", margin_jp_t6),
                        ("us_stocks", "現物",  us_stocks_t6),
                    ]
                    for tab_key, trade_type_default, orig_df in tab_configs:
                        edited_df = st.session_state.get(f"edited_{tab_key}")
                        if edited_df is None:
                            continue
                        for _, erow in edited_df.iterrows():
                            code = str(erow.get("コード","")).strip()
                            if not code:
                                continue
                            orig_match    = orig_df[orig_df['ticker_code'] == code]
                            market_val    = orig_match.iloc[0]['market']    if len(orig_match) > 0 else erow.get("市場","日本株")
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
                        save_df = pd.DataFrame(save_rows)
                        if write_sheet(sheets_client, spreadsheet_id, 'manual_positions', save_df):
                            st.success("✅ 保存しました")
                            st.rerun()
                    else:
                        st.warning("保存するデータがありません")
            else:
                st.info("現在保有中のポジションはありません")

        # ========== タブ7: 設定 ==========
        with tab7:
            st.subheader("⚙️ 設定")
            st.subheader("根拠リストのカスタマイズ")
            reason_type = st.selectbox(
                "編集する根拠タイプ",
                ["entry_category", "entry_detail", "stop_loss", "exit_category", "exit_detail"],
                format_func=lambda x: {
                    "entry_category": "エントリー種別",
                    "entry_detail":   "エントリー理由",
                    "stop_loss":      "損切り理由",
                    "exit_category":  "決済種別",
                    "exit_detail":    "決済理由"
                }[x]
            )

            df_reasons_t7 = get_reason_list(sheets_client, spreadsheet_id, reason_type)
            if len(df_reasons_t7) > 0:
                st.dataframe(df_reasons_t7, use_container_width=True)

            with st.expander("➕ 新規追加"):
                new_category = st.text_input("カテゴリ")
                new_detail   = st.text_input("詳細")
                if st.button("追加", use_container_width=True):
                    if new_category and new_detail:
                        new_row = {
                            'reason_type': reason_type, 'category': new_category,
                            'detail': new_detail, 'is_active': 1,
                            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        df_all_reasons = read_sheet(sheets_client, spreadsheet_id, 'reason_definitions')
                        if len(df_all_reasons) == 0:
                            df_all_reasons = pd.DataFrame([new_row])
                            write_sheet(sheets_client, spreadsheet_id, 'reason_definitions', df_all_reasons)
                        else:
                            append_to_sheet(sheets_client, spreadsheet_id, 'reason_definitions', new_row)
                        st.success("✅ 追加しました")
                        st.rerun()

            st.divider()
            st.subheader("データ管理")
            if st.button("🗑 全データをリセット", use_container_width=True):
                if st.checkbox("本当にリセットしますか？（取消不可）"):
                    for sheet_name, cols in [
                        ('trades', ['trade_date','settlement_date','market','ticker_code','stock_name',
                                    'account_type','trade_type','trade_action','quantity','price',
                                    'commission','tax','total_amount','exchange_rate','currency','created_at']),
                        ('active_trades', ['ticker_code','stock_name','entry_date','entry_price','quantity',
                                           'entry_reason_category','entry_reason_detail','stop_loss_price',
                                           'stop_loss_reason','notes','is_active','created_at']),
                        ('closed_trades', ['ticker_code','stock_name','entry_date','entry_price','exit_date',
                                           'exit_price','quantity','profit_loss','profit_loss_pct',
                                           'entry_reason_category','entry_reason_detail','exit_reason_category',
                                           'exit_reason_detail','stop_loss_price','max_profit','max_loss',
                                           'price_3days_later','price_1week_later','price_1month_later',
                                           'exit_evaluation','notes','created_at']),
                        ('trade_reasons', TRADE_REASONS_COLS),
                    ]:
                        write_sheet(sheets_client, spreadsheet_id, sheet_name, pd.DataFrame(columns=cols))
                    st.success("✅ データをリセットしました")
                    st.rerun()

            st.divider()
            st.subheader("接続情報")
            st.code(f"Spreadsheet ID: {spreadsheet_id}")
            st.caption("Railwayの環境変数 SPREADSHEET_ID に設定されているIDです")

        st.divider()
        st.caption("© 2026 トレード分析＆資金管理アプリ (Google Sheets版)")

    else:
        st.error("スプレッドシートIDの設定が必要です")

else:
    st.error("""
### ⚠️ Google Sheets認証が必要です

**Railwayの場合**、以下の環境変数を設定してください：

| 変数名 | 内容 |
|--------|------|
| `GCP_SERVICE_ACCOUNT_JSON` | サービスアカウントJSONファイルの中身（全文） |
| `SPREADSHEET_ID` | GoogleスプレッドシートのID |
""")
