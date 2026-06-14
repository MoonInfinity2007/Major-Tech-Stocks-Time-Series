import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Stock Analysis", page_icon="📈", layout="wide")
st.title("Major Tech Stocks & US Macroeconomic Indicators (2019–2023)")


tickers = requests.get(f"{API_URL}/tickers").json()["tickers"]


st.sidebar.header("Filters")
selected_ticker = st.sidebar.selectbox("Ticker", tickers)


@st.cache_data
def load_data(ticker):
    rows = []
    page = 1
    while True:
        r = requests.get(f"{API_URL}/stocks", params={"ticker": ticker, "page": page, "page_size": 1000}).json()
        rows.extend(r["data"])
        if len(rows) >= r["total"]:
            break
        page += 1
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


@st.cache_data
def load_all_data():
    rows = []
    page = 1
    while True:
        r = requests.get(f"{API_URL}/stocks", params={"page": page, "page_size": 5000}).json()
        rows.extend(r["data"])
        if len(rows) >= r["total"]:
            break
        page += 1
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


data = load_data(selected_ticker)
all_data = load_all_data()


st.header("1. Abstract")
st.markdown("""
This project analyzes historical stock data for major US technology companies 
from 2019 to 2023 and enriches it with macroeconomic indicators from the Federal Reserve Economic Data (FRED) database: 
Federal Funds Rate, Consumer Price Index, and Unemployment Rate. The main goal is to study stock price dynamics, 
trading activity, volatility, and how these patterns differ across companies and macroeconomic regimes.
""")

st.markdown("""
This project was carried out by Zhuriho Ivan Aleksandrovich (251-1) and Kukovyakin Artem
Aleksandrovich (251-1). Zhuriho Ivan Aleksandrovich was responsible for data collection,
hypothesis formulation, analytical discussion, data transformation, and the Streamlit
interface. Kukovyakin Artem Aleksandrovich was responsible for descriptive statistics,
visualizations, data cleaning, and FRED enrichment.
""")


st.header("2. Dataset Description")
col1, col2, col3 = st.columns(3)
col1.metric("Number of rows", f"{len(all_data):,}")
col2.metric("Number of tickers", len(tickers))
col3.metric("Period", f"{all_data['Date'].min().date()} -> {all_data['Date'].max().date()}")

st.markdown("""
The main dataset belongs to the financial market domain. It contains daily stock market
observations for five large technology companies: Apple, Microsoft, Amazon, Google, and Tesla.
Each row represents one trading day for one ticker. The file name mentions 2019-2024,
but the actual observations in the provided CSV run from 2019-01-02 to 2023-12-29.

The original stock dataset has 8 fields: `Date`, `Open`, `High`, `Low`, `Close`, `Adj Close`,
`Volume`, and `Ticker`. `Date` is a calendar field, `Ticker` is categorical, and the remaining
fields are numerical market indicators. The project also adds three macroeconomic time series from FRED:
`FEDFUNDS`, `CPIAUCSL`, and `UNRATE`. These indicators are monthly,
so they are merged into the daily stock data using the most recent available macroeconomic value for each trading date.
""")

st.subheader("The first rows of the table")
st.dataframe(data.head(10), use_container_width=True)


st.header("3. Descriptive Statistics")
st.caption(f"Ticker: **{selected_ticker}**")

STAT_FIELDS = ["Close", "Volume", "Daily_Return", "Volatility_30d", "Price_Range_Pct"]

