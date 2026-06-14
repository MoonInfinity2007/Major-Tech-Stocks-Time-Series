from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
import pandas as pd
import json


def to_records(d: pd.DataFrame):
    return json.loads(d.to_json(orient='records'))


app = FastAPI(title="Stock Analysis API")

stocks = pd.read_csv('major-tech-stock-2019-2024.csv')
stocks['Date'] = pd.to_datetime(stocks['Date'])
stocks = stocks.sort_values(['Ticker', 'Date']).reset_index(drop=True)

macro = pd.read_csv('fred_macro_2019_2024.csv', parse_dates=['DATE'])
macro = macro.rename(columns={'DATE': 'Date'}).sort_values('Date')
macro['CPI_YoY'] = macro['CPIAUCSL'].pct_change(12) * 100

stocks = pd.merge_asof(
    stocks.sort_values('Date'),
    macro.sort_values('Date'),
    on='Date',
    direction='backward'
).sort_values(['Ticker', 'Date']).reset_index(drop=True)

numeric_cols = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume', 'FEDFUNDS', 'CPIAUCSL', 'CPI_YoY', 'UNRATE']
for col in numeric_cols:
    stocks[col] = pd.to_numeric(stocks[col], errors='coerce')

stocks = stocks.drop_duplicates()
stocks = stocks.dropna(subset=numeric_cols + ['Date', 'Ticker']).reset_index(drop=True)

stocks['Daily_Return'] = stocks.groupby('Ticker')['Close'].pct_change() * 100
stocks['Price_Range'] = stocks['High'] - stocks['Low']
stocks['Price_Range_Pct'] = stocks['Price_Range'] / stocks['Open'] * 100
stocks['Volatility_30d'] = stocks.groupby('Ticker')['Daily_Return'].transform(lambda x: x.rolling(30).std())
stocks['MA_50'] = stocks.groupby('Ticker')['Close'].transform(lambda x: x.rolling(50).mean())
stocks['Above_MA50'] = (stocks['Close'] > stocks['MA_50']).astype(int)
stocks['High_Volume_Day'] = stocks['Volume'] > stocks.groupby('Ticker')['Volume'].transform(lambda x: x.quantile(0.90))
stocks['Rate_Regime'] = pd.qcut(stocks['FEDFUNDS'], q=3, labels=['Low rate', 'Medium rate', 'High rate'])

df = stocks



@app.get("/stocks")
def get_stocks(
    ticker: str = Query(None, description="Тикер, например AAPL"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=10000)
):
    data = df.copy()
    if ticker:
        data = data[data['Ticker'].str.upper() == ticker.upper()]
        if data.empty:
            raise HTTPException(status_code=404, detail=f"Тикер {ticker} не найден")
    total = len(data)
    start = (page - 1) * page_size
    end = start + page_size
    result = data.iloc[start:end].copy()
    result['Date'] = result['Date'].astype(str)
    result['Rate_Regime'] = result['Rate_Regime'].astype(str)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": to_records(result)
    }


@app.get("/stats")
def get_stats(
    ticker: str = Query(..., description="Ticker"),
    metric: str = Query("Close", description="Column: Open, High, Low, Close, Volume, Daily_Return, ...")
):
    data = df[df['Ticker'].str.upper() == ticker.upper()]
    if data.empty:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found")
    if metric not in data.columns:
        raise HTTPException(status_code=400, detail=f"Metric {metric} not found")
    col = pd.to_numeric(data[metric], errors='coerce').dropna()
    if col.empty:
        raise HTTPException(status_code=400, detail=f"No data for metric {metric}")

    def safe_round(value, ndigits=4):
        value = float(value)
        return None if pd.isna(value) else round(value, ndigits)

    return {
        "ticker": ticker.upper(),
        "metric": metric,
        "mean":   safe_round(col.mean()),
        "median": safe_round(col.median()),
        "std":    safe_round(col.std()),
        "min":    safe_round(col.min()),
        "max":    safe_round(col.max()),
    }


@app.get("/comparison")
def get_comparison():
    table = df.groupby(['Ticker', 'Rate_Regime']).agg(
        mean_return=('Daily_Return', 'mean'),
        median_return=('Daily_Return', 'median'),
        volatility=('Daily_Return', 'std'),
        mean_price_range=('Price_Range_Pct', 'mean'),
        high_volume_share=('High_Volume_Day', 'mean')
    ).round(3).reset_index()
    table['Rate_Regime'] = table['Rate_Regime'].astype(str)
    return {"data": to_records(table)}


@app.get("/correlation")
def get_correlation():
    pivot_returns = df.pivot_table(index='Date', columns='Ticker', values='Daily_Return')
    corr = pivot_returns.corr().round(4)
    matrix = json.loads(corr.to_json())
    return {
        "tickers": corr.columns.tolist(),
        "matrix": [[matrix[col][row] for col in corr.columns] for row in corr.index]
    }


@app.get("/hypothesis1")
def get_hypothesis1():
    avg_vol = df.groupby('Ticker')['Volatility_30d'].mean().round(4).sort_values(ascending=False)
    return {"average_volatility_by_ticker": json.loads(avg_vol.to_json())}


@app.get("/hypothesis2")
def get_hypothesis2():
    table = df.groupby(['Rate_Regime', 'High_Volume_Day'])['Price_Range_Pct'] \
        .agg(['mean', 'median', 'std', 'count']).round(3).reset_index()
    table['Rate_Regime'] = table['Rate_Regime'].astype(str)
    return {"data": to_records(table)}


class StockRecord(BaseModel):
    Date: str
    Ticker: str
    Open: float
    High: float
    Low: float
    Close: float
    Volume: float


@app.post("/stocks", status_code=201)
def add_stock(record: StockRecord):
    global df
    new_row = pd.DataFrame([record.dict()])
    new_row['Date'] = pd.to_datetime(new_row['Date'])
    df = pd.concat([df, new_row], ignore_index=True)
    return {"message": "Запись добавлена", "record": record.dict()}


@app.get("/tickers")
def get_tickers():
    return {"tickers": sorted(df['Ticker'].unique().tolist())}