from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
import json
import logging
import os

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.database import DuckDBManager
from src.data_sync import StockDataSync
from src.scheduler import DailyUpdateScheduler
from src.analysis import TechnicalIndicators

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Stock Analysis Platform API",
    description="DuckDB-based stock data analysis and visualization platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_manager: Optional[DuckDBManager] = None
data_sync: Optional[StockDataSync] = None
scheduler: Optional[DailyUpdateScheduler] = None

class StockQuery(BaseModel):
    ts_code: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class StockDataResponse(BaseModel):
    success: bool
    data: List[Dict[str, Any]]
    total: int

class NewsQuery(BaseModel):
    keyword: Optional[str] = None
    ts_code: Optional[str] = None
    src: Optional[str] = "all"
    limit: Optional[int] = 80

class NewsFavoritesQuery(BaseModel):
    stock_codes: List[str]
    src: Optional[str] = "all"
    limit_per_stock: Optional[int] = 12
    total_limit: Optional[int] = 100

class SyncResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class AnalysisResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

class SyncRequest(BaseModel):
    ts_code: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class FavoriteNewsRequest(BaseModel):
    stock_codes: List[str]
    src: Optional[str] = "all"
    limit_per_stock: Optional[int] = 12
    total_limit: Optional[int] = 100

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'stock_data.duckdb')
TOKEN = os.getenv('TUSHARE_TOKEN', '1ff975ea535e82679de240fc493698506452ace8f002152c965aed01')

