import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database import DuckDBManager
from src.data_sync import StockDataSync
from datetime import datetime, timedelta
import logging
import time
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def sync_failed_stocks():
    """同步所有没有2026年数据的股票"""
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

        # 1. 找出所有没有2026年数据的股票
        failed_stocks = db_manager.conn.execute("""
            SELECT DISTINCT ts_code
            FROM stock_daily
            WHERE ts_code NOT IN (
                SELECT DISTINCT ts_code
                FROM stock_daily
                WHERE trade_date >= '2026-01-17'
            )
        """).fetchdf()

        if failed_stocks.empty:
            logger.info("所有股票都已同步到2026年，无需处理！")
            return

        logger.info(f"发现 {len(failed_stocks)} 只股票需要同步")

        # 2. 获取这些股票的最后日期
        stocks_df = db_manager.conn.execute("""
            SELECT ts_code, MAX(trade_date) as last_date
            FROM stock_daily
            WHERE ts_code NOT IN (
                SELECT DISTINCT ts_code
                FROM stock_daily
                WHERE trade_date >= '2026-01-17'
            )
            GROUP BY ts_code
        """).fetchdf()

        # 3. 清理这些股票的旧数据（2026年1月16日之后的）
        codes_list = stocks_df['ts_code'].tolist()
        if codes_list:
            logger.info("清理旧数据...")
            db_manager.conn.execute("""
                DELETE FROM stock_daily
                WHERE ts_code = ANY(?) AND trade_date > '2026-01-16'
            """, [codes_list])
            logger.info("已清理旧数据")

        # 4. 批量获取真实数据
        REQUEST_INTERVAL = 2.0

        success_count = 0
        failed_count = 0
        total_records = 0

        for idx, row in stocks_df.iterrows():
            ts_code = row['ts_code']
            last_date = row['last_date']

            if last_date is None:
                continue

            if hasattr(last_date, 'date'):
                last_date = last_date.date()

            start_date = last_date + timedelta(days=1)

            if start_date > today:
                continue

            start_str = start_date.strftime('%Y%m%d')
            end_str = today.strftime('%Y%m%d')

            try:
                df = data_sync.download_stock_data(ts_code, start_str, end_str)

                if df is not None and not df.empty:
                    df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.date

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
                else:
                    failed_count += 1
                    logger.warning(f"{ts_code} 无数据返回")

            except Exception as e:
                logger.error(f"获取 {ts_code} 数据失败: {e}")
                failed_count += 1

            if (idx + 1) % 10 == 0 or idx == len(stocks_df) - 1:
                logger.info(f"进度: {idx + 1}/{len(stocks_df)} | 成功: {success_count} | 失败: {failed_count} | 记录: {total_records}")

            time.sleep(REQUEST_INTERVAL)

        logger.info(f"同步完成: 成功 {success_count} 只, 失败 {failed_count} 只, 新增 {total_records} 条记录")

        # 5. 验证结果
        result = db_manager.conn.execute("""
            SELECT COUNT(DISTINCT ts_code) as stock_count,
                   MAX(trade_date) as max_date,
                   COUNT(*) as total_records
            FROM stock_daily
            WHERE trade_date >= '2026-01-17'
        """).fetchone()

        logger.info(f"2026年数据统计: {result[0]} 只股票, 最新日期: {result[1]}, 总记录: {result[2]}")

    except Exception as e:
        logger.error(f"同步失败: {e}")
        raise
    finally:
        db_manager.close()


if __name__ == "__main__":
    sync_failed_stocks()
