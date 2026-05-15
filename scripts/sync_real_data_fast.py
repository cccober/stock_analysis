import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database import DuckDBManager
from src.data_sync import StockDataSync
from datetime import datetime, timedelta
import logging
import time
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sync_real_data_fast(target_codes=None):
    """
    使用 Tushare API 获取真实股票数据 - 优化版本
    
    由于 Tushare 免费版限制 50次/分钟，提供两种模式：
    1. 全量同步：需要约 3 小时（5309只股票 × 2秒间隔）
    2. 指定股票同步：只同步关注的股票列表
    
    :param target_codes: 指定要同步的股票代码列表，为 None 则同步所有
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
        
        # 1. 获取需要更新的股票列表
        if target_codes:
            # 使用指定的股票列表
            stocks_df = db_manager.conn.execute("""
                SELECT DISTINCT ts_code, MAX(trade_date) as last_date
                FROM stock_daily
                WHERE ts_code = ANY(?)
                GROUP BY ts_code
            """, [target_codes]).fetchdf()
            logger.info(f"指定同步 {len(stocks_df)} 只股票")
        else:
            # 获取所有股票
            stocks_df = db_manager.conn.execute("""
                SELECT DISTINCT ts_code, MAX(trade_date) as last_date
                FROM stock_daily
                GROUP BY ts_code
            """).fetchdf()
            logger.info(f"全量同步 {len(stocks_df)} 只股票（预计需要 {len(stocks_df) * 2 / 60:.1f} 分钟）")
        
        # 2. 清理这些股票的模拟数据
        codes_list = stocks_df['ts_code'].tolist()
        if codes_list:
            logger.info("清理旧数据...")
            # 使用 IN 子句清理
            db_manager.conn.execute("""
                DELETE FROM stock_daily 
                WHERE ts_code = ANY(?) AND trade_date > '2026-01-16'
            """, [codes_list])
            logger.info("已清理模拟数据")
        
        # 3. 批量获取真实数据
        REQUEST_INTERVAL = 2.0  # Tushare 免费版限制 50次/分钟
        
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
                    # 转换日期格式
                    df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.date
                    
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
                    
                    if (idx + 1) % 10 == 0 or idx == len(stocks_df) - 1:
                        logger.info(f"进度: {idx + 1}/{len(stocks_df)} | 成功: {success_count} | 失败: {failed_count} | 记录: {total_records}")
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
        
        # 5. 显示最新数据
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
    import sys
    
    # 检查是否有命令行参数指定股票代码
    if len(sys.argv) > 1:
        # 从命令行获取股票代码列表
        target_codes = sys.argv[1].split(',')
        logger.info(f"指定同步股票: {target_codes}")
        sync_real_data_fast(target_codes)
    else:
        # 同步所有股票
        sync_real_data_fast()
