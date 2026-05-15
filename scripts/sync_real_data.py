import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database import DuckDBManager
from src.data_sync import StockDataSync
from datetime import datetime, timedelta
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sync_real_data():
    """
    使用 Tushare API 获取真实股票数据并更新到数据库
    由于 Tushare 免费版频率限制为 50次/分钟，需要控制请求速度
    """
    db_path = os.getenv('DB_PATH', 'data/stock_data.duckdb')
    db_manager = DuckDBManager(db_path)
    
    token = os.getenv('TUSHARE_TOKEN')
    data_sync = StockDataSync(token)
    
    if data_sync.pro is None:
        logger.error("Tushare API 未初始化，无法获取真实数据")
        return
    
    try:
        today = datetime.now().date()
        logger.info(f"目标日期: {today}")
        
        # 1. 获取数据库中所有股票及其最后一天数据
        stocks_df = db_manager.conn.execute("""
            SELECT DISTINCT ts_code, MAX(trade_date) as last_date
            FROM stock_daily
            GROUP BY ts_code
        """).fetchdf()
        
        total_stocks = len(stocks_df)
        logger.info(f"共有 {total_stocks} 只股票需要检查更新")
        
        # 2. 清理之前生成的模拟数据（保留原始CSV数据到2026-01-16）
        logger.info("清理旧数据...")
        db_manager.conn.execute("""
            DELETE FROM stock_daily WHERE trade_date > '2026-01-16'
        """)
        logger.info("已清理模拟数据")
        
        # 3. 批量获取真实数据 - 控制频率避免超限
        # Tushare 免费版限制: 50次/分钟 = 每1.2秒1次
        # 我们使用 2秒间隔以确保安全
        REQUEST_INTERVAL = 2.0
        
        success_count = 0
        failed_count = 0
        total_records = 0
        
        for idx, row in stocks_df.iterrows():
            ts_code = row['ts_code']
            last_date = row['last_date']
            
            if last_date is None:
                continue
            
            # 确保 last_date 是 datetime.date 类型
            if hasattr(last_date, 'date'):
                last_date = last_date.date()
            
            # 计算需要获取的日期范围
            start_date = last_date + timedelta(days=1)
            
            if start_date > today:
                continue
            
            # 转换为 Tushare 格式 (YYYYMMDD)
            start_str = start_date.strftime('%Y%m%d')
            end_str = today.strftime('%Y%m%d')
            
            try:
                # 从 Tushare 获取真实数据
                df = data_sync.download_stock_data(ts_code, start_str, end_str)
                
                if df is not None and not df.empty:
                    # 转换列名以匹配数据库表结构
                    df = df.rename(columns={
                        'trade_date': 'trade_date_str',
                        'open': 'open',
                        'high': 'high',
                        'low': 'low',
                        'close': 'close',
                        'pre_close': 'pre_close',
                        'change': 'change',
                        'pct_chg': 'pct_chg',
                        'vol': 'vol',
                        'amount': 'amount'
                    })
                    
                    # 转换日期格式
                    import pandas as pd
                    df['trade_date'] = pd.to_datetime(df['trade_date_str'], format='%Y%m%d').dt.date
                    
                    # 选择需要的列
                    df = df[['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 
                             'pre_close', 'change', 'pct_chg', 'vol', 'amount']]
                    
                    # 批量插入
                    db_manager.conn.register('temp_real_data', df)
                    db_manager.conn.execute("""
                        INSERT OR REPLACE INTO stock_daily 
                        (ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount)
                        SELECT ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
                        FROM temp_real_data
                    """)
                    db_manager.conn.unregister('temp_real_data')
                    
                    total_records += len(df)
                    success_count += 1
                    
                    if (idx + 1) % 10 == 0 or idx == total_stocks - 1:
                        logger.info(f"进度: {idx + 1}/{total_stocks} | 成功: {success_count} | 失败: {failed_count} | 记录: {total_records}")
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"获取 {ts_code} 数据失败: {e}")
                failed_count += 1
            
            # 添加延迟以避免 API 频率限制
            time.sleep(REQUEST_INTERVAL)
        
        logger.info(f"同步完成: 成功 {success_count} 只, 失败 {failed_count} 只, 新增 {total_records} 条记录")
        
        # 4. 验证更新结果
        result = db_manager.conn.execute("""
            SELECT COUNT(DISTINCT ts_code) as stock_count,
                   MAX(trade_date) as max_date,
                   COUNT(*) as total_records
            FROM stock_daily
        """).fetchone()
        
        logger.info(f"数据库统计: {result[0]} 只股票, 最新日期: {result[1]}, 总记录: {result[2]}")
        
        # 5. 显示几只股票的最新数据
        max_date = result[1]
        if max_date:
            sample = db_manager.conn.execute("""
                SELECT s.ts_code, b.name, s.trade_date, s.close, s.pct_chg
                FROM stock_daily s
                LEFT JOIN stock_basic b ON s.ts_code = b.ts_code
                WHERE s.trade_date = ?
                LIMIT 10
            """, [max_date]).fetchdf()
            
            logger.info("示例数据（最新）:")
            print(sample.to_string(index=False))
        
    except Exception as e:
        logger.error(f"同步失败: {e}")
        raise
    finally:
        db_manager.close()


if __name__ == "__main__":
    sync_real_data()
