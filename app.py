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
def get_current_data(holdings_df):
    if holdings_df.empty:
        return None
    
    tickers = holdings_df['ticker'].tolist()
    # 1. 데이터 가져오기 (시도가 실패할 경우를 대비해 기간을 5일로 넉넉히 잡음)
    data = yf.download(tickers, period="5d", interval="1d")['Close']
    
    # 2. 데이터가 완전히 비어있는지 체크
    if data.empty:
        st.error("⚠️ 주식 시세를 가져올 수 없습니다. 티커(종목코드)가 올바른지 확인해주세요.")
        return None
    
    # 3. 마지막 유효한 가격(NaN이 아닌 마지막 값) 가져오기
    if len(tickers) == 1:
        # 종목이 하나일 때
        last_price = data.dropna().iloc[-1]
        current_prices = {tickers[0]: last_price}
    else:
        # 종목이 여러 개일 때
        last_prices = data.ffill().iloc[-1] # ffill()로 빈칸을 채운 후 마지막 행 선택
        current_prices = last_prices.to_dict()
    
    # 4. 데이터 매핑
    holdings_df['current_price'] = holdings_df['ticker'].map(current_prices)
    
    # 가격을 못 가져온 종목이 있는지 체크
    if holdings_df['current_price'].isnull().any():
        bad_tickers = holdings_df[holdings_df['current_price'].isnull()]['ticker'].tolist()
        st.warning(f"⚠️ 다음 종목의 시세를 찾을 수 없습니다: {', '.join(bad_tickers)}")
        # 시세를 못 가져온 종목은 0원으로 처리하거나 계산에서 제외
        holdings_df['current_price'] = holdings_df['current_price'].fillna(0)

    holdings_df['total_value'] = holdings_df['quantity'] * holdings_df['current_price']
    holdings_df['investment'] = holdings_df['quantity'] * holdings_df['avg_price']
    holdings_df['pnl'] = holdings_df['total_value'] - holdings_df['investment']
    holdings_df['roi'] = (holdings_df['pnl'] / holdings_df['investment']) * 100
    
    return holdings_df

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