@app.on_event("startup")
async def startup_event():
    global db_manager, data_sync, scheduler
    try:
        db_manager = DuckDBManager(DB_PATH)
        data_sync = StockDataSync(TOKEN)
        scheduler = DailyUpdateScheduler(DB_PATH, update_time="18:00", token=TOKEN)
        scheduler.start()
        logger.info("Application startup completed")
    except Exception as e:
        logger.error(f"Startup error: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    if scheduler:
        scheduler.stop()
    if db_manager:
        db_manager.close()
    logger.info("Application shutdown")

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/stocks")
async def get_stocks():
    try:
        stocks = db_manager.get_all_stocks()
        stocks_list = stocks.to_dict('records')
        return {"success": True, "data": stocks_list, "total": len(stocks_list)}
    except Exception as e:
        logger.error(f"Error getting stocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stock/{ts_code}")
async def get_stock(ts_code: str):
    try:
        data = db_manager.get_stock_data(ts_code)
        stock_name = db_manager.get_stock_name(ts_code)
        data_list = data.to_dict('records')
        return {
            "success": True,
            "data": data_list,
            "stock_name": stock_name,
            "total": len(data_list)
        }
    except Exception as e:
        logger.error(f"Error getting stock {ts_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stock/{ts_code}/kline")
async def get_kline(ts_code: str, limit: int = Query(5000, ge=1, le=10000)):
    try:
        data = db_manager.get_stock_data(ts_code)
        stock_name = db_manager.get_stock_name(ts_code)
        if data.empty:
            return {"success": True, "data": [], "stock_name": stock_name, "total": 0}
        data = data.tail(limit)
        data['time'] = data['trade_date'].astype(str)
        data_list = data.to_dict('records')
        return {
            "success": True,
            "data": data_list,
            "stock_name": stock_name,
            "total": len(data_list)
        }
    except Exception as e:
        logger.error(f"Error getting kline for {ts_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stock/{ts_code}/latest")
async def get_latest(ts_code: str):
    try:
        data = db_manager.get_stock_data(ts_code)
        if data.empty:
            return {"success": True, "data": []}
        latest = data.tail(1)
        data_list = latest.to_dict('records')
        return {"success": True, "data": data_list}
    except Exception as e:
        logger.error(f"Error getting latest data for {ts_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stock/{ts_code}/indicators")
async def get_indicators(ts_code: str):
    try:
        data = db_manager.get_stock_data(ts_code)
        if data.empty:
            return {"success": True, "data": {"summary": {}}}
        indicators_df = TechnicalIndicators.calculate_all_indicators(data)
        summary = TechnicalIndicators.get_indicator_summary(indicators_df)
        # Flatten summary for frontend compatibility
        flat_summary = {}
        for k, v in summary.items():
            if isinstance(v, dict):
                flat_summary.update(v)
            else:
                flat_summary[k] = v
        # Add close and MA20 for signal generation
        if not indicators_df.empty:
            latest = indicators_df.iloc[-1]
            flat_summary['close'] = latest.get('close')
            flat_summary['MA20'] = latest.get('MA20')
            flat_summary['SIGNAL'] = latest.get('MACD_Signal')
            flat_summary['K'] = latest.get('K')
            flat_summary['D'] = latest.get('D')
        return {"success": True, "data": {"summary": flat_summary}}
    except Exception as e:
        logger.error(f"Error calculating indicators for {ts_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stock/{ts_code}/stats")
async def get_stock_stats(ts_code: str):
    try:
        data = db_manager.get_stock_data(ts_code)
        if data.empty:
            return {"success": True, "data": {}}
        stats = {
            "total_days": len(data),
            "start_date": str(data['trade_date'].min()),
            "end_date": str(data['trade_date'].max()),
            "max_close": float(data['close'].max()),
            "min_close": float(data['close'].min()),
            "avg_close": float(data['close'].mean()),
            "max_volume": float(data['vol'].max()),
            "avg_volume": float(data['vol'].mean()),
        }
        return {"success": True, "data": stats}
    except Exception as e:
        logger.error(f"Error getting stats for {ts_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/query")
async def execute_sql_query(query: str = Query(..., description="SQL query string")):
    try:
        result = db_manager.execute_query(query)
        result_list = result.to_dict('records')
        return {"success": True, "data": result_list}
    except Exception as e:
        logger.error(f"Query error: {e}")
        return {"success": False, "message": str(e)}

@app.post("/api/sync", response_model=SyncResponse)
async def sync_data(request: Optional[SyncRequest] = None):
    try:
        result = data_sync.sync_stock_data(
            db_manager,
            ts_code=request.ts_code if request else None,
            start_date=request.start_date if request else None,
            end_date=request.end_date if request else None
        )
        return {"success": True, "message": "Sync completed", "data": result}
    except Exception as e:
        logger.error(f"Sync error: {e}")
        return {"success": False, "message": str(e)}

@app.post("/api/sync/basic", response_model=SyncResponse)
async def sync_basic():
    try:
        df = data_sync.get_stock_basic_info()
        if not df.empty:
            count = db_manager.import_stock_basic(df)
            return {"success": True, "message": f"Imported {count} stock basic records", "data": {"count": count}}
        else:
            return {"success": True, "message": "No basic data to import", "data": {"count": 0}}
    except Exception as e:
        logger.error(f"Sync basic error: {e}")
        return {"success": False, "message": str(e)}

@app.post("/api/sync/daily", response_model=SyncResponse)
async def daily_update():
    try:
        result = data_sync.sync_daily_update(db_manager)
        return {"success": True, "message": result.get("message", ""), "data": result}
    except Exception as e:
        logger.error(f"Daily update error: {e}")
        return {"success": False, "message": str(e)}

@app.get("/api/analysis/market")
async def market_analysis():
    try:
        stocks = db_manager.get_all_stocks()
        return {"success": True, "data": {"total_stocks": len(stocks), "stocks": stocks.to_dict('records')}}
    except Exception as e:
        logger.error(f"Market analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analysis/stock/{ts_code}")
async def stock_analysis(ts_code: str):
    try:
        data = db_manager.get_stock_data(ts_code)
        if data.empty:
            return {"success": True, "data": {}}
        indicators_df = TechnicalIndicators.calculate_all_indicators(data)
        summary = TechnicalIndicators.get_indicator_summary(indicators_df)
        return {"success": True, "data": summary}
    except Exception as e:
        logger.error(f"Stock analysis error for {ts_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/news")
async def get_news(
    keyword: Optional[str] = None,
    ts_code: Optional[str] = None,
    src: Optional[str] = "all",
    limit: int = Query(80, ge=1, le=200)
):
    try:
        df = data_sync.get_stock_news(ts_code=ts_code, keyword=keyword, src=src, limit=limit)
        if df is not None and not df.empty:
            data_list = df.to_dict('records')
            return {"success": True, "data": data_list, "source": src}
        else:
            return {"success": True, "data": [], "source": src}
    except Exception as e:
        logger.error(f"News fetch error: {e}")
        return {"success": False, "message": str(e), "data": []}

@app.post("/api/news/favorites")
async def get_favorites_news(query: NewsFavoritesQuery):
    try:
        all_frames = []
        for code in query.stock_codes:
            df = data_sync.get_stock_news(ts_code=code, src=query.src, limit=query.limit_per_stock)
            if df is not None and not df.empty:
                if 'stock_code' not in df.columns:
                    df['stock_code'] = code
                all_frames.append(df)
        if all_frames:
            merged = StockDataSync.merge_news_frames(all_frames, limit=query.total_limit)
            data_list = merged.to_dict('records')
            return {"success": True, "data": data_list, "source": query.src}
        else:
            return {"success": True, "data": [], "source": query.src}
    except Exception as e:
        logger.error(f"Favorites news error: {e}")
        return {"success": False, "message": str(e), "data": []}

static_path = os.path.join(os.path.dirname(__file__), "..", "..", "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/app", response_class=HTMLResponse)
async def web_app():
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PandaAI QuantFlow - 股票分析平台</title>
        <script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            :root {
                --bg-primary: #0d1117;
                --bg-secondary: #161b22;
                --bg-tertiary: #21262d;
                --bg-hover: #30363d;
                --border-color: #30363d;
                --text-primary: #c9d1d9;
                --text-secondary: #8b949e;
                --accent-blue: #58a6ff;
                --accent-green: #3fb950;
                --accent-red: #f85149;
                --accent-purple: #a371f7;
                --accent-orange: #d29922;
                --accent-yellow: #e3b341;
                --success: #238636;
                --danger: #da3633;
            }
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', sans-serif;
                background: var(--bg-primary);
                color: var(--text-primary);
                height: 100vh;
                overflow: hidden;
            }
            .app-container {
                display: flex;
                height: 100vh;
            }
            /* 左侧工具栏 */
            .sidebar {
                width: 64px;
                background: var(--bg-secondary);
                border-right: 1px solid var(--border-color);
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 12px 0;
                z-index: 100;
            }
            .sidebar-logo {
                width: 40px;
                height: 40px;
                background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-bottom: 24px;
                font-weight: bold;
                font-size: 18px;
            }
            .sidebar-item {
                width: 48px;
                height: 48px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 8px;
                margin-bottom: 8px;
                cursor: pointer;
                color: var(--text-secondary);
                transition: all 0.2s;
                position: relative;
            }
            .sidebar-item:hover, .sidebar-item.active {
                background: var(--bg-hover);
                color: var(--accent-blue);
            }
            .sidebar-item i {
                font-size: 20px;
            }
            .sidebar-tooltip {
                position: absolute;
                left: 56px;
                background: var(--bg-tertiary);
                padding: 6px 12px;
                border-radius: 6px;
                font-size: 12px;
                white-space: nowrap;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.2s;
                border: 1px solid var(--border-color);
                z-index: 200;
            }
            .sidebar-item:hover .sidebar-tooltip {
                opacity: 1;
            }
            /* 左侧面板 */
            .left-panel {
                width: 280px;
                background: var(--bg-secondary);
                border-right: 1px solid var(--border-color);
                display: flex;
                flex-direction: column;
                transition: width 0.3s;
            }
            .panel-header {
                padding: 16px;
                border-bottom: 1px solid var(--border-color);
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            .panel-title {
                font-size: 14px;
                font-weight: 600;
                color: var(--text-primary);
            }
            .panel-tabs {
                display: flex;
                padding: 0 16px;
                border-bottom: 1px solid var(--border-color);
            }
            .panel-search {
                padding: 12px 16px;
                border-bottom: 1px solid var(--border-color);
            }
            .panel-search input {
                width: 100%;
                padding: 8px 12px;
                background: var(--bg-primary);
                border: 1px solid var(--border-color);
                border-radius: 6px;
                color: var(--text-primary);
                font-size: 13px;
                outline: none;
            }
            .panel-search input:focus {
                border-color: var(--accent-blue);
            }
            .panel-search input::placeholder {
                color: var(--text-secondary);
            }
            .stock-list-container {
                flex: 1;
                overflow-y: auto;
                padding: 8px;
            }
            .stock-list-item {
                padding: 10px 12px;
                border-radius: 6px;
                cursor: pointer;
                transition: background 0.2s;
                margin-bottom: 4px;
            }
            .stock-list-item:hover, .stock-list-item.active {
                background: var(--bg-hover);
            }
            .stock-list-item-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 4px;
            }
            .stock-list-code {
                font-weight: 600;
                font-size: 13px;
            }
            .stock-list-price {
                font-weight: 600;
                font-size: 13px;
            }
            .stock-list-info {
                display: flex;
                justify-content: space-between;
                font-size: 11px;
                color: var(--text-secondary);
            }
            .stock-list-change {
                font-size: 11px;
                font-weight: 600;
            }
            .up { color: var(--accent-red); }
            .down { color: var(--accent-green); }
            /* 主内容区 */
            .main-content {
                flex: 1;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            /* 顶部栏 */
            .top-bar {
                height: 48px;
                background: var(--bg-secondary);
                border-bottom: 1px solid var(--border-color);
                display: flex;
                align-items: center;
                padding: 0 16px;
                justify-content: space-between;
            }
            .top-bar-left {
                display: flex;
                align-items: center;
                gap: 16px;
            }
            .stock-input-group {
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .stock-input-group input {
                width: 180px;
                padding: 6px 12px;
                background: var(--bg-primary);
                border: 1px solid var(--border-color);
                border-radius: 6px;
                color: var(--text-primary);
                font-size: 13px;
                outline: none;
            }
            .stock-input-group input:focus {
                border-color: var(--accent-blue);
            }
            .btn {
                padding: 6px 16px;
                background: var(--bg-hover);
                border: 1px solid var(--border-color);
                border-radius: 6px;
                color: var(--text-primary);
                font-size: 13px;
                cursor: pointer;
                transition: all 0.2s;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            .btn:hover {
                background: var(--accent-blue);
                border-color: var(--accent-blue);
            }
            .btn-primary {
                background: var(--accent-blue);
                border-color: var(--accent-blue);
            }
            .btn-primary:hover {
                background: #4a9eff;
            }
            .top-bar-right {
                display: flex;
                align-items: center;
                gap: 12px;
            }
            .status-badge {
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 12px;
                color: var(--text-secondary);
            }
            .status-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: var(--accent-green);
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            /* 工作区 */
            .workspace {
                flex: 1;
                display: flex;
                overflow: hidden;
            }
            .chart-layout {
                flex: 1;
                display: flex;
                overflow: hidden;
            }
            .chart-main {
                flex: 1;
                display: flex;
                flex-direction: column;
                padding: 12px;
                gap: 8px;
            }
            .chart-panel {
                flex: 1;
                background: var(--bg-secondary);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                padding: 12px;
                position: relative;
            }
            .chart-panel-title {
                font-size: 12px;
                color: var(--text-secondary);
                margin-bottom: 8px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .chart-panel-actions {
                display: flex;
                gap: 8px;
            }
            .chart-action-btn {
                padding: 4px 10px;
                background: var(--bg-tertiary);
                border: 1px solid var(--border-color);
                border-radius: 4px;
                color: var(--text-secondary);
                font-size: 11px;
                cursor: pointer;
            }
            .chart-action-btn:hover {
                background: var(--bg-hover);
                color: var(--text-primary);
            }
            .chart-action-btn.active {
                background: var(--accent-blue);
                color: white;
                border-color: var(--accent-blue);
            }
            #klineChart, #volumeChart {
                width: 100%;
                height: calc(100% - 30px);
            }
            .volume-panel {
                height: 160px;
                flex: none;
            }
            /* 右侧面板 */
            .right-panel {
                width: 320px;
                background: var(--bg-secondary);
                border-left: 1px solid var(--border-color);
                display: flex;
                flex-direction: column;
                overflow-y: auto;
            }
            .info-card {
                padding: 16px;
                border-bottom: 1px solid var(--border-color);
            }
            .info-card-title {
                font-size: 12px;
                color: var(--text-secondary);
                margin-bottom: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .price-display {
                display: flex;
                align-items: baseline;
                gap: 12px;
                margin-bottom: 12px;
            }
            .price-main {
                font-size: 32px;
                font-weight: 700;
            }
            .price-change {
                font-size: 16px;
                font-weight: 600;
            }
            .price-detail {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
            }
            .price-detail-item {
                display: flex;
                justify-content: space-between;
                font-size: 12px;
                padding: 6px 0;
                border-bottom: 1px solid var(--border-color);
            }
            .price-detail-label {
                color: var(--text-secondary);
            }
            .price-detail-value {
                font-weight: 600;
            }
            .indicator-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
            }
            .indicator-box {
                background: var(--bg-tertiary);
                padding: 12px;
                border-radius: 6px;
                border: 1px solid var(--border-color);
            }
            .indicator-box-label {
                font-size: 11px;
                color: var(--text-secondary);
                margin-bottom: 4px;
            }
            .indicator-box-value {
                font-size: 18px;
                font-weight: 700;
            }
            .signal-badge {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                margin-top: 4px;
            }
            .signal-buy { background: rgba(63, 185, 80, 0.2); color: var(--accent-green); }
            .signal-sell { background: rgba(248, 81, 73, 0.2); color: var(--accent-red); }
            .signal-neutral { background: rgba(139, 148, 158, 0.2); color: var(--text-secondary); }
            /* 底部状态栏 */
            .status-bar {
                height: 28px;
                background: var(--bg-secondary);
                border-top: 1px solid var(--border-color);
                display: flex;
                align-items: center;
                padding: 0 16px;
                font-size: 11px;
                color: var(--text-secondary);
                justify-content: space-between;
            }
            .status-bar-left {
                display: flex;
                gap: 16px;
            }
            .status-bar-item {
                display: flex;
                align-items: center;
                gap: 6px;
            }
            /* 标签页 */
            .tab-content { display: none; width: 100%; }
            .tab-content.active { display: flex; width: 100%; }
            #analysis-view.active { display: block; width: 100%; }
            #query-view.active { display: block; width: 100%; }
            #sync-view.active { display: block; width: 100%; }
            /* 数据查询页 */
            .query-workspace {
                flex: 1;
                display: flex;
                padding: 12px;
                gap: 12px;
            }
            .query-panel {
                flex: 1;
                background: var(--bg-secondary);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                padding: 16px;
                overflow-y: auto;
            }
            .data-table {
                width: 100%;
                border-collapse: collapse;
                font-size: 12px;
            }
            .data-table th, .data-table td {
                padding: 10px 12px;
                text-align: left;
                border-bottom: 1px solid var(--border-color);
            }
            .data-table th {
                background: var(--bg-tertiary);
                font-weight: 600;
                color: var(--text-secondary);
                font-size: 11px;
                text-transform: uppercase;
                position: sticky;
                top: 0;
            }
            .data-table tr:hover {
                background: var(--bg-hover);
            }
            /* 滚动条 */
            ::-webkit-scrollbar {
                width: 6px;
                height: 6px;
            }
            ::-webkit-scrollbar-track {
                background: var(--bg-primary);
            }
            ::-webkit-scrollbar-thumb {
                background: var(--bg-hover);
                border-radius: 3px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: var(--text-secondary);
            }
            /* 分析页 */
            .analysis-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 12px;
                padding: 12px;
            }
            .analysis-card {
                background: var(--bg-secondary);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                padding: 16px;
            }
            .analysis-card h4 {
                font-size: 13px;
                color: var(--text-secondary);
                margin-bottom: 12px;
            }
            .tab-btn {
                flex: 1;
                padding: 8px 12px;
                background: transparent;
                border: none;
                color: var(--text-secondary);
                font-size: 12px;
                cursor: pointer;
                transition: all 0.2s;
                border-bottom: 2px solid transparent;
            }
            .tab-btn:hover {
                color: var(--text-primary);
                background: var(--bg-tertiary);
            }
            .tab-btn.active {
                color: var(--accent-blue);
                border-bottom-color: var(--accent-blue);
                background: var(--bg-tertiary);
            }
            .fav-star {
                color: var(--accent-yellow) !important;
            }
            .stock-list-item .fav-icon {
                margin-left: auto;
                font-size: 11px;
                color: var(--accent-yellow);
                display: none;
            }
            .stock-list-item.favorite .fav-icon {
                display: inline;
            }
            .news-shell {
                flex: 1;
                display: grid;
                grid-template-columns: 340px minmax(0, 1fr);
                gap: 12px;
                padding: 12px;
                min-height: 0;
            }
            .news-toolbar {
                display: flex;
                gap: 8px;
                margin-bottom: 12px;
            }
            .news-mode-btn {
                flex: 1;
                justify-content: center;
            }
            .news-mode-btn.active {
                background: var(--accent-blue);
                border-color: var(--accent-blue);
                color: white;
            }
            .news-form {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            .news-field label {
                display: block;
                font-size: 11px;
                color: var(--text-secondary);
                margin-bottom: 6px;
            }
            .news-field input,
            .news-field select {
                width: 100%;
                padding: 8px 10px;
                background: var(--bg-primary);
                border: 1px solid var(--border-color);
                border-radius: 6px;
                color: var(--text-primary);
                font-size: 13px;
                outline: none;
            }
            .news-field input:focus,
            .news-field select:focus {
                border-color: var(--accent-blue);
            }
            .news-actions {
                display: flex;
                gap: 8px;
            }
            .news-card {
                padding: 14px 0;
                border-bottom: 1px solid var(--border-color);
            }
            .news-card-title {
                color: var(--text-primary);
                font-size: 14px;
                font-weight: 600;
                line-height: 1.45;
                text-decoration: none;
            }
            .news-card-title:hover {
                color: var(--accent-blue);
            }
            .news-meta {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-top: 8px;
                font-size: 11px;
                color: var(--text-secondary);
            }
            .news-pill {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 2px 7px;
                border-radius: 999px;
                background: var(--bg-tertiary);
                border: 1px solid var(--border-color);
            }
            .news-empty {
                padding: 48px 20px;
                text-align: center;
                color: var(--text-secondary);
                font-size: 13px;
            }
        </style>
    </head>
    <body>
        <div class="app-container">
            <!-- 左侧图标栏 -->
            <div class="sidebar">
                <div class="sidebar-logo">P</div>
                <div class="sidebar-item active" onclick="switchView('chart')" title="超级图表">
                    <i class="fas fa-chart-line"></i>
                    <span class="sidebar-tooltip">超级图表</span>
                </div>
                <div class="sidebar-item" onclick="switchView('query')" title="数据查询">
                    <i class="fas fa-database"></i>
                    <span class="sidebar-tooltip">数据查询</span>
                </div>
                <div class="sidebar-item" onclick="switchView('analysis')" title="因子分析">
                    <i class="fas fa-calculator"></i>
                    <span class="sidebar-tooltip">因子分析</span>
                </div>
                <div class="sidebar-item" onclick="switchView('sync')" title="数据同步">
                    <i class="fas fa-sync-alt"></i>
                    <span class="sidebar-tooltip">数据同步</span>
                </div>
                <div class="sidebar-item" onclick="switchView('news')" title="资讯中心">
                    <i class="fas fa-newspaper"></i>
                    <span class="sidebar-tooltip">资讯中心</span>
                </div>
                <div style="flex:1"></div>
                <div class="sidebar-item" onclick="toggleSettings()" title="设置">
                    <i class="fas fa-cog"></i>
                    <span class="sidebar-tooltip">设置</span>
                </div>
            </div>

            <!-- 左侧面板 - 股票列表 -->
            <div class="left-panel">
                <div class="panel-header">
                    <span class="panel-title">股票列表</span>
                    <span style="font-size:11px;color:var(--text-secondary)" id="stockCount">--</span>
                </div>
                <div class="panel-tabs">
                    <button id="tabAll" class="tab-btn active" onclick="switchStockTab('all')">全部</button>
                    <button id="tabFav" class="tab-btn" onclick="switchStockTab('fav')">收藏</button>
                </div>
                <div class="panel-search">
                    <input type="text" id="searchStock" placeholder="搜索股票代码/名称..." oninput="filterStocks()">
                </div>
                <div class="stock-list-container" id="stockList"></div>
            </div>

            <!-- 主内容区 -->
            <div class="main-content">
                <!-- 顶部栏 -->
                <div class="top-bar">
                    <div class="top-bar-left">
                        <div class="stock-input-group">
                            <input type="text" id="stockCode" placeholder="输入股票代码" value="000001.SZ">
                            <button class="btn btn-primary" onclick="loadKline()">
                                <i class="fas fa-search"></i> 查询
                            </button>
                        </div>
                        <div style="display:flex;gap:8px">
                            <button class="chart-action-btn active" onclick="setPeriod('day')">日线</button>
                            <button class="chart-action-btn" onclick="setPeriod('week')">周线</button>
                            <button class="chart-action-btn" onclick="setPeriod('month')">月线</button>
                        </div>
                    </div>
                    <div class="top-bar-right">
                        <div class="status-badge">
                            <div class="status-dot"></div>
                            <span id="systemStatus">系统正常</span>
                        </div>
                        <button class="btn" onclick="refreshData()">
                            <i class="fas fa-redo"></i>
                        </button>
                    </div>
                </div>

                <!-- 工作区 -->
                <div class="workspace">
                    <!-- K线图视图 -->
                    <div id="chart-view" class="tab-content active">
                        <div class="chart-layout">
                            <div class="chart-main">
                                <div class="chart-panel">
                                    <div class="chart-panel-title">
                                        <span>K线图 <span id="chartStockName" style="color:var(--accent-blue)"></span></span>
                                        <div class="chart-panel-actions">
                                            <button class="chart-action-btn" id="favBtn" onclick="toggleFavorite()" title="收藏"><i class="far fa-star"></i></button>
                                            <button class="chart-action-btn" onclick="toggleMA()">MA</button>
                                            <button class="chart-action-btn" onclick="toggleBOLL()">BOLL</button>
                                        </div>
                                    </div>
                                    <div id="klineChart"></div>
                                </div>
                                <div class="chart-panel volume-panel">
                                    <div class="chart-panel-title">
                                        <span>成交量</span>
                                    </div>
                                    <div id="volumeChart"></div>
                                </div>
                            </div>

                        </div>
                    </div>

                    <!-- 数据查询视图 -->
                    <div id="query-view" class="tab-content">
                        <div class="query-workspace">
                            <div class="query-panel" style="flex:0 0 350px">
                                <h4 style="margin-bottom:16px;font-size:14px">SQL 查询</h4>
                                <textarea id="sqlQuery" style="width:100%;height:200px;background:var(--bg-primary);border:1px solid var(--border-color);border-radius:6px;color:var(--text-primary);padding:12px;font-family:monospace;font-size:13px;resize:none" placeholder="输入 SQL 查询语句...">SELECT * FROM stock_daily LIMIT 100</textarea>
                                <button class="btn btn-primary" style="margin-top:12px;width:100%;justify-content:center" onclick="executeQuery()">
                                    <i class="fas fa-play"></i> 执行查询
                                </button>
                                <div style="margin-top:16px">
                                    <h5 style="font-size:12px;color:var(--text-secondary);margin-bottom:8px">常用查询</h5>
                                    <div style="display:flex;flex-direction:column;gap:6px">
                                        <button class="btn" style="justify-content:flex-start;font-size:12px" onclick="setQuery('SELECT ts_code, COUNT(*) as days FROM stock_daily GROUP BY ts_code ORDER BY days DESC LIMIT 20')">股票数据量统计</button>
                                        <button class="btn" style="justify-content:flex-start;font-size:12px" onclick="setQuery('SELECT * FROM stock_daily WHERE ts_code = \'000001.SZ\' ORDER BY trade_date DESC LIMIT 30')">最近30天数据</button>
                                    </div>
                                </div>
                            </div>
                            <div class="query-panel">
                                <h4 style="margin-bottom:16px;font-size:14px">查询结果</h4>
                                <div id="queryResult" style="overflow:auto;height:calc(100% - 40px)">
                                    <p style="color:var(--text-secondary);text-align:center;padding:40px">执行查询以查看结果</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 分析视图 -->
                    <div id="analysis-view" class="tab-content">
                        <div class="analysis-grid">
                            <div class="analysis-card">
                                <h4>趋势分析</h4>
                                <div id="trendAnalysis">加载中...</div>
                            </div>
                            <div class="analysis-card">
                                <h4>波动率分析</h4>
                                <div id="volatilityAnalysis">加载中...</div>
                            </div>
                            <div class="analysis-card">
                                <h4>成交量分析</h4>
                                <div id="volumeAnalysis">加载中...</div>
                            </div>
                            <div class="analysis-card">
                                <h4>技术指标综合</h4>
                                <div id="indicatorAnalysis">加载中...</div>
                            </div>
                        </div>
                    </div>

                    <!-- 同步视图 -->
                    <div id="sync-view" class="tab-content">
                        <div class="query-workspace">
                            <div class="query-panel" style="max-width:600px">
                                <h4 style="margin-bottom:16px;font-size:14px">数据同步管理</h4>
                                <div style="display:flex;flex-direction:column;gap:12px">
                                    <div style="padding:16px;background:var(--bg-tertiary);border-radius:8px;border:1px solid var(--border-color)">
                                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                                            <span style="font-weight:600">全量同步</span>
                                            <span style="font-size:11px;color:var(--text-secondary)">同步所有股票历史数据</span>
                                        </div>
                                        <button class="btn btn-primary" onclick="syncAllData()">
                                            <i class="fas fa-sync"></i> 开始同步
                                        </button>
                                    </div>
                                    <div style="padding:16px;background:var(--bg-tertiary);border-radius:8px;border:1px solid var(--border-color)">
                                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                                            <span style="font-weight:600">每日更新</span>
                                            <span style="font-size:11px;color:var(--text-secondary)">增量更新最新数据</span>
                                        </div>
                                        <button class="btn" onclick="syncDailyData()">
                                            <i class="fas fa-calendar-day"></i> 执行更新
                                        </button>
                                    </div>
                                    <div id="syncResult" style="margin-top:12px"></div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 资讯中心视图 -->
                    <div id="news-view" class="tab-content">
                        <div class="news-shell">
                            <div class="query-panel" style="min-width:0">
                                <h4 style="margin-bottom:14px;font-size:14px">资讯中心</h4>
                                <div class="news-toolbar">
                                    <button class="btn news-mode-btn active" id="newsModeStock" onclick="setNewsMode('stock')"><i class="fas fa-chart-line"></i> 单股</button>
                                    <button class="btn news-mode-btn" id="newsModeFav" onclick="setNewsMode('favorites')"><i class="fas fa-star"></i> 收藏</button>
                                    <button class="btn news-mode-btn" id="newsModeMarket" onclick="setNewsMode('market')"><i class="fas fa-globe"></i> 市场</button>
                                </div>
                                <div class="news-form">
                                    <div class="news-field" id="newsStockField">
                                        <label>股票代码</label>
                                        <div style="display:flex;gap:8px">
                                            <input type="text" id="newsStockCode" placeholder="000001.SZ" value="000001.SZ">
                                            <button class="btn btn-primary" onclick="loadNews()" title="查询"><i class="fas fa-search"></i></button>
                                        </div>
                                    </div>
                                    <div class="news-field">
                                        <label>资讯来源</label>
                                        <select id="newsSource" onchange="loadNews()">
                                            <option value="eastmoney">东方财富</option>
                                            <option value="all">全部来源</option>
                                            <option value="sina">新浪财经</option>
                                            <option value="10jqka">同花顺</option>
                                            <option value="wallstreetcn">华尔街见闻</option>
                                            <option value="yuncaijing">云财经</option>
                                        </select>
                                    </div>
                                    <div class="news-actions">
                                        <button class="btn btn-primary" style="flex:1;justify-content:center" onclick="loadNews()"><i class="fas fa-sync-alt"></i> 刷新资讯</button>
                                        <button class="btn" onclick="syncNewsStockWithChart()" title="使用当前K线股票"><i class="fas fa-link"></i></button>
                                    </div>
                                    <div id="newsHint" style="font-size:12px;color:var(--text-secondary);line-height:1.5"></div>
                                </div>
                            </div>
                            <div class="query-panel" style="min-width:0;display:flex;flex-direction:column">
                                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;gap:12px">
                                    <h4 style="font-size:14px">新闻列表 <span id="newsCount" style="color:var(--text-secondary);font-weight:normal"></span></h4>
                                    <span id="newsStatus" style="font-size:12px;color:var(--text-secondary)">等待查询</span>
                                </div>
                                <div id="newsList" style="overflow:auto;min-height:0;flex:1">
                                    <div class="news-empty">选择股票、收藏或市场模式查看资讯</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 底部状态栏 -->
                <div class="status-bar">
                    <div class="status-bar-left">
                        <div class="status-bar-item">
                            <i class="fas fa-database" style="font-size:10px"></i>
                            <span>DuckDB</span>
                        </div>
                        <div class="status-bar-item">
                            <i class="fas fa-clock" style="font-size:10px"></i>
                            <span id="lastUpdate">--</span>
                        </div>
                        <div class="status-bar-item">
                            <i class="fas fa-chart-bar" style="font-size:10px"></i>
                            <span id="dataStats">--</span>
                        </div>
                    </div>
                    <div>
                        <span>PandaAI QuantFlow v1.0</span>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let chart = null;
            let volumeChart = null;
            let candlestickSeries = null;
            let volumeSeries = null;
            let ma5Series = null;
            let ma10Series = null;
            let ma20Series = null;
            let currentStockData = null;
            let currentView = 'chart';
            let currentStockTab = 'all';
            let currentNewsMode = 'stock';
            let allStocksData = [];
            let currentStockName = '';
            let currentPeriod = 'day';

            // 收藏功能
            function getFavorites() {
                const favs = localStorage.getItem('stockFavorites');
                return favs ? JSON.parse(favs) : [];
            }

            function saveFavorites(favs) {
                localStorage.setItem('stockFavorites', JSON.stringify(favs));
            }

            function isFavorite(tsCode) {
                return getFavorites().includes(tsCode);
            }

            function toggleFavorite() {
                const code = document.getElementById('stockCode').value.trim();
                if (!code) return;
                
                let favs = getFavorites();
                const idx = favs.indexOf(code);
                const btn = document.getElementById('favBtn');
                
                if (idx >= 0) {
                    favs.splice(idx, 1);
                    btn.innerHTML = '<i class="far fa-star"></i>';
                    btn.classList.remove('fav-star');
                } else {
                    favs.push(code);
                    btn.innerHTML = '<i class="fas fa-star"></i>';
                    btn.classList.add('fav-star');
                }
                
                saveFavorites(favs);
                renderStockList();
            }

            function updateFavButton() {
                const code = document.getElementById('stockCode').value.trim();
                const btn = document.getElementById('favBtn');
                if (isFavorite(code)) {
                    btn.innerHTML = '<i class="fas fa-star"></i>';
                    btn.classList.add('fav-star');
                } else {
                    btn.innerHTML = '<i class="far fa-star"></i>';
                    btn.classList.remove('fav-star');
                }
            }

            function switchStockTab(tab) {
                currentStockTab = tab;
                document.getElementById('tabAll').classList.toggle('active', tab === 'all');
                document.getElementById('tabFav').classList.toggle('active', tab === 'fav');
                renderStockList();
            }

            function switchView(view) {
                currentView = view;
                document.querySelectorAll('.sidebar-item').forEach(item => item.classList.remove('active'));
                event.currentTarget.classList.add('active');
                
                document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
                document.getElementById(view + '-view').classList.add('active');
                
                if (view === 'chart' && chart) {
                    setTimeout(() => chart.applyOptions({ width: document.getElementById('klineChart').clientWidth }), 100);
                }
                if (view === 'news') {
                    setNewsMode(currentNewsMode || 'stock');
                }
            }

            function formatNumber(num, decimals = 2) {
                if (num === null || num === undefined || isNaN(num)) return '--';
                return Number(num).toFixed(decimals);
            }

            function formatVolume(num) {
                if (!num || isNaN(num)) return '--';
                if (num >= 100000000) return (num / 100000000).toFixed(2) + '亿';
                if (num >= 10000) return (num / 10000).toFixed(2) + '万';
                return num.toFixed(0);
            }

            async function loadKline() {
                const code = document.getElementById('stockCode').value.trim();
                if (!code) {
                    alert('\u8bf7\u8f93\u5165\u80a1\u7968\u4ee3\u7801');
                    return;
                }
                
                try {
                    const [klineRes, latestRes, indicatorRes] = await Promise.all([
                        fetch(`/api/stock/${code}/kline?limit=5000`),
                        fetch(`/api/stock/${code}/latest`),
                        fetch(`/api/stock/${code}/indicators`)
                    ]);
                    
                    const klineResult = await klineRes.json();
                    const latestResult = await latestRes.json();
                    const indicatorResult = await indicatorRes.json();
                    
                    if (!klineResult.success || klineResult.data.length === 0) {
                        alert('未找到该股票数据');
                        return;
                    }
                    
                    let displayData = klineResult.data;
                    if (currentPeriod === 'week') {
                        displayData = aggregateToWeekly(klineResult.data);
                    } else if (currentPeriod === 'month') {
                        displayData = aggregateToMonthly(klineResult.data);
                    }
                    
                    currentStockData = displayData;
                    renderChart(displayData);
                    renderVolumeChart(displayData);
                    
                    if (latestResult.success && latestResult.data.length > 0) {
                        updatePriceInfo(latestResult.data[0]);
                    }
                    
                    if (indicatorResult.success && indicatorResult.data.summary) {
                        updateIndicators(indicatorResult.data.summary);
                        generateSignals(indicatorResult.data.summary);
                        updateTrendAnalysis(indicatorResult.data.summary, displayData);
                        updateVolatilityAnalysis(displayData);
                        updateVolumeAnalysis(displayData);
                        updateIndicatorAnalysis(indicatorResult.data.summary);
                    }
                    
                    const displayName = klineResult.stock_name && klineResult.stock_name !== code
                        ? `${code} ${klineResult.stock_name}`
                        : (currentStockName ? `${code} ${currentStockName}` : code);
                    document.getElementById('chartStockName').textContent = displayName;
                    updateFavButton();
                } catch (error) {
                    console.error('\u52a0\u8f7dK\u7ebf\u5931\u8d25', error);
                    alert('\u52a0\u8f7dK\u7ebf\u5931\u8d25');
                }
            }

            function renderChart(data) {
                const container = document.getElementById('klineChart');
                container.innerHTML = '';
                
                if (chart) chart.remove();
                
                chart = LightweightCharts.createChart(container, {
                    layout: {
                        background: { type: 'solid', color: '#161b22' },
                        textColor: '#8b949e'
                    },
                    grid: {
                        vertLines: { color: '#21262d', style: 2 },
                        horzLines: { color: '#21262d', style: 2 }
                    },
                    crosshair: {
                        mode: LightweightCharts.CrosshairMode.Normal,
                        vertLine: { color: '#58a6ff', width: 1, style: 3 },
                        horzLine: { color: '#58a6ff', width: 1, style: 3 }
                    },
                    rightPriceScale: {
                        borderColor: '#30363d',
                        scaleMargins: { top: 0.15, bottom: 0.15 },
                        autoScale: true
                    },
                    timeScale: {
                        borderColor: '#30363d',
                        timeVisible: false,
                        fixLeftEdge: true,
                        fixRightEdge: true
                    },
                    handleScroll: { vertTouchDrag: false }
                });
                
                candlestickSeries = chart.addCandlestickSeries({
                    upColor: '#f85149',
                    downColor: '#3fb950',
                    borderDownColor: '#3fb950',
                    borderUpColor: '#f85149',
                    wickDownColor: '#3fb950',
                    wickUpColor: '#f85149'
                });
                
                const chartData = data.map(d => ({
                    time: d.time.split(' ')[0],
                    open: d.open,
                    high: d.high,
                    low: d.low,
                    close: d.close
                }));
                
                candlestickSeries.setData(chartData);
                
                // 添加MA线
                const ma5Data = calculateMA(chartData, 5);
                const ma10Data = calculateMA(chartData, 10);
                const ma20Data = calculateMA(chartData, 20);
                
                ma5Series = chart.addLineSeries({ color: '#58a6ff', lineWidth: 1, title: 'MA5', lastValueVisible: false });
                ma10Series = chart.addLineSeries({ color: '#a371f7', lineWidth: 1, title: 'MA10', lastValueVisible: false });
                ma20Series = chart.addLineSeries({ color: '#d29922', lineWidth: 1, title: 'MA20', lastValueVisible: false });
                
                ma5Series.setData(ma5Data);
                ma10Series.setData(ma10Data);
                ma20Series.setData(ma20Data);
                
                // 默认显示最近500条数据，保留全部历史数据可缩放查看
                if (chartData.length > 500) {
                    const startIndex = chartData.length - 500;
                    chart.timeScale().setVisibleLogicalRange({
                        from: startIndex,
                        to: chartData.length - 1
                    });
                } else {
                    chart.timeScale().fitContent();
                }
                
                // 同步缩放
                chart.timeScale().subscribeVisibleTimeRangeChange(() => {
                    if (volumeChart) {
                        volumeChart.timeScale().setVisibleLogicalRange(chart.timeScale().getVisibleLogicalRange());
                    }
                });
            }

            function calculateMA(data, period) {
                const ma = [];
                for (let i = period - 1; i < data.length; i++) {
                    let sum = 0;
                    for (let j = 0; j < period; j++) {
                        sum += data[i - j].close;
                    }
                    ma.push({ time: data[i].time, value: sum / period });
                }
                return ma;
            }

            function renderVolumeChart(data) {
                const container = document.getElementById('volumeChart');
                container.innerHTML = '';
                
                if (volumeChart) volumeChart.remove();
                
                volumeChart = LightweightCharts.createChart(container, {
                    layout: {
                        background: { type: 'solid', color: '#161b22' },
                        textColor: '#8b949e'
                    },
                    grid: {
                        vertLines: { color: '#21262d', style: 2 },
                        horzLines: { color: '#21262d', style: 2 }
                    },
                    rightPriceScale: {
                        borderColor: '#30363d',
                        scaleMargins: { top: 0.2, bottom: 0 }
                    },
                    timeScale: {
                        visible: false
                    },
                    handleScroll: false,
                    handleScale: false
                });
                
                volumeSeries = volumeChart.addHistogramSeries({
                    color: '#58a6ff'
                });
                
                const volumeData = data.map(d => ({
                    time: d.time.split(' ')[0],
                    value: d.volume,
                    color: d.close >= d.open ? '#f8514966' : '#3fb95066'
                }));
                
                volumeSeries.setData(volumeData);
                
                // 默认显示最近500条数据
                if (volumeData.length > 500) {
                    const startIndex = volumeData.length - 500;
                    volumeChart.timeScale().setVisibleLogicalRange({
                        from: startIndex,
                        to: volumeData.length - 1
                    });
                }
            }

            function updatePriceInfo(stock) {
                const close = stock.close || 0;
                const pctChange = stock.pct_chg || 0;
                const changeClass = pctChange >= 0 ? 'up' : 'down';
                
                const currentPrice = document.getElementById('currentPrice');
                const pctChangeEl = document.getElementById('pctChange');
                const openPrice = document.getElementById('openPrice');
                const preClose = document.getElementById('preClose');
                const highPrice = document.getElementById('highPrice');
                const lowPrice = document.getElementById('lowPrice');
                const volume = document.getElementById('volume');
                const amount = document.getElementById('amount');
                
                if (currentPrice) { currentPrice.textContent = formatNumber(close); currentPrice.className = 'price-main ' + changeClass; }
                if (pctChangeEl) { pctChangeEl.textContent = (pctChange >= 0 ? '+' : '') + formatNumber(pctChange) + '%'; pctChangeEl.className = 'price-change ' + changeClass; }
                if (openPrice) openPrice.textContent = formatNumber(stock.open);
                if (preClose) preClose.textContent = formatNumber(stock.pre_close);
                if (highPrice) highPrice.textContent = formatNumber(stock.high);
                if (lowPrice) lowPrice.textContent = formatNumber(stock.low);
                if (volume) volume.textContent = formatVolume(stock.vol);
                if (amount) amount.textContent = formatVolume(stock.amount);
            }

            function updateIndicators(s) {
                const ma5 = document.getElementById('ma5');
                const ma10 = document.getElementById('ma10');
                const ma20 = document.getElementById('ma20');
                const macd = document.getElementById('macd');
                const rsi = document.getElementById('rsi');
                const rsiSignal = document.getElementById('rsiSignal');
                const kdjK = document.getElementById('kdjK');
                const bollUp = document.getElementById('bollUp');
                const bollDown = document.getElementById('bollDown');
                
                if (ma5) ma5.textContent = formatNumber(s.MA5);
                if (ma10) ma10.textContent = formatNumber(s.MA10);
                if (ma20) ma20.textContent = formatNumber(s.MA20);
                if (macd) macd.textContent = formatNumber(s.MACD);
                if (rsi) rsi.textContent = formatNumber(s.RSI);
                
                if (rsiSignal) {
                    if (s.RSI > 70) { rsiSignal.textContent = '超买'; rsiSignal.className = 'signal-badge signal-sell'; }
                    else if (s.RSI < 30) { rsiSignal.textContent = '超卖'; rsiSignal.className = 'signal-badge signal-buy'; }
                    else { rsiSignal.textContent = '中性'; rsiSignal.className = 'signal-badge signal-neutral'; }
                }
                
                if (kdjK) kdjK.textContent = formatNumber(s.K);
                if (bollUp) bollUp.textContent = formatNumber(s.BOLL_UP);
                if (bollDown) bollDown.textContent = formatNumber(s.BOLL_DOWN);
            }

            function generateSignals(s) {
                const tradeSignals = document.getElementById('tradeSignals');
                if (!tradeSignals) return;
                
                const signals = [];
                
                if (s.MACD > 0 && s.MACD > s.SIGNAL) signals.push({ name: 'MACD', signal: '买入', class: 'signal-buy' });
                else if (s.MACD < 0 && s.MACD < s.SIGNAL) signals.push({ name: 'MACD', signal: '卖出', class: 'signal-sell' });

                if (s.RSI < 30) signals.push({ name: 'RSI', signal: '超卖反弹', class: 'signal-buy' });
                else if (s.RSI > 70) signals.push({ name: 'RSI', signal: '超买回调', class: 'signal-sell' });

                if (s.K > s.D && s.K < 20) signals.push({ name: 'KDJ', signal: '金叉买入', class: 'signal-buy' });
                else if (s.K < s.D && s.K > 80) signals.push({ name: 'KDJ', signal: '死叉卖出', class: 'signal-sell' });
                
                const html = signals.length > 0 
                    ? signals.map(sig => `
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border-color)">
                            <span style="font-size:12px">${sig.name}</span>
                            <span class="signal-badge ${sig.class}">${sig.signal}</span>
                        </div>
                    `).join('')
                    : '<div style="padding:12px;text-align:center;color:var(--text-secondary);font-size:12px">暂无明确信号</div>';
                
                tradeSignals.innerHTML = html;
            }

            function updateTrendAnalysis(s, data) {
                const prices = data.map(d => d.close).filter(v => v !== null && v !== undefined);
                const len = prices.length;
                if (len < 20) {
                    document.getElementById('trendAnalysis').innerHTML = '<div style="padding:12px;text-align:center;color:var(--text-secondary);font-size:12px">\u6570\u636e\u4e0d\u8db3</div>';
                    return;
                }
                const current = prices[len - 1];
                const ma5 = prices.slice(-5).reduce((a,b)=>a+b,0) / 5;
                const ma20 = prices.slice(-20).reduce((a,b)=>a+b,0) / 20;
                const ma60 = len >= 60 ? prices.slice(-60).reduce((a,b)=>a+b,0) / 60 : ma20;
                const change5d = ((current - prices[len-5]) / prices[len-5] * 100).toFixed(2);
                const change20d = ((current - prices[len-20]) / prices[len-20] * 100).toFixed(2);
                let trend = '\u9707\u8361';
                if (current > ma5 && ma5 > ma20 && ma20 > ma60) trend = '\u5f3a\u52bf\u4e0a\u6da8';
                else if (current > ma5 && ma5 > ma20) trend = '\u4e0a\u6da8\u8d8b\u52bf';
                else if (current < ma5 && ma5 < ma20 && ma20 < ma60) trend = '\u5f3a\u52bf\u4e0b\u8dcc';
                else if (current < ma5 && ma5 < ma20) trend = '\u4e0b\u8dcc\u8d8b\u52bf';
                document.getElementById('trendAnalysis').innerHTML = `
                    <div style="padding:8px 0">
                        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-color)"><span style="font-size:12px;color:var(--text-secondary)">\u77ed\u671f\u8d8b\u52bf(5\u65e5)</span><span style="font-size:12px;font-weight:600;color:${change5d>=0?'var(--accent-green)':'var(--accent-red)'}">${change5d>=0?'+':''}${change5d}%</span></div>
                        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-color)"><span style="font-size:12px;color:var(--text-secondary)">\u4e2d\u671f\u8d8b\u52bf(20\u65e5)</span><span style="font-size:12px;font-weight:600;color:${change20d>=0?'var(--accent-green)':'var(--accent-red)'}">${change20d>=0?'+':''}${change20d}%</span></div>
                        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-color)"><span style="font-size:12px;color:var(--text-secondary)">\u5747\u7ebf\u6392\u5217</span><span class="signal-badge ${trend.includes('\u4e0a\u6da8')?'signal-buy':trend.includes('\u4e0b\u8dcc')?'signal-sell':'signal-neutral'}">${trend}</span></div>
                        <div style="display:flex;justify-content:space-between;padding:6px 0"><span style="font-size:12px;color:var(--text-secondary)">\u5f53\u524d vs MA20</span><span style="font-size:12px;color:${current>=ma20?'var(--accent-green)':'var(--accent-red)'}">${current>=ma20?'\u4e0a\u65b9':'\u4e0b\u65b9'} ${Math.abs((current-ma20)/ma20*100).toFixed(2)}%</span></div>
                    </div>`;
            }

            function updateVolatilityAnalysis(data) {
                const returns = [];
                for (let i = 1; i < data.length; i++) if (data[i-1].close && data[i].close) returns.push((data[i].close - data[i-1].close) / data[i-1].close * 100);
                if (returns.length < 5) {
                    document.getElementById('volatilityAnalysis').innerHTML = '<div style="padding:12px;text-align:center;color:var(--text-secondary);font-size:12px">\u6570\u636e\u4e0d\u8db3</div>';
                    return;
                }
                const avg = returns.reduce((a,b)=>a+b,0) / returns.length;
                const volatility = Math.sqrt(returns.reduce((sum,r)=>sum + Math.pow(r - avg, 2), 0) / returns.length);
                const maxReturn = Math.max(...returns);
                const minReturn = Math.min(...returns);
                let volLevel = '\u4e2d\u7b49';
                if (volatility < 1.5) volLevel = '\u4f4e\u6ce2\u52a8';
                else if (volatility > 3.5) volLevel = '\u9ad8\u6ce2\u52a8';
                document.getElementById('volatilityAnalysis').innerHTML = `
                    <div style="padding:8px 0">
                        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-color)"><span style="font-size:12px;color:var(--text-secondary)">\u65e5\u6ce2\u52a8\u7387</span><span style="font-size:12px;font-weight:600">${volatility.toFixed(2)}%</span></div>
                        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-color)"><span style="font-size:12px;color:var(--text-secondary)">\u6ce2\u52a8\u7b49\u7ea7</span><span class="signal-badge ${volLevel==='\u9ad8\u6ce2\u52a8'?'signal-sell':volLevel==='\u4f4e\u6ce2\u52a8'?'signal-buy':'signal-neutral'}">${volLevel}</span></div>
                        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-color)"><span style="font-size:12px;color:var(--text-secondary)">\u6700\u5927\u5355\u65e5\u6da8\u5e45</span><span style="font-size:12px;color:var(--accent-green)">+${maxReturn.toFixed(2)}%</span></div>
                        <div style="display:flex;justify-content:space-between;padding:6px 0"><span style="font-size:12px;color:var(--text-secondary)">\u6700\u5927\u5355\u65e5\u8dcc\u5e45</span><span style="font-size:12px;color:var(--accent-red)">${minReturn.toFixed(2)}%</span></div>
                    </div>`;
            }

            function updateVolumeAnalysis(data) {
                const volumes = data.map(d => d.volume || 0);
                const len = volumes.length;
                if (len < 5) {
                    document.getElementById('volumeAnalysis').innerHTML = '<div style="padding:12px;text-align:center;color:var(--text-secondary);font-size:12px">\u6570\u636e\u4e0d\u8db3</div>';
                    return;
                }
                const current = volumes[len - 1];
                const avg5 = volumes.slice(-5).reduce((a,b)=>a+b,0) / 5;
                const ratio5 = avg5 ? current / avg5 : 0;
                let volSignal = '\u6b63\u5e38';
                if (ratio5 > 1.5) volSignal = '\u653e\u91cf';
                else if (ratio5 < 0.8) volSignal = '\u7f29\u91cf';
                document.getElementById('volumeAnalysis').innerHTML = `
                    <div style="padding:8px 0">
                        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-color)"><span style="font-size:12px;color:var(--text-secondary)">\u5f53\u524d\u6210\u4ea4\u91cf</span><span style="font-size:12px;font-weight:600">${(current/10000).toFixed(2)}\u4e07\u624b</span></div>
                        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-color)"><span style="font-size:12px;color:var(--text-secondary)">5\u65e5\u5747\u91cf</span><span style="font-size:12px">${(avg5/10000).toFixed(2)}\u4e07\u624b</span></div>
                        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-color)"><span style="font-size:12px;color:var(--text-secondary)">\u91cf\u6bd4(5\u65e5)</span><span style="font-size:12px;color:${ratio5>1.5?'var(--accent-green)':ratio5<0.8?'var(--accent-red)':'var(--text-secondary)'}">${ratio5.toFixed(2)}x</span></div>
                        <div style="display:flex;justify-content:space-between;padding:6px 0"><span style="font-size:12px;color:var(--text-secondary)">\u91cf\u80fd\u4fe1\u53f7</span><span class="signal-badge ${volSignal==='\u653e\u91cf'?'signal-buy':volSignal==='\u7f29\u91cf'?'signal-sell':'signal-neutral'}">${volSignal}</span></div>
                    </div>`;
            }

            function updateIndicatorAnalysis(s) {
                if (!s) return;
                let score = 50;
                const reasons = [];
                if (s.MACD > 0) { score += 10; reasons.push('MACD\u6b63\u503c'); } else { score -= 10; reasons.push('MACD\u8d1f\u503c'); }
                if (s.MACD > s.SIGNAL) { score += 10; reasons.push('MACD\u91d1\u53c9'); } else { score -= 10; reasons.push('MACD\u6b7b\u53c9'); }
                if (s.RSI > 30 && s.RSI < 70) { score += 5; reasons.push('RSI\u6b63\u5e38'); } else if (s.RSI < 30) { score += 15; reasons.push('RSI\u8d85\u5356'); } else { score -= 10; reasons.push('RSI\u8d85\u4e70'); }
                if (s.K > s.D) { score += 10; reasons.push('KDJ\u91d1\u53c9'); } else { score -= 10; reasons.push('KDJ\u6b7b\u53c9'); }
                if (s.close > s.MA20) { score += 10; reasons.push('\u4ef7\u683c\u4e0a\u7a7fMA20'); } else { score -= 10; reasons.push('\u4ef7\u683c\u4e0b\u7a7fMA20'); }
                score = Math.max(0, Math.min(100, score));
                let rating = '\u4e2d\u6027';
                let ratingClass = 'signal-neutral';
                if (score >= 70) { rating = '\u5f3a\u70c8\u770b\u591a'; ratingClass = 'signal-buy'; }
                else if (score >= 55) { rating = '\u504f\u591a'; ratingClass = 'signal-buy'; }
                else if (score <= 30) { rating = '\u5f3a\u70c8\u770b\u7a7a'; ratingClass = 'signal-sell'; }
                else if (score <= 45) { rating = '\u504f\u7a7a'; ratingClass = 'signal-sell'; }
                document.getElementById('indicatorAnalysis').innerHTML = `<div style="padding:8px 0"><div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-color)"><span style="font-size:12px;color:var(--text-secondary)">\u7efc\u5408\u8bc4\u5206</span><span style="font-size:16px;font-weight:700;color:${score>=60?'var(--accent-green)':score<=40?'var(--accent-red)':'var(--text-secondary)'}">${score}</span></div><div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-color)"><span style="font-size:12px;color:var(--text-secondary)">\u8bc4\u7ea7</span><span class="signal-badge ${ratingClass}">${rating}</span></div><div style="padding:6px 0"><div style="font-size:11px;color:var(--text-secondary);margin-bottom:4px">\u5173\u952e\u56e0\u5b50</div><div style="display:flex;flex-wrap:wrap;gap:4px">${reasons.map(r => `<span style="font-size:10px;padding:2px 6px;background:var(--bg-tertiary);border-radius:3px;color:var(--text-secondary)">${r}</span>`).join('')}</div></div></div>`;
            }
            async function loadStockList() {
                try {
                    const response = await fetch('/api/stocks');
                    const result = await response.json();
                    if (result.success) {
                        allStocksData = result.data;
                        renderStockList();
                    }
                } catch (error) {
                    console.error('\u52a0\u8f7d\u80a1\u7968\u5217\u8868\u5931\u8d25:', error);
                }
            }

            function renderStockList() {
                const favs = getFavorites();
                let stocksToShow = allStocksData;
                
                if (currentStockTab === 'fav') {
                    stocksToShow = allStocksData.filter(s => favs.includes(s.ts_code));
                }
                
                document.getElementById('stockCount').textContent = stocksToShow.length + ' \u53ea';
                
                const listHtml = stocksToShow.map(stock => {
                    const name = stock.name && stock.name !== stock.ts_code ? stock.name : '';
                    const displayName = name ? `${stock.ts_code} <span style="color:var(--text-secondary);font-size:11px;margin-left:4px">${name}</span>` : stock.ts_code;
                    const isFav = favs.includes(stock.ts_code);
                    return `
                        <div class="stock-list-item ${isFav ? 'favorite' : ''}" onclick="selectStock('${stock.ts_code}', '${name || ''}')" data-code="${stock.ts_code}">
                            <div class="stock-list-item-header">
                                <span class="stock-list-code">${displayName}</span>
                                <span class="fav-icon"><i class="fas fa-star"></i></span>
                            </div>
                            <div class="stock-list-info">
                                <span>${stock.industry || ''}</span>
                                <span>${stock.start_date || ''} ~ ${stock.end_date || ''}</span>
                            </div>
                        </div>
                    `}).join('');
                
                document.getElementById('stockList').innerHTML = listHtml || '<div style="padding:20px;text-align:center;color:var(--text-secondary);font-size:12px">\u6682\u65e0\u80a1\u7968</div>';
            }

            function filterStocks() {
                const search = document.getElementById('searchStock').value.toLowerCase();
                const items = document.querySelectorAll('.stock-list-item');
                items.forEach(item => {
                    const text = item.textContent.toLowerCase();
                    item.style.display = text.includes(search) ? 'block' : 'none';
                });
            }

            async function selectStock(code, name) {
                document.getElementById('stockCode').value = code;
                currentStockName = name || '';
                document.querySelectorAll('.stock-list-item').forEach(item => item.classList.remove('active'));
                if (event && event.currentTarget) {
                    event.currentTarget.classList.add('active');
                }
                updateFavButton();
                loadKline();
            }

            function setPeriod(period) {
                document.querySelectorAll('.chart-action-btn').forEach(btn => {
                    if (btn.textContent.includes('\u7ebf')) btn.classList.remove('active');
                });
                event.target.classList.add('active');
                currentPeriod = period;
                loadKline();
            }

            function aggregateToWeekly(data) {
                const weekly = [];
                let currentWeek = null;
                
                data.forEach(d => {
                    const date = new Date(d.time);
                    const weekStart = new Date(date);
                    weekStart.setDate(date.getDate() - date.getDay() + 1);
                    const weekKey = weekStart.toISOString().split('T')[0];
                    
                    if (!currentWeek || currentWeek.time !== weekKey) {
                        if (currentWeek) weekly.push(currentWeek);
                        currentWeek = {
                            time: weekKey,
                            open: d.open,
                            high: d.high,
                            low: d.low,
                            close: d.close,
                            volume: d.volume || 0
                        };
                    } else {
                        currentWeek.high = Math.max(currentWeek.high, d.high);
                        currentWeek.low = Math.min(currentWeek.low, d.low);
                        currentWeek.close = d.close;
                        currentWeek.volume += (d.volume || 0);
                    }
                });
                if (currentWeek) weekly.push(currentWeek);
                return weekly;
            }

            function aggregateToMonthly(data) {
                const monthly = [];
                let currentMonth = null;
                
                data.forEach(d => {
                    const monthKey = d.time.substring(0, 7) + '-01';
                    
                    if (!currentMonth || currentMonth.time !== monthKey) {
                        if (currentMonth) monthly.push(currentMonth);
                        currentMonth = {
                            time: monthKey,
                            open: d.open,
                            high: d.high,
                            low: d.low,
                            close: d.close,
                            volume: d.volume || 0
                        };
                    } else {
                        currentMonth.high = Math.max(currentMonth.high, d.high);
                        currentMonth.low = Math.min(currentMonth.low, d.low);
                        currentMonth.close = d.close;
                        currentMonth.volume += (d.volume || 0);
                    }
                });
                if (currentMonth) monthly.push(currentMonth);
                return monthly;
            }

            function toggleMA() {
                event.target.classList.toggle('active');
                const visible = event.target.classList.contains('active');
                if (ma5Series) ma5Series.applyOptions({ visible });
                if (ma10Series) ma10Series.applyOptions({ visible });
                if (ma20Series) ma20Series.applyOptions({ visible });
            }

            function toggleBOLL() {
                event.target.classList.toggle('active');
            }

            async function refreshData() {
                await loadKline();
            }
            function escapeHtml(value) {
                return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
            }

            function setNewsMode(mode) {
                currentNewsMode = mode;
                ['Stock', 'Fav', 'Market'].forEach(name => {
                    const id = `newsMode${name}`;
                    const el = document.getElementById(id);
                    if (el) el.classList.remove('active');
                });
                const activeId = mode === 'stock' ? 'newsModeStock' : (mode === 'favorites' ? 'newsModeFav' : 'newsModeMarket');
                document.getElementById(activeId)?.classList.add('active');
                document.getElementById('newsStockField').style.display = mode === 'stock' ? 'block' : 'none';
                const favCount = getFavorites().length;
                const hints = {
                    stock: '按股票名称/代码搜索最近 30 天资讯，可切换单一来源或全部来源聚合。',
                    favorites: `将聚合本机收藏列表中的股票资讯，当前收藏 ${favCount} 只。`,
                    market: '市场模式会拉取 A 股关键词资讯，适合快速看盘前盘后消息。'
                };
                document.getElementById('newsHint').textContent = hints[mode];
                loadNews();
            }

            function syncNewsStockWithChart() {
                const chartCode = document.getElementById('stockCode').value.trim();
                if (chartCode) {
                    document.getElementById('newsStockCode').value = chartCode;
                    setNewsMode('stock');
                }
            }

            function setNewsLoading(text) {
                document.getElementById('newsStatus').textContent = text;
                document.getElementById('newsList').innerHTML = `<div class="news-empty"><i class="fas fa-spinner fa-spin"></i> ${text}</div>`;
            }

            function setNewsError(message) {
                document.getElementById('newsStatus').textContent = '加载失败';
                document.getElementById('newsList').innerHTML = `<div class="news-empty" style="color:var(--accent-red)">${escapeHtml(message)}</div>`;
            }

            async function loadNews() {
                if (currentNewsMode === 'favorites') return loadFavoritesNews();
                if (currentNewsMode === 'market') return loadMarketNews();
                return loadStockNews();
            }

            async function loadStockNews() {
                const code = document.getElementById('newsStockCode').value.trim().toUpperCase();
                const src = document.getElementById('newsSource').value;
                if (!code) {
                    renderNewsList({ success: true, data: [] }, '请输入股票代码');
                    return;
                }
                setNewsLoading('加载单股资讯...');
                try {
                    const response = await fetch(`/api/news?ts_code=${encodeURIComponent(code)}&src=${encodeURIComponent(src)}&limit=80`);
                    renderNewsList(await response.json());
                } catch (error) {
                    setNewsError(error.message);
                }
            }

            async function loadFavoritesNews() {
                const favs = getFavorites();
                if (favs.length === 0) {
                    renderNewsList({ success: true, data: [] }, '暂无收藏股票，请先在K线图中点星标收藏。');
                    return;
                }
                const src = document.getElementById('newsSource').value;
                setNewsLoading('聚合收藏股票资讯...');
                try {
                    const response = await fetch('/api/news/favorites', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ stock_codes: favs, src, limit_per_stock: 12, total_limit: 100 })
                    });
                    renderNewsList(await response.json());
                } catch (error) {
                    setNewsError(error.message);
                }
            }

            async function loadMarketNews() {
                const src = document.getElementById('newsSource').value;
                setNewsLoading('加载市场要闻...');
                try {
                    const response = await fetch(`/api/news?keyword=${encodeURIComponent('A股')}&src=${encodeURIComponent(src)}&limit=80`);
                    renderNewsList(await response.json());
                } catch (error) {
                    setNewsError(error.message);
                }
            }

            function renderNewsList(result, emptyText = '暂无新闻') {
                if (!result.success) {
                    setNewsError(result.message || '资讯加载失败');
                    document.getElementById('newsCount').textContent = '';
                    return;
                }
                const items = result.data || [];
                document.getElementById('newsCount').textContent = items.length ? `(${items.length}条)` : '';
                document.getElementById('newsStatus').textContent = items.length ? `更新于 ${new Date().toLocaleTimeString()}` : '无结果';
                if (items.length === 0) {
                    document.getElementById('newsList').innerHTML = `<div class="news-empty">${escapeHtml(emptyText)}</div>`;
                    return;
                }
                document.getElementById('newsList').innerHTML = items.map(item => {
                    const title = escapeHtml(item.title || '无标题');
                    const time = escapeHtml(item.datetime || item.time || item.pub_time || '未知时间');
                    const source = escapeHtml(item.src || item.source || result.source || 'unknown');
                    const url = item.url ? escapeHtml(item.url) : '#';
                    const stockCode = item.stock_code ? `<span class="news-pill"><i class="fas fa-tag"></i>${escapeHtml(item.stock_code)}</span>` : '';
                    const openAction = item.url ? `<a class="news-pill" href="${url}" target="_blank" rel="noopener"><i class="fas fa-external-link-alt"></i>原文</a>` : '';
                    return `
                        <div class="news-card">
                            <a class="news-card-title" href="${url}" target="_blank" rel="noopener">${title}</a>
                            <div class="news-meta">
                                ${stockCode}
                                <span class="news-pill"><i class="far fa-newspaper"></i>${source}</span>
                                <span class="news-pill"><i class="far fa-clock"></i>${time}</span>
                                ${openAction}
                            </div>
                        </div>
                    `;
                }).join('');
            }

            async function executeQuery() {
                const query = document.getElementById('sqlQuery').value;
                try {
                    const response = await fetch(`/api/query?query=${encodeURIComponent(query)}`);
                    const result = await response.json();
                    if (result.success) {
                        if (result.data.length === 0) {
                            document.getElementById('queryResult').innerHTML = '<p style="color:var(--text-secondary);text-align:center">\u65e0\u6570\u636e\u8fd4\u56de</p>';
                            return;
                        }
                        const columns = Object.keys(result.data[0]);
                        let html = '<table class="data-table"><thead><tr>';
                        columns.forEach(col => html += `<th>${col}</th>`);
                        html += '</tr></thead><tbody>';
                        result.data.forEach(row => {
                            html += '<tr>';
                            columns.forEach(col => {
                                const val = row[col];
                                html += `<td>${val !== null ? val : 'NULL'}</td>`;
                            });
                            html += '</tr>';
                        });
                        html += '</tbody></table>';
                        document.getElementById('queryResult').innerHTML = html;
                    } else {
                        document.getElementById('queryResult').innerHTML = `<p style="color:var(--accent-red)">\u9519\u8bef: ${result.message}</p>`;
                    }
                } catch (error) {
                    document.getElementById('queryResult').innerHTML = `<p style="color:var(--accent-red)">\u67e5\u8be2\u5931\u8d25: ${error.message}</p>`;
                }
            }

            function setQuery(query) {
                document.getElementById('sqlQuery').value = query;
            }

            async function syncAllData() {
                document.getElementById('syncResult').innerHTML = '<div style="padding:12px;color:var(--accent-blue)"><i class="fas fa-spinner fa-spin"></i> \u540c\u6b65\u4e2d...</div>';
                try {
                    const response = await fetch('/api/sync', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
                    const result = await response.json();
                    if (result.success) {
                        document.getElementById('syncResult').innerHTML = `
                            <div style="padding:12px;background:var(--bg-tertiary);border-radius:6px">
                                <div style="color:var(--accent-green);margin-bottom:8px"><i class="fas fa-check"></i> \u540c\u6b65\u5b8c\u6210</div>
                                <div style="font-size:12px;color:var(--text-secondary)">\u6210\u529f: ${result.data.success_stocks} | \u5931\u8d25: ${result.data.failed_stocks} | \u603b\u8bb0\u5f55: ${result.data.total_records}</div>
                            </div>`;
                    } else {
                        document.getElementById('syncResult').innerHTML = '<div style="padding:12px;color:var(--accent-red)">\u540c\u6b65\u5931\u8d25</div>';
                    }
                } catch (error) {
                    document.getElementById('syncResult').innerHTML = `<div style="padding:12px;color:var(--accent-red)">\u540c\u6b65\u5931\u8d25: ${error.message}</div>`;
                }
            }

            async function syncDailyData() {
                document.getElementById('syncResult').innerHTML = '<div style="padding:12px;color:var(--accent-blue)"><i class="fas fa-spinner fa-spin"></i> \u66f4\u65b0\u4e2d...</div>';
                try {
                    const response = await fetch('/api/sync/daily', { method: 'POST' });
                    const result = await response.json();
                    document.getElementById('syncResult').innerHTML = `
                        <div style="padding:12px;background:var(--bg-tertiary);border-radius:6px">
                            <div style="color:var(--accent-green);margin-bottom:8px"><i class="fas fa-check"></i> \u66f4\u65b0\u5b8c\u6210</div>
                            <div style="font-size:12px;color:var(--text-secondary)">${result.message}</div>
                        </div>`;
                } catch (error) {
                    document.getElementById('syncResult').innerHTML = `<div style="padding:12px;color:var(--accent-red)">\u66f4\u65b0\u5931\u8d25: ${error.message}</div>`;
                }
            }

            async function checkHealth() {
                try {
                    await fetch('/api/health');
                    document.getElementById('systemStatus').textContent = '\u7cfb\u7edf\u6b63\u5e38';
                    document.querySelector('.status-dot').style.background = 'var(--accent-green)';
                } catch (error) {
                    document.getElementById('systemStatus').textContent = '\u7cfb\u7edf\u5f02\u5e38';
                    document.querySelector('.status-dot').style.background = 'var(--accent-red)';
                }
            }

            async function loadStats() {
                try {
                    const response = await fetch('/api/stocks');
                    const result = await response.json();
                    if (result.success) {
                        document.getElementById('dataStats').textContent = result.total + ' \u53ea\u80a1\u7968';
                    }
                } catch (e) {}
            }

            window.onload = function() {
                loadStockList();
                checkHealth();
                loadStats();
                setInterval(checkHealth, 30000);
                document.getElementById('lastUpdate').textContent = new Date().toLocaleString('zh-CN');
                setTimeout(() => loadKline(), 500);
            };

            window.addEventListener('resize', () => {
                if (chart) chart.applyOptions({ width: document.getElementById('klineChart').clientWidth });
                if (volumeChart) volumeChart.applyOptions({ width: document.getElementById('volumeChart').clientWidth });
            });
        </script>
    </body>
    </html>
    """
    return html_content


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
