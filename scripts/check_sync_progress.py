import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database import DuckDBManager
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def check_progress():
    db_path = os.getenv('DB_PATH', 'data/stock_data.duckdb')
    db_manager = DuckDBManager(db_path)
    
    try:
        # 1. 总股票数
        total = db_manager.conn.execute("SELECT COUNT(DISTINCT ts_code) FROM stock_daily").fetchone()[0]
        
        # 2. 有2026年数据的股票数
        has_2026 = db_manager.conn.execute("""
            SELECT COUNT(DISTINCT ts_code) 
            FROM stock_daily 
            WHERE trade_date >= '2026-01-17'
        """).fetchone()[0]
        
        # 3. 最新日期
        max_date = db_manager.conn.execute("SELECT MAX(trade_date) FROM stock_daily").fetchone()[0]
        
        # 4. 2026年总记录数
        records_2026 = db_manager.conn.execute("""
            SELECT COUNT(*) 
            FROM stock_daily 
            WHERE trade_date >= '2026-01-17'
        """).fetchone()[0]
        
        # 5. 最新日期的股票数
        if max_date:
            latest_count = db_manager.conn.execute("""
                SELECT COUNT(DISTINCT ts_code) 
                FROM stock_daily 
                WHERE trade_date = ?
            """, [max_date]).fetchone()[0]
        else:
            latest_count = 0
        
        logger.info("=" * 50)
        logger.info(f"同步进度监控")
        logger.info("=" * 50)
        logger.info(f"数据库中总股票数: {total}")
        logger.info(f"有2026年数据的股票: {has_2026}")
        logger.info(f"最新数据日期: {max_date}")
        logger.info(f"最新日期股票数: {latest_count}")
        logger.info(f"2026年新增记录数: {records_2026}")
        logger.info(f"进度: {has_2026}/{total} ({has_2026/total*100:.1f}%)")
        logger.info("=" * 50)
        
        # 显示几只最新同步的股票
        if max_date:
            sample = db_manager.conn.execute("""
                SELECT s.ts_code, b.name, s.close, s.pct_chg
                FROM stock_daily s
                LEFT JOIN stock_basic b ON s.ts_code = b.ts_code
                WHERE s.trade_date = ?
                LIMIT 5
            """, [max_date]).fetchall()
            
            logger.info(f"\n最新日期 ({max_date}) 示例数据:")
            for row in sample:
                name = row[1] if row[1] else 'N/A'
                logger.info(f"  {row[0]} ({name}): 收盘 {row[2]:.2f}, 涨跌 {row[3]:.2f}%")
        
    except Exception as e:
        logger.error(f"查询失败: {e}")
    finally:
        db_manager.close()

if __name__ == "__main__":
    check_progress()
