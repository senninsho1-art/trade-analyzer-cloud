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
/* ===== 全体レイアウト ===== */
.main .block-container {
    padding-top: 0.5rem;
    padding-bottom: 1rem;
    padding-left: 0.75rem;
    padding-right: 0.75rem;
    max-width: 100%;
}

/* ===== タイトルを小さく ===== */
h1 {
    font-size: 1.2rem !important;
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
}
.stCaption {
    margin-top: 0 !important;
    font-size: 0.7rem !important;
}

/* ===== タブをスクロール時も上部固定 ===== */
/* メインタブ（最外側）のみ固定 */
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

/* ===== アクティブトレードカード ===== */
.trade-card {
    background-color: #1a1f2e;
    border: 1px solid #2d3348;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 10px;
}
.trade-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
}
.trade-ticker {
    font-size: 1.1rem;
    font-weight: bold;
    color: #fff;
}
.trade-name {
    font-size: 0.8rem;
    color: #aaa;
}
.trade-row {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-top: 4px;
}
.trade-item {
    text-align: center;
    min-width: 70px;
}
.trade-label {
    font-size: 0.68rem;
    color: #888;
}
.trade-value {
    font-size: 0.95rem;
    font-weight: 600;
    color: #e0e0e0;
}
.trade-value.profit { color: #00cc96; }
.trade-value.loss { color: #ef553b; }
.trade-value.neutral { color: #ffa500; }
.trade-reason {
    font-size: 0.72rem;
    color: #777;
    margin-top: 6px;
    border-top: 1px solid #2d3348;
    padding-top: 4px;
}

/* ===== ボタン ===== */
.stButton button {
    width: 100%;
    height: 48px;
    font-size: 15px;
    margin: 4px 0;
    border-radius: 8px;
}

/* ===== 入力フィールド ===== */
.stTextInput input, .stNumberInput input {
    height: 46px;
    font-size: 15px;
}

/* ===== データテーブル ===== */
.dataframe {
    font-size: 13px;
}

/* ===== 最終インポート日時の小さいテキスト ===== */
.import-date {
    font-size: 0.72rem;
    color: #888;
    margin-top: 4px;
    text-align: center;
}

/* ===== セクションヘッダーをコンパクトに ===== */
h2 {
    font-size: 1.1rem !important;
}
h3 {
    font-size: 1.0rem !important;
}
</style>
""", unsafe_allow_html=True)

# Google Sheets接続設定
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_google_sheets_client():
    try:
        gcp_json_str = os.environ.get("GCP_SERVICE_ACCOUNT_JSON", "")
        if gcp_json_str:
            service_account_info = json.loads(gcp_json_str)
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=SCOPES
            )
            service = build('sheets', 'v4', credentials=credentials)
            return service.spreadsheets()

        if hasattr(st, 'secrets') and "gcp_service_account" in st.secrets:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=SCOPES
            )
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
                {'properties': {'title': 'reason_definitions'}}
            ]
        }
        try:
            result = sheets_client.create(body=spreadsheet).execute()
            new_id = result['spreadsheetId']
            st.success(f"✅ スプレッドシート作成完了！")
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
    """シートが存在しない場合は新規作成する"""
    try:
        result = sheets_client.get(spreadsheetId=spreadsheet_id).execute()
        existing = [s['properties']['title'] for s in result.get('sheets', [])]
        if sheet_name not in existing:
            body = {'requests': [{'addSheet': {'properties': {'title': sheet_name}}}]}
            sheets_client.batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
    except Exception as e:
        pass  # エラーは無視（既存シートへの書き込みは通常通り動作）

def init_spreadsheet(sheets_client, spreadsheet_id):
    # manual_positionsシートを確実に作成
    ensure_sheet_exists(sheets_client, spreadsheet_id, 'manual_positions')

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
        reason_df = pd.DataFrame(initial_reasons, columns=[
            'reason_type', 'category', 'detail', 'is_active'
        ])
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
        'id': [1],
        'total_capital': [total_capital],
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

def parse_jp_csv(df):
    numeric_columns = ['数量［株］', '単価［円］', '手数料［円］', '税金等［円］', '受渡金額［円］']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '').str.strip()
            df[col] = df[col].replace({'-': None, '': None, 'nan': None})
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    parsed = pd.DataFrame({
        'trade_date': pd.to_datetime(df['約定日'], format='%Y/%m/%d').dt.strftime('%Y-%m-%d'),
        'settlement_date': pd.to_datetime(df['受渡日'], format='%Y/%m/%d',
                                          errors='coerce').dt.strftime('%Y-%m-%d'),
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
        'settlement_date': pd.to_datetime(df['受渡日'], format='%Y/%m/%d',
                                          errors='coerce').dt.strftime('%Y-%m-%d'),
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

def load_all_trades(sheets_client, spreadsheet_id):
    df = read_sheet(sheets_client, spreadsheet_id, 'trades')
    if len(df) > 0:
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        numeric_cols = ['quantity', 'price', 'commission', 'tax', 'total_amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        # ticker_codeを文字列に統一（スプレッドシートから3179.0のような形で来る場合の対策）
        if 'ticker_code' in df.columns:
            df['ticker_code'] = df['ticker_code'].astype(str).str.strip()
            # "3179.0" → "3179" に変換
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
    """
    移動平均法で平均取得単価のみを計算。
    全売りしたら avg をリセット → その後の買付から再計算（楽天証券方式）。
    数量計算はこの関数では行わない（単純集計で別途算出）。
    """
    qty = 0.0
    avg = 0.0
    for _, row in rows_sorted.iterrows():
        action = str(row.get('trade_action', ''))
        acct   = str(row.get('account_type', ''))
        q = float(row['quantity']) if not pd.isna(row['quantity']) else 0.0
        p = float(row['price']) if not pd.isna(row['price']) else 0.0
        is_kenin = (acct == '現引')

        if action in buy_actions:
            # 買付/入庫/買建：加重平均を更新
            total_cost = avg * qty + p * q
            qty += q
            avg = total_cost / qty if qty > 0 else 0.0

        elif is_kenin and not kenin_sell:
            # 現引（現物側）：建単価で加重平均を更新。price=0なら現在のavgを引き継ぐ
            effective_p = p if p > 0 else avg
            total_cost = avg * qty + effective_p * q
            qty += q
            avg = total_cost / qty if qty > 0 else 0.0

        elif action == sell_action or (is_kenin and kenin_sell):
            # 売付/売埋/現引（信用側）：数量を減らす。全売りでリセット
            qty -= q
            if qty <= 0:
                qty = 0.0
                avg = 0.0  # 全売りでリセット

    return avg


def calculate_position_summary(df):
    """
    保有ポジションの計算

    【数量】単純集計（デバッグ2と同じロジック）
      現物残（日本株）= 買付 + 入庫 + 現引 - 売付
      現物残（米国株）= 買付 + 現引 - 売付
      信用残          = 買建 - 売埋 - 現引

    【平均取得単価】移動平均法（全売りでリセット、楽天証券方式）

    ※ バグ修正ポイント（セッション3）:
      - spot_r フィルタを「現物側に関係する行のみ」に厳密化
        （旧: account_type=='現物' OR 入庫 OR 現引）
        （新: 現物買付・売付・入庫・現引 の行のみ）
      - margin_r フィルタを「信用側に関係する行のみ」に厳密化
        （旧: 買建 OR 売埋 OR 現引）
        （新: 買建・売埋 の行のみ ＋ 現引は信用側の減算用として含む）
      - kenin_qty 計算で account_type=='現引' かつ trade_action が '買建'/'売埋' でない行のみ対象
        （古いCSV形式で現引が誤って買建/売埋として記録されていたデータへの対策）
    """
    if len(df) == 0:
        return pd.DataFrame()

    df = df[df['trade_action'] != '売買区分'].copy()
    df = df[df['ticker_code'] != '銘柄コード']
    df = df[df['ticker_code'].notna() & (df['ticker_code'] != '')]

    df['quantity'] = pd.to_numeric(
        df['quantity'].astype(str).str.replace(',', '').str.strip(),
        errors='coerce'
    ).fillna(0)
    df['price'] = pd.to_numeric(
        df['price'].astype(str).str.replace(',', '').str.strip(),
        errors='coerce'
    ).fillna(0)

    df = df.sort_values('trade_date').reset_index(drop=True)

    summary = []

    for ticker in df['ticker_code'].unique():
        r = df[df['ticker_code'] == ticker]

        name_rows  = r[r['stock_name'].notna() & (r['stock_name'] != '')]
        stock_name = name_rows.iloc[0]['stock_name'] if len(name_rows) > 0 else ticker
        market     = name_rows.iloc[0]['market']     if len(name_rows) > 0 else '日本株'

        # ===== 数量：単純集計 =====
        # 現引は「account_type=='現引'」かつ「trade_action が 買建/売埋 でない」行のみ
        # （古い形式で現引が誤って買建/売埋として記録されていたデータを除外）
        kenin_rows = r[
            (r['account_type'] == '現引') &
            (~r['trade_action'].isin(['買建', '売埋']))
        ]
        kenin_qty = kenin_rows['quantity'].sum()

        if market == '米国株':
            buy_qty   = r[r['trade_action'] == '買付']['quantity'].sum()
            sell_qty  = r[r['trade_action'] == '売付']['quantity'].sum()
            nyuko_qty = 0
        else:
            # 日本株：account_type=='現物' の買付/売付のみカウント
            spot_rows  = r[r['account_type'] == '現物']
            buy_qty    = spot_rows[spot_rows['trade_action'] == '買付']['quantity'].sum()
            sell_qty   = spot_rows[spot_rows['trade_action'] == '売付']['quantity'].sum()
            nyuko_qty  = r[r['trade_action'] == '入庫']['quantity'].sum()

        spot_qty   = buy_qty + nyuko_qty + kenin_qty - sell_qty

        # 信用：買建/売埋のみ（account_type が '信用新規'/'信用返済' の行）
        mbuy_qty   = r[r['trade_action'] == '買建']['quantity'].sum()
        msell_qty  = r[r['trade_action'] == '売埋']['quantity'].sum()
        margin_qty = mbuy_qty - msell_qty - kenin_qty

        # ===== 平均取得単価：移動平均法 =====
        if spot_qty > 0:
            if market == '米国株':
                # 米国株：買付・売付のみ（現引があれば含める）
                spot_r = r[
                    r['trade_action'].isin(['買付', '売付']) |
                    ((r['account_type'] == '現引') & (~r['trade_action'].isin(['買建', '売埋'])))
                ].copy()
            else:
                # 日本株：現物の買付/売付・入庫・現引のみ
                spot_r = r[
                    ((r['account_type'] == '現物') & r['trade_action'].isin(['買付', '売付'])) |
                    (r['trade_action'] == '入庫') |
                    ((r['account_type'] == '現引') & (~r['trade_action'].isin(['買建', '売埋'])))
                ].copy()
            spot_avg = calc_avg_price(
                spot_r.sort_values('trade_date'),
                buy_actions=['買付', '入庫'],
                sell_action='売付',
                kenin_sell=False
            )
            summary.append({
                'ticker_code': ticker,
                'stock_name':  stock_name,
                'market':      market,
                'trade_type':  '現物',
                'quantity':    int(round(spot_qty)),
                'avg_price':   round(spot_avg, 2),
                'total_cost':  round(spot_avg * spot_qty, 0)
            })

        if margin_qty > 0:
            # 信用：買建/売埋のみ（現引は信用側の減算として含める）
            margin_r = r[
                r['trade_action'].isin(['買建', '売埋']) |
                ((r['account_type'] == '現引') & (~r['trade_action'].isin(['買建', '売埋'])))
            ].copy()
            margin_avg = calc_avg_price(
                margin_r.sort_values('trade_date'),
                buy_actions=['買建'],
                sell_action='売埋',
                kenin_sell=True
            )
            summary.append({
                'ticker_code': ticker,
                'stock_name':  stock_name,
                'market':      market,
                'trade_type':  '信用買',
                'quantity':    int(round(margin_qty)),
                'avg_price':   round(margin_avg, 2),
                'total_cost':  round(margin_avg * margin_qty, 0)
            })

    result = pd.DataFrame(summary)
    if len(result) > 0:
        result = result.sort_values('ticker_code').reset_index(drop=True)
    return result



# ==================== メイン ====================
sheets_client = get_google_sheets_client()
if sheets_client:
    spreadsheet_id = create_spreadsheet_if_needed(sheets_client)
    if spreadsheet_id:
        init_spreadsheet(sheets_client, spreadsheet_id)

        st.markdown("### 📊 トレード分析＆資金管理")

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📥 データ",
            "📦 ポジション",
            "💰 資金",
            "📈 アクティブ",
            "📊 分析",
            "⚙️ 設定"
        ])

        # ========== タブ1: データ管理 ==========
        with tab1:
            st.subheader("📥 CSVインポート")

            # 使い方をexpanderで折りたたみ
            with st.expander("📖 使い方を見る"):
                st.markdown(
                    "1. 楽天証券 → 取引履歴 → **全期間** でCSVダウンロード\n"
                    "2. 日本株・米国株の両方をアップロード\n"
                    "3. 「全件差し替えインポート」を押す\n\n"
                    "⚠️ **全期間**を選ばないと平均取得単価がずれます"
                )

            # 最終インポート日時を取得して表示
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
                if st.button("🔄 全件差し替えインポート", use_container_width=True, type="primary", disabled=True):
                    pass

            # 最終インポート日時を小さく表示
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
                        'trade_date': '約定日',
                        'market': '市場',
                        'ticker_code': 'コード',
                        'stock_name': '銘柄名',
                        'trade_action': '売買',
                        'quantity': '数量',
                        'price': '単価',
                        'total_amount': '金額'
                    }).reset_index(drop=True),
                    use_container_width=True,
                    height=400
                )
            else:
                st.info("データがありません。CSVファイルをインポートしてください。")

        # ========== タブ2: 保有ポジション ==========
        with tab2:
            st.subheader("📦 保有ポジション")

            # df_allがタブ1で読み込まれていない場合に備えて再取得
            if 'df_all' not in dir() or df_all is None:
                df_all = load_all_trades(sheets_client, spreadsheet_id)

            # デバッグ：銘柄別の生データ確認
            if len(df_all) > 0:
                with st.expander("🔍 デバッグ：銘柄別の取引生データ確認"):
                    debug_ticker = st.selectbox(
                        "確認する銘柄コード",
                        sorted(df_all["ticker_code"].unique().tolist()),
                        key="debug_ticker"
                    )
                    debug_r = df_all[df_all["ticker_code"] == debug_ticker].sort_values("trade_date")
                    st.dataframe(
                        debug_r[["trade_date","market","account_type","trade_type","trade_action","quantity","price"]],
                        use_container_width=True,
                        height=300
                    )
                    st.markdown("**account_type / trade_action の組み合わせ一覧:**")
                    st.dataframe(
                        debug_r.groupby(["account_type","trade_action"], dropna=False)["quantity"].sum().reset_index(),
                        use_container_width=True
                    )
                    spot_r = debug_r[
                        ((debug_r["account_type"] == "現物") & debug_r["trade_action"].isin(["買付", "売付"])) |
                        (debug_r["trade_action"] == "入庫") |
                        ((debug_r["account_type"] == "現引") & (~debug_r["trade_action"].isin(["買建", "売埋"])))
                    ].sort_values("trade_date")
                    st.markdown("**現物計算対象行:**")
                    st.dataframe(spot_r[["trade_date","account_type","trade_action","quantity","price"]], use_container_width=True)
                    margin_r = debug_r[
                        debug_r["trade_action"].isin(["買建","売埋"]) |
                        ((debug_r["account_type"] == "現引") & (~debug_r["trade_action"].isin(["買建", "売埋"])))
                    ].sort_values("trade_date")
                    st.markdown("**信用計算対象行:**")
                    st.dataframe(margin_r[["trade_date","account_type","trade_action","quantity","price"]], use_container_width=True)

            df_positions = calculate_position_summary(df_all)

            # デバッグ2：全銘柄の残数量チェック
            if len(df_all) > 0:
                with st.expander("🔍 デバッグ2：全銘柄の残数量チェック"):
                    all_tickers = sorted(df_all["ticker_code"].unique().tolist())
                    check_rows = []
                    for t in all_tickers:
                        r = df_all[df_all["ticker_code"] == t]
                        # 現引を正しく識別（account_type=='現引' かつ 買建/売埋でない）
                        kenin = r[
                            (r["account_type"] == "現引") &
                            (~r["trade_action"].isin(["買建", "売埋"]))
                        ]["quantity"].sum()
                        market_val = r.iloc[0]["market"] if len(r) > 0 else "日本株"
                        if market_val == '米国株':
                            buy = r[r["trade_action"] == "買付"]["quantity"].sum()
                            sell = r[r["trade_action"] == "売付"]["quantity"].sum()
                            nyuko = 0
                        else:
                            spot_rows = r[r["account_type"] == "現物"]
                            buy = spot_rows[spot_rows["trade_action"] == "買付"]["quantity"].sum()
                            sell = spot_rows[spot_rows["trade_action"] == "売付"]["quantity"].sum()
                            nyuko = r[r["trade_action"] == "入庫"]["quantity"].sum()
                        mbuy = r[r["trade_action"] == "買建"]["quantity"].sum()
                        msell = r[r["trade_action"] == "売埋"]["quantity"].sum()
                        spot_rem = buy + nyuko + kenin - sell
                        margin_rem = mbuy - msell - kenin
                        check_rows.append({
                            "コード": t,
                            "現物買付": int(buy), "入庫": int(nyuko), "現物売付": int(sell), "現引": int(kenin),
                            "現物残": int(round(spot_rem)),
                            "買建": int(mbuy), "売埋": int(msell),
                            "信用残": int(round(margin_rem))
                        })
                    check_df = pd.DataFrame(check_rows)
                    # 残があるものだけ表示
                    has_position = check_df[(check_df["現物残"] > 0) | (check_df["信用残"] > 0)]
                    st.write(f"残あり銘柄数: {len(has_position)}")
                    st.dataframe(has_position, use_container_width=True)

            # manual_positionsシートから手動上書きデータを読み込み
            manual_pos_df = read_sheet(sheets_client, spreadsheet_id, 'manual_positions')

            # CSVから計算したポジションに手動上書きをマージ
            if len(df_positions) > 0 and len(manual_pos_df) > 0:
                manual_pos_df['quantity'] = pd.to_numeric(manual_pos_df['quantity'], errors='coerce').fillna(0)
                manual_pos_df['avg_price'] = pd.to_numeric(manual_pos_df['avg_price'], errors='coerce').fillna(0)
                # ticker_code + trade_type をキーにして上書き
                for _, mrow in manual_pos_df.iterrows():
                    mask = (
                        (df_positions['ticker_code'] == mrow['ticker_code']) &
                        (df_positions['trade_type'] == mrow['trade_type'])
                    )
                    if mask.any():
                        if float(mrow['quantity']) <= 0:
                            # 数量0以下 → 削除
                            df_positions = df_positions[~mask]
                        else:
                            df_positions.loc[mask, 'quantity'] = int(mrow['quantity'])
                            df_positions.loc[mask, 'avg_price'] = float(mrow['avg_price'])
                            df_positions.loc[mask, 'total_cost'] = round(float(mrow['avg_price']) * float(mrow['quantity']), 0)
                    else:
                        # 新規行（手動追加）
                        if float(mrow['quantity']) > 0:
                            df_positions = pd.concat([df_positions, pd.DataFrame([{
                                'ticker_code': mrow['ticker_code'],
                                'stock_name': mrow.get('stock_name', mrow['ticker_code']),
                                'market': mrow.get('market', '日本株'),
                                'trade_type': mrow['trade_type'],
                                'quantity': int(mrow['quantity']),
                                'avg_price': float(mrow['avg_price']),
                                'total_cost': round(float(mrow['avg_price']) * float(mrow['quantity']), 0)
                            }])], ignore_index=True)
                df_positions = df_positions.sort_values('ticker_code').reset_index(drop=True)

            if len(df_positions) > 0:
                total_count = len(df_positions)
                st.caption(f"保有銘柄数: {total_count}件　💡 数量を0にすると削除")

                # 日本株現物／日本株信用／米国株 の3タブに分けて表示
                spot_jp   = df_positions[(df_positions['market'] == '日本株') & (df_positions['trade_type'] == '現物')].copy()
                margin_jp = df_positions[(df_positions['market'] == '日本株') & (df_positions['trade_type'] == '信用買')].copy()
                us_stocks = df_positions[df_positions['market'] == '米国株'].copy()

                pos_tab1, pos_tab2, pos_tab3 = st.tabs([
                    f"🇯🇵 現物 {len(spot_jp)}",
                    f"📊 信用 {len(margin_jp)}",
                    f"🇺🇸 米国 {len(us_stocks)}"
                ])

                def render_editable_positions(sub_df, tab_key):
                    if len(sub_df) == 0:
                        st.info("このカテゴリの保有はありません")
                        return
                    display_df = sub_df[['ticker_code','stock_name','quantity','avg_price','total_cost']].rename(columns={
                        'ticker_code': 'コード',
                        'stock_name': '銘柄名',
                        'quantity': '数量',
                        'avg_price': '平均単価',
                        'total_cost': '総額'
                    }).reset_index(drop=True)
                    edited = st.data_editor(
                        display_df,
                        use_container_width=True,
                        num_rows="dynamic",
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

                def render_margin_positions(sub_df):
                    """信用ポジション：楽天証券画面風にトレードごと表示 + アクティブ登録ボタン"""
                    if len(sub_df) == 0:
                        st.info("信用ポジションはありません")
                        return
                    # df_allから信用建玉の個別トレードを取得
                    margin_trades = df_all[df_all['trade_action'] == '買建'].copy()
                    # 売埋済みを除く（簡易：ticker_codeの信用残が0より多い銘柄のみ）
                    valid_tickers = sub_df['ticker_code'].tolist()
                    margin_trades = margin_trades[margin_trades['ticker_code'].isin(valid_tickers)]
                    margin_trades = margin_trades.sort_values(['ticker_code', 'trade_date'])

                    # 売埋数量を差し引いて残建玉を特定（FIFO簡易）
                    remaining_trades = []
                    for ticker in valid_tickers:
                        t_trades = margin_trades[margin_trades['ticker_code'] == ticker].copy()
                        sell_rows = df_all[(df_all['ticker_code'] == ticker) & (df_all['trade_action'] == '売埋')]
                        kenin_rows = df_all[(df_all['ticker_code'] == ticker) & (df_all['account_type'] == '現引')]
                        sold_qty = sell_rows['quantity'].sum() + kenin_rows['quantity'].sum()
                        # FIFOで古い建玉から消費
                        for _, tr in t_trades.iterrows():
                            if sold_qty <= 0:
                                remaining_trades.append(tr)
                            else:
                                q = float(tr['quantity'])
                                if sold_qty >= q:
                                    sold_qty -= q
                                else:
                                    tr_copy = tr.copy()
                                    tr_copy['quantity'] = q - sold_qty
                                    remaining_trades.append(tr_copy)
                                    sold_qty = 0

                    if not remaining_trades:
                        render_editable_positions(sub_df, "margin_jp")
                        return

                    remaining_df = pd.DataFrame(remaining_trades)
                    stock_names = dict(zip(df_all['ticker_code'], df_all['stock_name']))

                    # アクティブ登録用データをsession_stateに格納
                    for i, (_, tr) in enumerate(remaining_df.iterrows()):
                        ticker = str(tr['ticker_code'])
                        name = stock_names.get(ticker, ticker)
                        price = float(tr['price'])
                        qty = int(tr['quantity'])
                        date_str = str(tr['trade_date'])[:10] if pd.notna(tr['trade_date']) else ''

                        col_main, col_btn = st.columns([5, 1])
                        with col_main:
                            st.markdown(f"""
<div style="background:#1a1f2e;border:1px solid #2d3348;border-radius:8px;padding:10px 12px;margin-bottom:6px;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span style="font-size:1.05rem;font-weight:bold;color:#ffffff;">{ticker}　<span style="font-size:0.8rem;color:#cccccc;font-weight:normal;">{name}</span></span>
    <span style="font-size:0.8rem;color:#bbbbbb;">{date_str}</span>
  </div>
  <div style="display:flex;gap:20px;margin-top:6px;flex-wrap:wrap;">
    <div><div style="font-size:0.65rem;color:#aaaaaa;">建数量</div><div style="font-size:0.95rem;font-weight:700;color:#ffffff;">{qty}株</div></div>
    <div><div style="font-size:0.65rem;color:#aaaaaa;">建単価</div><div style="font-size:0.95rem;font-weight:700;color:#ffffff;">¥{price:,.1f}</div></div>
    <div><div style="font-size:0.65rem;color:#aaaaaa;">建玉金額</div><div style="font-size:0.95rem;font-weight:700;color:#ffffff;">¥{price*qty:,.0f}</div></div>
  </div>
</div>
""", unsafe_allow_html=True)
                        with col_btn:
                            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                            if st.button("📝", key=f"reg_active_{ticker}_{i}", help="アクティブ登録", use_container_width=True):
                                st.session_state['prefill_ticker'] = ticker
                                st.session_state['prefill_name'] = name
                                st.session_state['prefill_price'] = price
                                st.session_state['prefill_qty'] = qty
                                st.session_state['prefill_date'] = date_str
                                st.session_state['goto_active_register'] = True
                                st.rerun()

                    st.divider()
                    st.caption("💡 集計編集（数量・単価の手動修正）")
                    render_editable_positions(sub_df, "margin_jp")

                with pos_tab1:
                    render_editable_positions(spot_jp, "spot_jp")
                with pos_tab2:
                    render_margin_positions(margin_jp)
                with pos_tab3:
                    render_editable_positions(us_stocks, "us_stocks")

                st.divider()
                if st.button("💾 変更を保存", use_container_width=True, type="primary"):
                    # 3タブの編集結果を結合してmanual_positionsに保存
                    save_rows = []
                    tab_configs = [
                        ("spot_jp",   "現物",  spot_jp),
                        ("margin_jp", "信用買", margin_jp),
                        ("us_stocks", "現物",  us_stocks),
                    ]
                    for tab_key, trade_type_default, orig_df in tab_configs:
                        edited_df = st.session_state.get(f"edited_{tab_key}")
                        if edited_df is None:
                            continue
                        for _, erow in edited_df.iterrows():
                            code = str(erow.get("コード","")).strip()
                            if not code:
                                continue
                            # 元のデータから market/trade_type を取得
                            orig_match = orig_df[orig_df['ticker_code'] == code]
                            market_val    = orig_match.iloc[0]['market']    if len(orig_match) > 0 else erow.get("市場","日本株")
                            tradetype_val = orig_match.iloc[0]['trade_type'] if len(orig_match) > 0 else trade_type_default
                            save_rows.append({
                                'ticker_code': code,
                                'stock_name':  str(erow.get("銘柄名", code)),
                                'market':      market_val,
                                'trade_type':  tradetype_val,
                                'quantity':    float(erow.get("保有数量", 0)),
                                'avg_price':   float(erow.get("平均取得単価", 0)),
                                'updated_at':  datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                    if save_rows:
                        save_df = pd.DataFrame(save_rows)
                        if write_sheet(sheets_client, spreadsheet_id, 'manual_positions', save_df):
                            st.success("✅ 保存しました。ページを再読み込みすると反映されます。")
                            st.rerun()
                    else:
                        st.warning("保存するデータがありません")

            else:
                st.info("現在保有中のポジションはありません")
            if len(df_all) == 0:
                st.info("データがありません。CSVファイルをインポートしてください。")

        # ========== タブ3: 資金管理 ==========
        with tab3:
            st.subheader("💰 資金管理")
            settings = load_settings(sheets_client, spreadsheet_id)

            st.subheader("総資産設定")
            col1, col2 = st.columns([2, 1])
            with col1:
                total_capital = st.number_input(
                    "現在の総資産（円）",
                    min_value=0.0,
                    value=float(settings['total_capital']),
                    step=10000.0,
                    format="%.0f"
                )
            with col2:
                st.metric("総資産", f"¥{total_capital:,.0f}")

            st.subheader("リスク設定")
            risk_pct = st.slider(
                "1トレードの許容リスク（%）",
                min_value=0.1,
                max_value=5.0,
                value=float(settings['risk_per_trade_pct']),
                step=0.1,
                format="%.1f%%"
            )
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
                calc_ticker = st.text_input("銘柄コード", placeholder="例: 7203")
                calc_current_price = st.number_input("現在価格（円）", min_value=0.0, step=0.01,
                                                     format="%.2f")
            with col2:
                calc_stop_loss = st.number_input("損切り価格（円）", min_value=0.0, step=0.01,
                                                 format="%.2f")

            if calc_current_price > 0 and calc_stop_loss > 0 and calc_current_price > calc_stop_loss:
                loss_per_share = calc_current_price - calc_stop_loss
                max_shares = int(risk_amount / loss_per_share)
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

        # ========== タブ4: アクティブトレード ==========
        with tab4:
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
                    entry_price    = st.number_input("エントリー価格（円）", min_value=0.0, value=float(prefill.get('price', 0.0)), step=1.0, format="%.1f", key="entry_price")
                    entry_qty      = st.number_input("数量（株）", min_value=1, value=int(prefill.get('qty', 1)), step=1, key="entry_qty")
                    stop_loss_price = st.number_input("損切り価格（円）", min_value=0.0, step=1.0, format="%.1f", key="stop_loss_price")

                st.markdown("**エントリー根拠**")
                entry_categories = get_reason_list(sheets_client, spreadsheet_id, 'entry_category')
                col1, col2 = st.columns(2)
                with col1:
                    entry_category = st.selectbox("種別", entry_categories['detail'].tolist() if len(entry_categories) > 0 else [""], key="entry_cat")
                with col2:
                    entry_details = get_reason_list(sheets_client, spreadsheet_id, 'entry_detail')
                    if len(entry_details) > 0:
                        entry_groups = entry_details.groupby('category')['detail'].apply(list).to_dict()
                        entry_group  = st.selectbox("カテゴリ", list(entry_groups.keys()), key="entry_group")
                        entry_detail = st.selectbox("詳細", entry_groups[entry_group], key="entry_detail_sel")
                    else:
                        entry_group  = st.text_input("カテゴリ", key="entry_group")
                        entry_detail = st.text_input("詳細", key="entry_detail_sel")

                stop_loss_reasons = get_reason_list(sheets_client, spreadsheet_id, 'stop_loss')
                stop_loss_reason = st.selectbox("損切り根拠", stop_loss_reasons['detail'].tolist() if len(stop_loss_reasons) > 0 else [""], key="sl_reason")
                entry_notes = st.text_area("メモ", key="entry_notes", height=70)

                if st.button("✅ 登録する", use_container_width=True, type="primary", key="save_entry"):
                    if entry_ticker and entry_price > 0 and entry_qty > 0:
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

            # ===== アクティブトレード一覧（楽天証券風カード） =====
            df_active = read_sheet(sheets_client, spreadsheet_id, 'active_trades')
            if len(df_active) > 0:
                df_active = df_active[df_active['is_active'] == '1'].reset_index(drop=True)

            if len(df_active) == 0:
                st.info("アクティブなポジションはありません")
            else:
                st.caption(f"保有中: {len(df_active)}件")
                for idx, row in df_active.iterrows():
                    entry_p = float(row['entry_price'])
                    stop_p  = float(row['stop_loss_price']) if row.get('stop_loss_price') else 0.0
                    qty     = int(row['quantity'])
                    loss_per = entry_p - stop_p if stop_p > 0 else 0
                    max_loss = loss_per * qty

                    # カード本体
                    st.markdown(f"""
<div style="background:#1a1f2e;border:1px solid #2d3348;border-radius:10px;padding:12px 14px;margin-bottom:8px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
    <div>
      <span style="font-size:1.1rem;font-weight:bold;color:#ffffff;">{row['ticker_code']}</span>
      <span style="font-size:0.82rem;color:#cccccc;margin-left:8px;">{row['stock_name']}</span>
    </div>
    <span style="font-size:0.75rem;color:#bbbbbb;">{row['entry_date']}</span>
  </div>
  <div style="display:flex;gap:0;border:1px solid #3a3f55;border-radius:8px;overflow:hidden;text-align:center;">
    <div style="flex:1;padding:8px 4px;border-right:1px solid #3a3f55;">
      <div style="font-size:0.62rem;color:#aaaaaa;">建数量</div>
      <div style="font-size:1.0rem;font-weight:700;color:#ffffff;">{qty}<span style="font-size:0.65rem;color:#cccccc;">株</span></div>
    </div>
    <div style="flex:1.5;padding:8px 4px;border-right:1px solid #3a3f55;">
      <div style="font-size:0.62rem;color:#aaaaaa;">建単価</div>
      <div style="font-size:1.0rem;font-weight:700;color:#ffffff;">¥{entry_p:,.1f}</div>
    </div>
    <div style="flex:1.5;padding:8px 4px;border-right:1px solid #3a3f55;">
      <div style="font-size:0.62rem;color:#aaaaaa;">損切価格</div>
      <div style="font-size:1.0rem;font-weight:700;color:#ff8080;">¥{stop_p:,.1f}</div>
    </div>
    <div style="flex:1.5;padding:8px 4px;">
      <div style="font-size:0.62rem;color:#aaaaaa;">最大損失</div>
      <div style="font-size:1.0rem;font-weight:700;color:#ff6060;">¥{max_loss:,.0f}</div>
    </div>
  </div>
  <div style="font-size:0.7rem;color:#bbbbbb;margin-top:6px;border-top:1px solid #2d3348;padding-top:4px;">
    📌 {row['entry_reason_category']} / {row['entry_reason_detail']}　　✂️ {row['stop_loss_reason']}
  </div>
</div>
""", unsafe_allow_html=True)

                    # 決済ボタン
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

                            exit_categories = get_reason_list(sheets_client, spreadsheet_id, 'exit_category')
                            exit_category = st.selectbox("決済種別", exit_categories['detail'].tolist() if len(exit_categories) > 0 else [""])

                            exit_details = get_reason_list(sheets_client, spreadsheet_id, 'exit_detail')
                            if len(exit_details) > 0:
                                exit_groups = exit_details.groupby('category')['detail'].apply(list).to_dict()
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

        # ========== タブ5: 分析 ==========
        with tab5:
            st.subheader("📊 トレード分析")
            df_closed = read_sheet(sheets_client, spreadsheet_id, 'closed_trades')
            if len(df_closed) > 0:
                df_closed['entry_date'] = pd.to_datetime(df_closed['entry_date'])
                df_closed['exit_date'] = pd.to_datetime(df_closed['exit_date'])
                df_closed['hold_days'] = (df_closed['exit_date'] - df_closed['entry_date']).dt.days
                df_closed['profit_loss'] = pd.to_numeric(df_closed['profit_loss'], errors='coerce')
                df_closed['profit_loss_pct'] = pd.to_numeric(df_closed['profit_loss_pct'], errors='coerce')

                st.subheader("📈 パフォーマンスサマリー")
                col1, col2, col3, col4 = st.columns(4)
                total_trades = len(df_closed)
                winning_trades = len(df_closed[df_closed['profit_loss'] > 0])
                losing_trades = len(df_closed[df_closed['profit_loss'] < 0])
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

                with col1:
                    st.metric("総トレード数", total_trades)
                    st.metric("勝率", f"{win_rate:.1f}%")
                with col2:
                    total_profit = df_closed['profit_loss'].sum()
                    avg_profit = df_closed['profit_loss'].mean()
                    st.metric("総損益", f"¥{total_profit:,.0f}")
                    st.metric("平均損益", f"¥{avg_profit:,.0f}")
                with col3:
                    max_profit = df_closed['profit_loss'].max()
                    max_loss = df_closed['profit_loss'].min()
                    st.metric("最大利益", f"¥{max_profit:,.0f}")
                    st.metric("最大損失", f"¥{max_loss:,.0f}")
                with col4:
                    avg_win = df_closed[df_closed['profit_loss'] > 0]['profit_loss'].mean() if winning_trades > 0 else 0
                    avg_loss = abs(df_closed[df_closed['profit_loss'] < 0]['profit_loss'].mean()) if losing_trades > 0 else 0
                    pf = avg_win / avg_loss if avg_loss > 0 else 0
                    st.metric("PF", f"{pf:.2f}")
                    st.metric("平均保有日数", f"{df_closed['hold_days'].mean():.1f}日")

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
                    win_loss_data = pd.DataFrame({
                        '結果': ['勝ち', '負け'],
                        '件数': [winning_trades, losing_trades]
                    })
                    fig = px.pie(win_loss_data, values='件数', names='結果',
                                 title='勝敗分布',
                                 color='結果',
                                 color_discrete_map={'勝ち': '#00CC96', '負け': '#EF553B'})
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

                df_filtered = df_closed[
                    (df_closed['exit_date'] >= pd.Timestamp(date_from)) &
                    (df_closed['exit_date'] <= pd.Timestamp(date_to))
                ]
                display_cols = ['exit_date', 'ticker_code', 'stock_name', 'entry_price',
                                'exit_price', 'quantity', 'profit_loss', 'profit_loss_pct',
                                'entry_reason_category', 'exit_reason_category']
                st.dataframe(
                    df_filtered[display_cols].rename(columns={
                        'exit_date': '決済日',
                        'ticker_code': 'コード',
                        'stock_name': '銘柄名',
                        'entry_price': 'IN価格',
                        'exit_price': 'OUT価格',
                        'quantity': '数量',
                        'profit_loss': '損益',
                        'profit_loss_pct': '損益率%',
                        'entry_reason_category': 'IN根拠',
                        'exit_reason_category': 'OUT根拠'
                    }),
                    use_container_width=True,
                    height=400
                )
            else:
                st.info("決済済みトレードがありません")

        # ========== タブ6: 設定 ==========
        with tab6:
            st.subheader("⚙️ 設定")
            st.subheader("根拠リストのカスタマイズ")
            reason_type = st.selectbox(
                "編集する根拠タイプ",
                ["entry_category", "entry_detail", "stop_loss", "exit_category", "exit_detail"],
                format_func=lambda x: {
                    "entry_category": "エントリー種別",
                    "entry_detail": "エントリー理由",
                    "stop_loss": "損切り理由",
                    "exit_category": "決済種別",
                    "exit_detail": "決済理由"
                }[x]
            )

            df_reasons = get_reason_list(sheets_client, spreadsheet_id, reason_type)
            if len(df_reasons) > 0:
                st.dataframe(df_reasons, use_container_width=True)

            with st.expander("➕ 新規追加"):
                new_category = st.text_input("カテゴリ")
                new_detail = st.text_input("詳細")
                if st.button("追加", use_container_width=True):
                    if new_category and new_detail:
                        new_row = {
                            'reason_type': reason_type,
                            'category': new_category,
                            'detail': new_detail,
                            'is_active': 1,
                            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        df_all_reasons = read_sheet(sheets_client, spreadsheet_id, 'reason_definitions')
                        if len(df_all_reasons) == 0:
                            df_all_reasons = pd.DataFrame([new_row])
                            write_sheet(sheets_client, spreadsheet_id, 'reason_definitions', df_all_reasons)
                        else:
                            append_to_sheet(sheets_client, spreadsheet_id, 'closed_trades', new_row)
                        st.success("✅ 追加しました")
                        st.rerun()

            st.divider()
            st.subheader("データ管理")
            if st.button("🗑 全データをリセット", use_container_width=True):
                if st.checkbox("本当にリセットしますか？（取消不可）"):
                    write_sheet(sheets_client, spreadsheet_id, 'trades',
                                pd.DataFrame(columns=['trade_date', 'settlement_date', 'market', 'ticker_code',
                                                      'stock_name', 'account_type', 'trade_type', 'trade_action',
                                                      'quantity', 'price', 'commission', 'tax', 'total_amount',
                                                      'exchange_rate', 'currency', 'created_at']))
                    write_sheet(sheets_client, spreadsheet_id, 'active_trades',
                                pd.DataFrame(columns=['ticker_code', 'stock_name', 'entry_date', 'entry_price',
                                                      'quantity', 'entry_reason_category', 'entry_reason_detail',
                                                      'stop_loss_price', 'stop_loss_reason', 'notes',
                                                      'is_active', 'created_at']))
                    write_sheet(sheets_client, spreadsheet_id, 'closed_trades',
                                pd.DataFrame(columns=['ticker_code', 'stock_name', 'entry_date', 'entry_price',
                                                      'exit_date', 'exit_price', 'quantity', 'profit_loss',
                                                      'profit_loss_pct', 'entry_reason_category',
                                                      'entry_reason_detail', 'exit_reason_category',
                                                      'exit_reason_detail', 'stop_loss_price', 'max_profit',
                                                      'max_loss', 'price_3days_later', 'price_1week_later',
                                                      'price_1month_later', 'exit_evaluation', 'notes', 'created_at']))
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

詳細は `RAILWAY_DEPLOY.md` を参照してください。
""")
