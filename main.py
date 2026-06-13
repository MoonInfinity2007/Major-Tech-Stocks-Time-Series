from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
import pandas as pd

app = FastAPI(title="Stock Analysis API")
df = pd.read_csv('major-tech-stock-2019-2024.csv')
df['Date'] = pd.to_datetime(df['Date'])


@app.get("/stocks")
def get_stocks(
    ticker: str = Query(None, description="Тикер, например AAPL"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500)
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
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": result.to_dict(orient='records')
    }


@app.get("/stats")
def get_stats(
    ticker: str = Query(..., description="Тикер"),
    metric: str = Query("Close", description="Колонка: Open, High, Low, Close, Volume")
):
    data = df[df['Ticker'].str.upper() == ticker.upper()]
    if data.empty:
        raise HTTPException(status_code=404, detail=f"Тикер {ticker} не найден")
    if metric not in data.columns:
        raise HTTPException(status_code=400, detail=f"Метрика {metric} не найдена")
    col = data[metric].dropna()
    return {
        "ticker": ticker.upper(),
        "metric": metric,
        "mean":   round(col.mean(), 4),
        "median": round(col.median(), 4),
        "std":    round(col.std(), 4),
        "min":    round(col.min(), 4),
        "max":    round(col.max(), 4),
    }


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