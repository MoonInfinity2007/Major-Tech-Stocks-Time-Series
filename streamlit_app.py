import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Stock Analysis", page_icon="📈", layout="wide")
st.title("📈 Major Tech Stocks Analysis (2019–2024)")

# Получаем тикеры
try:
    tickers = requests.get(f"{API_URL}/tickers").json()["tickers"]
except:
    tickers = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "NVDA"]

# ── Сайдбар ────────────────────────────────────────────────────────────────
st.sidebar.header("Фильтры")
selected_ticker = st.sidebar.selectbox("Тикер", tickers)
metric = st.sidebar.selectbox("Метрика", ["Close", "Open", "High", "Low", "Volume"])

# ── Секция 1: Статистика ───────────────────────────────────────────────────
st.header("1. Descriptive Statistics")
try:
    stats = requests.get(f"{API_URL}/stats", params={"ticker": selected_ticker, "metric": metric}).json()
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Mean",   f"{stats['mean']:.2f}")
    col2.metric("Median", f"{stats['median']:.2f}")
    col3.metric("Std",    f"{stats['std']:.2f}")
    col4.metric("Min",    f"{stats['min']:.2f}")
    col5.metric("Max",    f"{stats['max']:.2f}")
except Exception as e:
    st.error(f"API недоступен: {e}")

# ── Секция 2: Данные и графики ─────────────────────────────────────────────
st.header("2. Price History")

@st.cache_data
def load_data(ticker):
    rows = []
    page = 1
    while True:
        r = requests.get(f"{API_URL}/stocks", params={"ticker": ticker, "page": page, "page_size": 500}).json()
        rows.extend(r["data"])
        if len(rows) >= r["total"]:
            break
        page += 1
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    return df

data = load_data(selected_ticker)

fig = go.Figure()
fig.add_trace(go.Scatter(x=data["Date"], y=data["Close"], name="Close", line=dict(color="#01696f")))
ma50 = data["Close"].rolling(50).mean()
fig.add_trace(go.Scatter(x=data["Date"], y=ma50, name="MA50", line=dict(dash="dash", color="orange")))
fig.update_layout(title=f"{selected_ticker} — Close Price", xaxis_title="Date", yaxis_title="Price (USD)")
st.plotly_chart(fig, use_container_width=True)

# ── Секция 3: Волатильность ────────────────────────────────────────────────
st.header("3. Volatility")
data["Daily_Return"] = data["Close"].pct_change() * 100
data["Volatility_30d"] = data["Daily_Return"].rolling(30).std()

fig2 = px.line(data, x="Date", y="Volatility_30d", title=f"{selected_ticker} — 30-Day Rolling Volatility")
fig2.update_traces(line_color="#a12c7b")
st.plotly_chart(fig2, use_container_width=True)

# ── Секция 4: Добавить запись ──────────────────────────────────────────────
st.header("4. Add New Record")
with st.form("add_record"):
    col1, col2 = st.columns(2)
    date_input   = col1.date_input("Date")
    ticker_input = col2.text_input("Ticker", value=selected_ticker)
    open_v  = col1.number_input("Open",   value=100.0)
    high_v  = col1.number_input("High",   value=105.0)
    low_v   = col2.number_input("Low",    value=98.0)
    close_v = col2.number_input("Close",  value=102.0)
    volume  = col1.number_input("Volume", value=1000000.0)
    submitted = st.form_submit_button("Add Record")
    if submitted:
        payload = {"Date": str(date_input), "Ticker": ticker_input,
                   "Open": open_v, "High": high_v, "Low": low_v,
                   "Close": close_v, "Volume": volume}
        r = requests.post(f"{API_URL}/stocks", json=payload)
        if r.status_code == 201:
            st.success("✅ Запись добавлена!")
        else:
            st.error(f"Ошибка: {r.text}")