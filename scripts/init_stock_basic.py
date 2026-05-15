import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database import DuckDBManager
from src.data_sync import StockDataSync
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_stock_basic():
    """初始化股票基础信息"""
    db_path = os.getenv('DB_PATH', 'data/stock_data.duckdb')
    
    # 初始化数据库管理器
    db_manager = DuckDBManager(db_path)
    logger.info("数据库管理器初始化完成")
    
    # 初始化数据同步器
    token = os.getenv('TUSHARE_TOKEN')
    data_sync = StockDataSync(token)
    logger.info("数据同步器初始化完成")
    
    if data_sync.pro is None:
        logger.error("Tushare API 未初始化，无法获取股票基础信息")
        return
    
    # 获取股票基础信息
    logger.info("正在从 Tushare 获取股票基础信息...")
    df = data_sync.get_stock_basic_info()
    
    if df.empty:
        logger.error("获取股票基础信息失败")
        return
    
    logger.info(f"获取到 {len(df)} 条股票基础信息")
    
    # 导入到数据库
    count = db_manager.import_stock_basic(df)
    logger.info(f"成功导入 {count} 条股票基础信息")
    
    # 验证
    result = db_manager.conn.execute("SELECT COUNT(*) FROM stock_basic").fetchone()
    logger.info(f"数据库中股票基础信息总数: {result[0]}")
    
    # 显示几个示例
    sample = db_manager.conn.execute("SELECT ts_code, name, industry FROM stock_basic LIMIT 5").fetchdf()
    logger.info("示例数据:")
    print(sample)
    
    db_manager.close()
    logger.info("完成")

if __name__ == "__main__":
    init_stock_basic()
