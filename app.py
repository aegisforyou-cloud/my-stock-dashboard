import streamlit as st
import pandas as pd
import yfinance as yf
import sqlite3
from datetime import datetime
import plotly.express as px

# --- 1. 데이터베이스 설정 ---
def init_db():
    conn = sqlite3.connect('assets.db')
    c = conn.cursor()
    # 보유 종목 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS holdings 
                 (ticker TEXT PRIMARY KEY, quantity REAL, avg_price REAL)''')
    # 자산 이력 테이블 (일별 스냅샷)
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (date TEXT, total_value REAL, daily_pnl REAL)''')
    conn.commit()
    return conn

# --- 2. 핵심 로직: 시세 가져오기 및 계산 ---
# 메인 화면: 포트폴리오 현황
import streamlit as st
import pandas as pd
import yfinance as yf
import sqlite3
from datetime import datetime
import plotly.express as px

# --- 1. 데이터베이스 설정 ---
def init_db():
    conn = sqlite3.connect('assets.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS holdings 
                 (ticker TEXT PRIMARY KEY, quantity REAL, avg_price REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (date TEXT, total_value REAL, daily_pnl REAL)''')
    conn.commit()
    return conn

# --- 2. 핵심 로직: 시세 가져오기 (NameError 방지를 위해 위치 고정) ---
def get_current_data(holdings_df):
    if holdings_df.empty:
        return None
    
    tickers = holdings_df['ticker'].tolist()
    try:
        # 주말이나 공휴일을 대비해 7일치 데이터를 가져옵니다.
        data = yf.download(tickers, period="7d", interval="1d")['Close']
        
        if data.empty:
            return None

        # 마지막으로 유효한 가격 추출
        if len(tickers) == 1:
            last_price = data.dropna().iloc[-1]
            current_prices = {tickers[0]: last_price}
        else:
            last_prices = data.ffill().iloc[-1]
            current_prices = last_prices.to_dict()
        
        # 데이터 계산
        df = holdings_df.copy()
        df['current_price'] = df['ticker'].map(current_prices)
        df['total_value'] = df['quantity'] * df['current_price']
        df['investment'] = df['quantity'] * df['avg_price']
        df['pnl'] = df['total_value'] - df['investment']
        df['roi'] = (df['pnl'] / df['investment']) * 100 if df['investment'].sum() > 0 else 0
        return df
    except Exception as e:
        st.error(f"데이터를 가져오는 중 오류 발생: {e}")
        return None

# --- 3. UI 구성 ---
def main():
    st.set_page_config(page_title="My Stock Dashboard", layout="wide")
    st.title("📈 개인용 주식 자산 관리 대시보드")
    
    conn = init_db()
    
    # 사이드바: 입력 및 삭제
    st.sidebar.header("📥 데이터 관리")
    with st.sidebar.form("input_form"):
        ticker = st.text_input("종목명 (예: 005930.KS, TSLA)").upper().strip()
        qty = st.number_input("보유 수량", min_value=0.0)
        price = st.number_input("평균 취득 단가", min_value=0.0)
        submit = st.form_submit_button("추가/수정")
        
        if submit and ticker:
            conn.execute("INSERT OR REPLACE INTO holdings VALUES (?, ?, ?)", (ticker, qty, price))
            conn.commit()
            st.rerun()

    if st.sidebar.button("🗑️ 전체 데이터 초기화"):
        conn.execute("DELETE FROM holdings")
        conn.commit()
        st.rerun()

    # 메인 화면
    holdings_df = pd.read_sql("SELECT * FROM holdings", conn)
    
    if not holdings_df.empty:
        df = get_current_data(holdings_df)
        
        if df is not None:
            # 상단 지표
            total_inv = df['investment'].sum()
            total_val = df['total_value'].sum()
            total_pnl = df['pnl'].sum()
            total_roi = (total_pnl / total_inv) * 100 if total_inv > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            col1.metric("총 투자금", f"{total_inv:,.0f}원")
            col2.metric("현재 자산 가치", f"{total_val:,.0f}원", f"{total_pnl:,.0f}원")
            col3.metric("전체 수익률", f"{total_roi:.2f}%")

            # 상세 테이블
            st.subheader("📝 종목별 상세 현황")
            st.dataframe(df.style.format({
                'avg_price': '{:,.0f}', 'current_price': '{:,.0f}', 
                'total_value': '{:,.0f}', 'pnl': '{:,.0f}', 'roi': '{:.2f}%'
            }), use_container_width=True)
            
            # 기록 저장
            if st.button("💾 현재 자산 상태 기록 저장"):
                today = datetime.now().strftime('%Y-%m-%d')
                conn.execute("INSERT INTO history (date, total_value, daily_pnl) VALUES (?, ?, ?)", 
                             (today, total_val, total_pnl))
                conn.commit()
                st.success("기록 완료!")
        else:
            st.warning("시세를 불러올 수 없습니다. 티커 형식을 확인해 주세요.")
    else:
        # 사이드바: 입력 및 삭제
    st.sidebar.header("📥 데이터 관리")
    
    # key="stock_input_form" 처럼 고유한 이름을 명시적으로 지정합니다.
    with st.sidebar.form(key="stock_input_form"):
        ticker = st.text_input("종목명 (예: 005930.KS, TSLA)").upper().strip()
        qty = st.number_input("보유 수량", min_value=0.0, step=1.0)
        price = st.number_input("평균 취득 단가", min_value=0.0, step=100.0)
        submit = st.form_submit_button("추가/수정")
        
        if submit and ticker:
            conn.execute("INSERT OR REPLACE INTO holdings VALUES (?, ?, ?)", (ticker, qty, price))
            conn.commit()
            st.rerun()

    # 자산 변화 차트
    history_df = pd.read_sql("SELECT * FROM history ORDER BY date", conn)
    if not history_df.empty:
        st.subheader("📉 자산 성장 추이")
        fig_line = px.line(history_df, x='date', y='total_value', markers=True)
        st.plotly_chart(fig_line, use_container_width=True)

if __name__ == "__main__":
    main()

# --- 3. UI 구성 (Streamlit) ---
def main():
    st.set_page_config(page_title="My Stock Dashboard", layout="wide")
    st.title("📈 개인용 주식 자산 관리 대시보드")
    
    conn = init_db()
    
    # 사이드바: 데이터 입력 인터페이스
    st.sidebar.header("📥 데이터 입력")
    with st.sidebar.form("input_form"):
        ticker = st.text_input("종목명 (예: 005930.KS, TSLA)").upper()
        qty = st.number_input("보유 수량", min_value=0.0)
        price = st.number_input("평균 취득 단가", min_value=0.0)
        submit = st.form_submit_button("포트폴리오 추가/수정")
        
        if submit and ticker:
            conn.execute("INSERT OR REPLACE INTO holdings VALUES (?, ?, ?)", (ticker, qty, price))
            conn.commit()
            st.success(f"{ticker} 저장 완료!")

    # 메인 화면: 포트폴리오 현황
    holdings_df = pd.read_sql("SELECT * FROM holdings", conn)
    
    if not holdings_df.empty:
        df = get_current_data(holdings_df)
        
        # 상단 지표 (Total Metrics)
        total_inv = df['investment'].sum()
        total_val = df['total_value'].sum()
        total_pnl = df['pnl'].sum()
        total_roi = (total_pnl / total_inv) * 100 if total_inv > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("총 투자금", f"{total_inv:,.0f}원")
        col2.metric("현재 자산 가치", f"{total_val:,.0f}원", f"{total_pnl:,.0f}원")
        col3.metric("전체 수익률", f"{total_roi:.2f}%")

        # 자산 구성 차트
        st.subheader("📊 포트폴리오 구성")
        fig_pie = px.pie(df, values='total_value', names='ticker', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

        # 상세 테이블
        st.subheader("📝 종목별 상세 현황")
        st.dataframe(df.style.format({
            'avg_price': '{:,.0f}', 'current_price': '{:,.0f}', 
            'total_value': '{:,.0f}', 'pnl': '{:,.0f}', 'roi': '{:.2f}%'
        }), use_container_width=True)
        
        # 기록 저장 버튼 (수동 스케줄링 시뮬레이션)
        if st.button("💾 현재 자산 상태 기록 저장 (장 마감 기록)"):
            today = datetime.now().strftime('%Y-%m-%d')
            conn.execute("INSERT INTO history (date, total_value, daily_pnl) VALUES (?, ?, ?)", 
                         (today, total_val, total_pnl))
            conn.commit()
            st.toast("기록이 성공적으로 저장되었습니다.")
            
    else:
        st.info("왼쪽 사이드바에서 종목을 추가해 주세요.")

    # 자산 변화 추이 그래프
    st.subheader("📉 자산 성장 추이")
    history_df = pd.read_sql("SELECT * FROM history ORDER BY date", conn)
    if not history_df.empty:
        fig_line = px.line(history_df, x='date', y='total_value', markers=True)
        st.plotly_chart(fig_line, use_container_width=True)

if __name__ == "__main__":
    main()