try:
    rows = []
    for field in STAT_FIELDS:
        s = requests.get(f"{API_URL}/stats", params={"ticker": selected_ticker, "metric": field}).json()
        rows.append({
            "Field": field,
            "Mean": s["mean"],
            "Median": s["median"],
            "Std": s["std"],
            "Min": s["min"],
            "Max": s["max"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f"API is unavailable: {e}")

st.markdown("""
The stock price fields have different scales because the companies have different nominal share prices.
`Volume` is also highly dispersed, which is typical for market data because trading activity changes
sharply across companies and market events. The macroeconomic fields have smaller ranges because they
describe national monthly indicators rather than company-level daily prices.
""")


st.header("4. Data Cleanup")
st.markdown("""
The first quality check shows that the original stock file is already mostly clean:
there are no missing values in the supplied columns, and the expected numerical columns are read as numeric types.
The `Date` column was converted from string to datetime because date operations, rolling windows,
and time-based merges require a proper datetime type.

After merging in the macroeconomic data, the dataset is cleaned further: all analytical columns
are coerced to numeric type, duplicate rows are dropped, and rows with missing values are removed —
in particular, the earliest observations for which year-over-year CPI cannot yet be computed
(it requires 12 prior monthly values).
""")

missing = all_data.isna().sum()
missing = missing[missing > 0]

st.markdown("Missing values:")
st.dataframe(missing)
st.markdown("""
Note: after adding these rolling-window and shift-based columns, a small number of missing
values appear at the start of each ticker's time series — Daily_Return has 5 NaNs (1 per
ticker, the first day with no prior Close), Volatility_30d has 150 NaNs (30 per ticker, until
a full 30-day window of returns is available), and MA_50 has 245 NaNs (49 per ticker, until
a full 50-day window of prices is available). This is expected behavior of rolling
calculations rather than a data quality issue, so these rows are kept rather than dropped.
""")


st.header("5. Price History & Overview Plots")

fig = go.Figure()
fig.add_trace(go.Scatter(x=data["Date"], y=data["Close"], name="Close", line=dict(color="#01696f")))
ma50 = data["Close"].rolling(50).mean()
fig.add_trace(go.Scatter(x=data["Date"], y=ma50, name="MA50", line=dict(dash="dash", color="orange")))
fig.update_layout(title=f"{selected_ticker} — Close Price & 50-Day MA", xaxis_title="Date", yaxis_title="Price (USD)")
st.plotly_chart(fig, use_container_width=True)

c1, c2 = st.columns(2)
with c1:
    fig_hist = px.histogram(
        data, x="Daily_Return", nbins=80,
        title=f"{selected_ticker} — Distribution of Daily Returns",
        color_discrete_sequence=["steelblue"]
    )
    fig_hist.add_vline(x=0, line_dash="dash", line_color="red")
    st.plotly_chart(fig_hist, use_container_width=True)

with c2:
    sample = data.sample(min(2000, len(data)), random_state=42)
    fig_scatter = px.scatter(
        sample, x="Volume", y="Price_Range_Pct",
        title=f"{selected_ticker} — Volume vs Intraday Price Range",
        opacity=0.35, color_discrete_sequence=["steelblue"]
    )
    fig_scatter.update_layout(xaxis_title="Volume (shares)", yaxis_title="Price Range (% of Open)")
    st.plotly_chart(fig_scatter, use_container_width=True)

fig_box = px.box(
    all_data, x="Ticker", y="Close",
    title="Close Price Distribution by Ticker",
    color_discrete_sequence=["lightsteelblue"]
)
st.plotly_chart(fig_box, use_container_width=True)

st.markdown("""
The line chart shows the overall upward trend of tech stocks, interrupted by market corrections.
The histogram of daily returns is centered near zero but has "fat tails," meaning very large
daily moves occasionally occur. The scatter plot shows that higher trading volume is often
associated with a larger intraday price range, although the relationship is noisy. The boxplot
confirms that nominal prices differ substantially between tickers.
""")


st.header("6. Volatility")
fig2 = px.line(data, x="Date", y="Volatility_30d", title=f"{selected_ticker} — 30-Day Rolling Volatility")
fig2.update_traces(line_color="#a12c7b")
st.plotly_chart(fig2, use_container_width=True)


st.header("7. Detailed Overview: Comparative Outputs")

c1, c2 = st.columns(2)

with c1:
    fig_ma = go.Figure()
    for ticker in tickers:
        subset = all_data[all_data["Ticker"] == ticker]
        ma50_all = subset["Close"].rolling(50).mean()
        fig_ma.add_trace(go.Scatter(x=subset["Date"], y=ma50_all, name=ticker, mode="lines"))
    fig_ma.update_layout(title="50-Day Moving Average by Ticker", xaxis_title="Date", yaxis_title="Price (USD)")
    st.plotly_chart(fig_ma, use_container_width=True)

with c2:
    try:
        corr_resp = requests.get(f"{API_URL}/correlation").json()
        corr_df = pd.DataFrame(corr_resp["matrix"], index=corr_resp["tickers"], columns=corr_resp["tickers"])
        fig_corr = px.imshow(
            corr_df, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
            title="Correlation of Daily Returns"
        )
        st.plotly_chart(fig_corr, use_container_width=True)
        st.caption("""
        This heatmap shows the correlation coefficient of daily returns between each pair of
        tickers. Values close to **+1** (dark blue) mean the stocks tend to rise and fall on
        the same days; values close to **0** mean a weak relationship; values close to **-1**
        (dark red) would mean the stocks move in opposite directions. The diagonal is always 1,
        since it is each ticker's correlation with itself.
        """)
    except Exception as e:
        st.error(f"Could not fetch correlation data: {e}")

c3, c4 = st.columns(2)

with c3:
    fig_vol = go.Figure()
    for ticker in tickers:
        subset = all_data[all_data["Ticker"] == ticker]
        fig_vol.add_trace(go.Scatter(x=subset["Date"], y=subset["Volatility_30d"], name=ticker, mode="lines"))
    fig_vol.update_layout(title="30-Day Rolling Volatility by Ticker", xaxis_title="Date", yaxis_title="Volatility (%)")
    st.plotly_chart(fig_vol, use_container_width=True)

with c4:
    macro_plot = all_data.drop_duplicates("Date").sort_values("Date")
    fig_macro = go.Figure()
    fig_macro.add_trace(go.Scatter(x=macro_plot["Date"], y=macro_plot["FEDFUNDS"], name="Fed Funds Rate"))
    fig_macro.add_trace(go.Scatter(x=macro_plot["Date"], y=macro_plot["CPI_YoY"], name="CPI YoY (%)"))
    fig_macro.add_trace(go.Scatter(x=macro_plot["Date"], y=macro_plot["UNRATE"], name="Unemployment Rate"))
    fig_macro.update_layout(title="Macroeconomic Indicators Over Time", xaxis_title="Date", yaxis_title="Value")
    st.plotly_chart(fig_macro, use_container_width=True)

st.subheader("Comparison table: returns, volatility & price range by ticker and rate regime")
try:
    comp = requests.get(f"{API_URL}/comparison").json()["data"]
    st.dataframe(pd.DataFrame(comp), use_container_width=True)
except Exception as e:
    st.error(f"Could not fetch comparison table: {e}")

st.markdown("""
The detailed overview compares companies and macroeconomic regimes rather than treating the
whole dataset as a single block. The moving-average and volatility charts show that risk and
trends are not uniform across tickers. The correlation heatmap shows that the companies tend
to move together but not perfectly in sync. The macro indicators chart provides context for
the high-rate period after 2022, and the comparison table summarizes returns, volatility,
intraday price range, and the share of high-volume days by ticker and rate regime.
""")


st.header("8. Data Transformation")
st.markdown("""
The following derived columns were added to the original and enriched data:

- **Daily_Return** — daily return (% change in `Close`)
- **Price_Range** / **Price_Range_Pct** — intraday price range and its share of `Open`
- **Volatility_30d** — rolling 30-day standard deviation of daily returns
- **MA_50** and **Above_MA50** — 50-day moving average and a flag for price above it
- **High_Volume_Day** — flag for trading days in the top 10% of volume for that ticker
- **Rate_Regime** — Federal Funds Rate regime category (Low / Medium / High), derived from `FEDFUNDS`
""")
st.dataframe(
    data[["Date", "Close", "Daily_Return", "Price_Range_Pct", "Volatility_30d", "MA_50", "Above_MA50",
          "High_Volume_Day", "Rate_Regime"]].tail(10),
    use_container_width=True
)


st.header("9. Hypothesis 1: TSLA is More Volatile Than Other Tech Stocks")
st.markdown("""
**Hypothesis:** Tesla (`TSLA`) has higher rolling volatility than the other major tech stocks,
especially during periods of market stress — the early-2020 COVID crash and the 2022 shift
to higher interest rates.
""")

c1, c2 = st.columns(2)
with c1:
    fig_h1 = go.Figure()
    for ticker in tickers:
        subset = all_data[all_data["Ticker"] == ticker]
        is_tsla = ticker == "TSLA"
        fig_h1.add_trace(go.Scatter(
            x=subset["Date"], y=subset["Volatility_30d"], name=ticker,
            line=dict(width=3 if is_tsla else 1),
            opacity=1.0 if is_tsla else 0.5
        ))
    fig_h1.add_vrect(x0="2020-02-01", x1="2020-06-01", fillcolor="red", opacity=0.1, line_width=0,
                      annotation_text="COVID crash")
    fig_h1.add_vrect(x0="2022-01-01", x1="2022-12-31", fillcolor="orange", opacity=0.1, line_width=0,
                      annotation_text="2022 rate hikes")
    fig_h1.update_layout(title="30-Day Rolling Volatility Over Time", xaxis_title="Date", yaxis_title="Volatility (%)")
    st.plotly_chart(fig_h1, use_container_width=True)

with c2:
    try:
        h1 = requests.get(f"{API_URL}/hypothesis1").json()["average_volatility_by_ticker"]
        h1_df = pd.DataFrame(list(h1.items()), columns=["Ticker", "Avg_Volatility_30d"]).sort_values(
            "Avg_Volatility_30d", ascending=False)
        colors = ["crimson" if t == "TSLA" else "steelblue" for t in h1_df["Ticker"]]
        fig_h1b = px.bar(h1_df, x="Ticker", y="Avg_Volatility_30d", title="Average 30-Day Volatility by Ticker")
        fig_h1b.update_traces(marker_color=colors)
        st.plotly_chart(fig_h1b, use_container_width=True)
    except Exception as e:
        st.error(f"Could not fetch hypothesis 1 data: {e}")

st.markdown("""
The hypothesis is supported if Tesla has the highest, or close to the highest, average 30-day
volatility, and if its volatility line sits above most other companies over extended periods.
This check is more informative than a simple price comparison, since it uses a transformed risk
metric, compares multiple companies, and considers specific periods of market stress.
""")


st.header("10. Hypothesis 2: High Volume + High Rate Regime → Larger Price Swings")
st.markdown("""
**Hypothesis:** intraday price swings are largest when two conditions hold at the same time:
the trading day has high volume for its ticker, and the macroeconomic backdrop corresponds to
a high interest-rate regime. This hypothesis combines ticker-specific volume thresholds,
transformed price-range data, and FRED-based rate regimes.
""")

try:
    h2 = requests.get(f"{API_URL}/hypothesis2").json()["data"]
    h2_df = pd.DataFrame(h2)
    st.dataframe(h2_df, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        fig_h2a = px.bar(
            h2_df, x="Rate_Regime", y="mean", color="High_Volume_Day", barmode="group",
            title="Average Price Range by Rate Regime and Volume Condition",
            labels={"mean": "Mean Price Range (% of Open)", "Rate_Regime": "Federal Funds Rate Regime"},
            color_discrete_sequence=["steelblue", "crimson"]
        )
        st.plotly_chart(fig_h2a, use_container_width=True)

    with c2:
        ticker_condition = all_data.groupby(["Ticker", "High_Volume_Day"])["Price_Range_Pct"].mean().reset_index()
        fig_h2b = px.bar(
            ticker_condition, x="Ticker", y="Price_Range_Pct", color="High_Volume_Day", barmode="group",
            title="Average Price Range by Ticker and Volume Condition",
            color_discrete_sequence=["steelblue", "crimson"]
        )
        st.plotly_chart(fig_h2b, use_container_width=True)
except Exception as e:
    st.error(f"Could not fetch hypothesis 2 data: {e}")

st.markdown("""
The hypothesis is supported if the high-volume bars are taller than the regular-day bars, and
if the "high rate + high volume" combination produces the largest average intraday price range.
This is a comparison across multiple conditions at once: it uses per-ticker volume thresholds,
FRED-based rate regimes, and the transformed `Price_Range_Pct` metric.
""")


st.header("11. Discussion")
st.markdown("""
This project uses a composite dataset: daily stock data merged with macroeconomic indicators
from FRED. The original stock dataset is clean, but the project still performs explicit quality
checks, type conversions, and removal of duplicates and missing values after the macroeconomic
enrichment. The derived columns make the analysis more informative, since they focus on returns,
volatility, price range, position relative to the moving average, and interest-rate regimes
rather than just raw prices.

The visual analysis shows that major tech stocks largely move together with the market, but
their volatility and trading behavior differ. The hypotheses were tested using derived metrics
and multi-condition comparisons. Tesla turns out to be more volatile than its peer group, and
high-volume days under different rate regimes show larger intraday price swings — especially
when high trading activity and macroeconomic pressure occur together.
""")


st.header("12. Add New Record")
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
            st.success("Record added!")
            st.cache_data.clear()
        else:
            st.error(f"Error: {r.text}")