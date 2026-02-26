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

# カスタムCSS（モバイルファースト）
st.markdown("""
<style>
.main .block-container {
    padding-top: 1rem;
    padding-bottom: 1rem;
    padding-left: 1rem;
    padding-right: 1rem;
    max-width: 100%;
}
.stButton button {
    width: 100%;
    height: 50px;
    font-size: 16px;
    margin: 5px 0;
}
.stTextInput input, .stNumberInput input, .stSelectbox select {
    height: 50px;
    font-size: 16px;
}
.stTabs [data-baseweb="tab-list"] button {
    font-size: 16px;
    padding: 15px;
}
.metric-card {
    background-color: #f0f2f6;
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
}
.dataframe {
    font-size: 14px;
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

def init_spreadsheet(sheets_client, spreadsheet_id):
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

def calculate_position_summary(df):
    """保有ポジションの計算

    数量計算: 単純集計（買付+現引-売付、買建-売埋-現引）
    平均取得単価: 買付のみの加重平均（現引は建単価、priceが0なら信用買建の加重平均を使用）
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

    summary = []

    for ticker in df['ticker_code'].unique():
        r = df[df['ticker_code'] == ticker]

        name_rows = r[r['stock_name'].notna() & (r['stock_name'] != '')]
        stock_name = name_rows.iloc[0]['stock_name'] if len(name_rows) > 0 else ticker
        market = name_rows.iloc[0]['market'] if len(name_rows) > 0 else '日本株'

        # ===== 数量計算（単純集計）=====
        kenin_qty = r[r['account_type'] == '現引']['quantity'].sum()

        if market == '米国株':
            buy_qty  = r[r['trade_action'] == '買付']['quantity'].sum()
            sell_qty = r[r['trade_action'] == '売付']['quantity'].sum()
        else:
            spot = r[r['account_type'] == '現物']
            buy_qty  = spot[spot['trade_action'] == '買付']['quantity'].sum()
            sell_qty = spot[spot['trade_action'] == '売付']['quantity'].sum()
            buy_qty += r[r['trade_action'] == '入庫']['quantity'].sum()

        spot_remaining = buy_qty + kenin_qty - sell_qty

        mbuy_qty  = r[r['trade_action'] == '買建']['quantity'].sum()
        msell_qty = r[r['trade_action'] == '売埋']['quantity'].sum()
        margin_remaining = mbuy_qty - msell_qty - kenin_qty

        # ===== 現物の平均取得単価 =====
        if spot_remaining > 0:
            if market == '米国株':
                buy_rows = r[r['trade_action'] == '買付']
            else:
                buy_rows = r[(r['account_type'] == '現物') & (r['trade_action'] == '買付')]

            if buy_rows['quantity'].sum() > 0:
                # 買付のみの加重平均
                avg_price = (buy_rows['price'] * buy_rows['quantity']).sum() / buy_rows['quantity'].sum()
            else:
                # 買付なし（現引のみで現物になった）→ 信用買建の加重平均を使用
                mbuy_rows = r[r['trade_action'] == '買建']
                if mbuy_rows['quantity'].sum() > 0:
                    avg_price = (mbuy_rows['price'] * mbuy_rows['quantity']).sum() / mbuy_rows['quantity'].sum()
                else:
                    avg_price = 0
            summary.append({
                'ticker_code': ticker,
                'stock_name': stock_name,
                'market': market,
                'trade_type': '現物',
                'quantity': int(spot_remaining),
                'avg_price': round(avg_price, 2),
                'total_cost': round(avg_price * spot_remaining, 0)
            })

        # ===== 信用の平均取得単価 =====
        if margin_remaining > 0:
            mbuy_rows = r[r['trade_action'] == '買建']
            if mbuy_rows['quantity'].sum() > 0:
                avg_price = (mbuy_rows['price'] * mbuy_rows['quantity']).sum() / mbuy_rows['quantity'].sum()
            else:
                avg_price = 0
            summary.append({
                'ticker_code': ticker,
                'stock_name': stock_name,
                'market': market,
                'trade_type': '信用買',
                'quantity': int(margin_remaining),
                'avg_price': round(avg_price, 2),
                'total_cost': round(avg_price * margin_remaining, 0)
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

        st.title("📊 トレード分析＆資金管理")
        st.caption("🔗 Google Sheets連携版")

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📥 データ管理",
            "💰 資金管理",
            "📈 アクティブ",
            "📊 分析",
            "⚙️ 設定"
        ])

        # ========== タブ1: データ管理 ==========
        with tab1:
            st.header("データ管理")

            # ===== 推奨：全件差し替えインポート =====
            st.subheader("📥 CSVインポート（推奨：全件差し替え）")
            st.info(
                "**使い方：** トレードのたびに楽天証券から「全期間」のCSVをダウンロードし、"
                "日本株・米国株の両方をアップロードして「全件差し替えインポート」を押してください。"
                "スプレッドシートの取引データを最新CSVで丸ごと上書きします（重複しません）。"
            )
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
                st.warning("⚠️ 「全件差し替えインポート」を押すと、既存の取引データがすべて上書きされます。")
                if st.button("🔄 全件差し替えインポート（推奨）", use_container_width=True, type="primary"):
                    with st.spinner('インポート中...'):
                        parts = []
                        if jp_file:
                            parts.append(parse_jp_csv(df_jp))
                        if us_file:
                            parts.append(parse_us_csv(df_us))
                        combined = pd.concat(parts, ignore_index=True) if len(parts) > 1 else parts[0]
                        if write_sheet(sheets_client, spreadsheet_id, 'trades', combined, clear_first=True):
                            st.success(f"✅ {len(combined)}件をインポートしました（既存データを上書き）")
                            st.rerun()

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
                st.info(f"総件数: {len(df_all)}件")
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

                # ② 最新の約定日から降順に並び替え
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

            st.divider()
            st.subheader("📦 保有ポジション")

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
                    # 集計サマリー
                    st.markdown("**account_type / trade_action の組み合わせ一覧:**")
                    st.dataframe(
                        debug_r.groupby(["account_type","trade_action"], dropna=False)["quantity"].sum().reset_index(),
                        use_container_width=True
                    )
                    # ポジション計算のデバッグ
                    from io import StringIO
                    import sys
                    spot_r = debug_r[
                        (debug_r["account_type"] == "現物") |
                        (debug_r["trade_action"] == "入庫") |
                        (debug_r["account_type"] == "現引")
                    ].sort_values("trade_date")
                    st.markdown("**現物計算対象行:**")
                    st.dataframe(spot_r[["trade_date","account_type","trade_action","quantity","price"]], use_container_width=True)
                    margin_r = debug_r[debug_r["trade_action"].isin(["買建","売埋"]) | (debug_r["account_type"] == "現引")].sort_values("trade_date")
                    st.markdown("**信用計算対象行:**")
                    st.dataframe(margin_r[["trade_date","account_type","trade_action","quantity","price"]], use_container_width=True)

            df_positions = calculate_position_summary(df_all)

            # デバッグ：全銘柄の残数量チェック（68件問題の調査）
            if len(df_all) > 0:
                with st.expander("🔍 デバッグ2：全銘柄の残数量チェック"):
                    all_tickers = sorted(df_all["ticker_code"].unique().tolist())
                    check_rows = []
                    for t in all_tickers:
                        r = df_all[df_all["ticker_code"] == t]
                        buy = r[r["trade_action"] == "買付"]["quantity"].sum()
                        sell = r[r["trade_action"] == "売付"]["quantity"].sum()
                        kenin = r[r["account_type"] == "現引"]["quantity"].sum()
                        mbuy = r[r["trade_action"] == "買建"]["quantity"].sum()
                        msell = r[r["trade_action"] == "売埋"]["quantity"].sum()
                        spot_rem = buy + kenin - sell
                        margin_rem = mbuy - msell - kenin
                        check_rows.append({
                            "コード": t,
                            "現物買付": int(buy), "現物売付": int(sell), "現引": int(kenin),
                            "現物残": int(spot_rem),
                            "買建": int(mbuy), "売埋": int(msell),
                            "信用残": int(margin_rem)
                        })
                    check_df = pd.DataFrame(check_rows)
                    # 残があるものだけ表示
                    has_position = check_df[(check_df["現物残"] > 0) | (check_df["信用残"] > 0)]
                    st.write(f"残あり銘柄数: {len(has_position)}")
                    st.dataframe(has_position, use_container_width=True)

            if len(df_positions) > 0:
                total_count = len(df_positions)
                st.info(f"保有銘柄数: {total_count}件")

                # ① 日本株現物／日本株信用／米国株 の3タブに分けて表示
                spot_jp    = df_positions[(df_positions['market'] == '日本株') & (df_positions['trade_type'] == '現物')]
                margin_jp  = df_positions[(df_positions['market'] == '日本株') & (df_positions['trade_type'] == '信用買')]
                us_stocks  = df_positions[df_positions['market'] == '米国株']

                col_rename = {
                    'ticker_code': 'コード',
                    'stock_name': '銘柄名',
                    'market': '市場',
                    'trade_type': '種別',
                    'quantity': '保有数量',
                    'avg_price': '平均取得単価',
                    'total_cost': '総額'
                }

                pos_tab1, pos_tab2, pos_tab3 = st.tabs([
                    f"🇯🇵 日本株（現物）{len(spot_jp)}件",
                    f"📊 日本株（信用）{len(margin_jp)}件",
                    f"🇺🇸 米国株 {len(us_stocks)}件"
                ])

                with pos_tab1:
                    if len(spot_jp) > 0:
                        st.dataframe(
                            spot_jp.rename(columns=col_rename).reset_index(drop=True),
                            use_container_width=True
                        )
                    else:
                        st.info("日本株（現物）の保有はありません")

                with pos_tab2:
                    if len(margin_jp) > 0:
                        st.dataframe(
                            margin_jp.rename(columns=col_rename).reset_index(drop=True),
                            use_container_width=True
                        )
                    else:
                        st.info("日本株（信用）の保有はありません")

                with pos_tab3:
                    if len(us_stocks) > 0:
                        st.dataframe(
                            us_stocks.rename(columns=col_rename).reset_index(drop=True),
                            use_container_width=True
                        )
                    else:
                        st.info("米国株の保有はありません")

            else:
                st.info("現在保有中のポジションはありません")
            if len(df_all) == 0:
                st.info("データがありません。CSVファイルをインポートしてください。")

        # ========== タブ2: 資金管理 ==========
        with tab2:
            st.header("💰 資金管理ダッシュボード")
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

        # ========== タブ3: アクティブトレード ==========
        with tab3:
            st.header("📈 アクティブトレード管理")

            with st.expander("➕ 新規ポジション登録", expanded=False):
                entry_ticker = st.text_input("銘柄コード", key="entry_ticker")
                entry_name = st.text_input("銘柄名", key="entry_name")
                col1, col2 = st.columns(2)
                with col1:
                    entry_date = st.date_input("エントリー日", key="entry_date")
                    entry_price = st.number_input("エントリー価格", min_value=0.0, step=0.01,
                                                  key="entry_price")
                with col2:
                    entry_qty = st.number_input("数量", min_value=1, step=1, key="entry_qty")
                    stop_loss_price = st.number_input("損切り価格", min_value=0.0, step=0.01,
                                                      key="stop_loss_price")

                st.subheader("エントリー根拠")
                entry_categories = get_reason_list(sheets_client, spreadsheet_id, 'entry_category')
                if len(entry_categories) > 0:
                    entry_category = st.selectbox("種別", entry_categories['detail'].tolist(),
                                                  key="entry_cat")
                else:
                    entry_category = st.text_input("種別", key="entry_cat")

                entry_details = get_reason_list(sheets_client, spreadsheet_id, 'entry_detail')
                if len(entry_details) > 0:
                    entry_groups = entry_details.groupby('category')['detail'].apply(list).to_dict()
                    if len(entry_groups) > 0:
                        entry_group = st.selectbox("理由カテゴリ", list(entry_groups.keys()),
                                                   key="entry_group")
                        entry_detail = st.selectbox("理由詳細", entry_groups[entry_group],
                                                    key="entry_detail")
                    else:
                        entry_group = st.text_input("理由カテゴリ", key="entry_group")
                        entry_detail = st.text_input("理由詳細", key="entry_detail")
                else:
                    entry_group = st.text_input("理由カテゴリ", key="entry_group")
                    entry_detail = st.text_input("理由詳細", key="entry_detail")

                stop_loss_reasons = get_reason_list(sheets_client, spreadsheet_id, 'stop_loss')
                if len(stop_loss_reasons) > 0:
                    stop_loss_reason = st.selectbox("損切り根拠", stop_loss_reasons['detail'].tolist(),
                                                    key="sl_reason")
                else:
                    stop_loss_reason = st.text_input("損切り根拠", key="sl_reason")

                entry_notes = st.text_area("メモ", key="entry_notes")

                if st.button("✅ 登録する", use_container_width=True, key="save_entry"):
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
                        df_active = read_sheet(sheets_client, spreadsheet_id, 'active_trades')
                        if len(df_active) == 0:
                            df_active = pd.DataFrame([new_row])
                            write_sheet(sheets_client, spreadsheet_id, 'active_trades', df_active)
                        else:
                            append_to_sheet(sheets_client, spreadsheet_id, 'active_trades', new_row)
                        st.success("✅ 登録しました")
                        st.rerun()
                    else:
                        st.error("必須項目を入力してください")

            st.divider()
            st.subheader("保有中のポジション")
            df_active = read_sheet(sheets_client, spreadsheet_id, 'active_trades')
            if len(df_active) > 0:
                df_active = df_active[df_active['is_active'] == '1']
                for idx, row in df_active.iterrows():
                    with st.container():
                        col1, col2, col3 = st.columns([2, 2, 1])
                        with col1:
                            st.markdown(f"**{row['ticker_code']}** {row['stock_name']}")
                            st.caption(f"エントリー: {row['entry_date']} @ ¥{float(row['entry_price']):,.2f}")
                        with col2:
                            st.metric("数量", f"{row['quantity']}株")
                            st.caption(f"損切: ¥{float(row['stop_loss_price']):,.2f}")
                        with col3:
                            if st.button("決済", key=f"close_{idx}", use_container_width=True):
                                st.session_state[f"closing_{idx}"] = True
                                st.rerun()

                        with st.expander("詳細"):
                            st.write(f"**エントリー根拠:** {row['entry_reason_category']} - {row['entry_reason_detail']}")
                            st.write(f"**損切り理由:** {row['stop_loss_reason']}")
                            if row.get('notes'):
                                st.write(f"**メモ:** {row['notes']}")

                        if st.session_state.get(f"closing_{idx}", False):
                            with st.form(f"close_form_{idx}"):
                                st.subheader("決済入力")
                                col1, col2 = st.columns(2)
                                with col1:
                                    exit_date = st.date_input("決済日", value=datetime.now())
                                    exit_price = st.number_input("決済価格", min_value=0.0, step=0.01,
                                                                 value=float(row['entry_price']))
                                with col2:
                                    max_profit = st.number_input("最大含み益", value=0.0, step=0.01)
                                    max_loss = st.number_input("最大含み損", value=0.0, step=0.01)

                                exit_categories = get_reason_list(sheets_client, spreadsheet_id, 'exit_category')
                                if len(exit_categories) > 0:
                                    exit_category = st.selectbox("決済種別", exit_categories['detail'].tolist())
                                else:
                                    exit_category = st.text_input("決済種別")

                                exit_details = get_reason_list(sheets_client, spreadsheet_id, 'exit_detail')
                                if len(exit_details) > 0:
                                    exit_groups = exit_details.groupby('category')['detail'].apply(list).to_dict()
                                    if len(exit_groups) > 0:
                                        exit_group = st.selectbox("決済理由カテゴリ", list(exit_groups.keys()))
                                        exit_detail = st.selectbox("決済理由詳細", exit_groups[exit_group])
                                    else:
                                        exit_group = st.text_input("決済理由カテゴリ")
                                        exit_detail = st.text_input("決済理由詳細")
                                else:
                                    exit_group = st.text_input("決済理由カテゴリ")
                                    exit_detail = st.text_input("決済理由詳細")

                                close_notes = st.text_area("決済メモ")
                                col1, col2 = st.columns(2)
                                with col1:
                                    submit = st.form_submit_button("✅ 決済完了", use_container_width=True)
                                with col2:
                                    cancel = st.form_submit_button("❌ キャンセル", use_container_width=True)

                                if submit and exit_price > 0:
                                    profit_loss = (exit_price - float(row['entry_price'])) * float(row['quantity'])
                                    profit_loss_pct = ((exit_price - float(row['entry_price'])) /
                                                       float(row['entry_price'])) * 100
                                    closed_row = {
                                        'ticker_code': row['ticker_code'],
                                        'stock_name': row['stock_name'],
                                        'entry_date': row['entry_date'],
                                        'entry_price': row['entry_price'],
                                        'exit_date': str(exit_date),
                                        'exit_price': exit_price,
                                        'quantity': row['quantity'],
                                        'profit_loss': profit_loss,
                                        'profit_loss_pct': profit_loss_pct,
                                        'entry_reason_category': row['entry_reason_category'],
                                        'entry_reason_detail': row['entry_reason_detail'],
                                        'exit_reason_category': exit_category,
                                        'exit_reason_detail': f"{exit_group}/{exit_detail}",
                                        'stop_loss_price': row['stop_loss_price'],
                                        'max_profit': max_profit,
                                        'max_loss': max_loss,
                                        'price_3days_later': '',
                                        'price_1week_later': '',
                                        'price_1month_later': '',
                                        'exit_evaluation': '',
                                        'notes': f"{row.get('notes', '')}\n決済メモ: {close_notes}" if close_notes else row.get('notes', ''),
                                        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    }
                                    df_closed_sheet = read_sheet(sheets_client, spreadsheet_id, 'closed_trades')
                                    if len(df_closed_sheet) == 0:
                                        df_closed_sheet = pd.DataFrame([closed_row])
                                        write_sheet(sheets_client, spreadsheet_id, 'closed_trades', df_closed_sheet)
                                    else:
                                        append_to_sheet(sheets_client, spreadsheet_id, 'closed_trades', closed_row)
                                    df_active.loc[idx, 'is_active'] = 0
                                    write_sheet(sheets_client, spreadsheet_id, 'active_trades', df_active)
                                    st.success(f"✅ 決済完了 損益: ¥{profit_loss:,.0f} ({profit_loss_pct:+.2f}%)")
                                    del st.session_state[f"closing_{idx}"]
                                    st.rerun()

                                if cancel:
                                    del st.session_state[f"closing_{idx}"]
                                    st.rerun()

            st.divider()
            if len(df_active) == 0:
                st.info("アクティブなポジションはありません")

        # ========== タブ4: 分析 ==========
        with tab4:
            st.header("📊 トレード分析")
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

        # ========== タブ5: 設定 ==========
        with tab5:
            st.header("⚙️ 設定")
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
                            append_to_sheet(sheets_client, spreadsheet_id, 'reason_definitions', new_row)
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
