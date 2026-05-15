#!/usr/bin/env python3
"""
数据同步脚本
用于手动触发股票数据同步
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import DuckDBManager
from src.data_sync import StockDataSync

def sync_data(ts_code: str = None, start_date: str = None, end_date: str = None, 
              db_path: str = "data/stock_data.duckdb"):
    """
    同步股票数据
    
    :param ts_code: 股票代码，如果为None则同步所有股票
    :param start_date: 开始日期 (YYYYMMDD)
    :param end_date: 结束日期 (YYYYMMDD)
    :param db_path: 数据库路径
    """
    print(f"开始同步数据到数据库: {db_path}")
    
    # 创建数据库管理器和数据同步器
    db_manager = DuckDBManager(db_path)
    
    try:
        token = os.getenv('TUSHARE_TOKEN')
        data_sync = StockDataSync(token)
        
        # 执行同步
        result = data_sync.sync_stock_data(
            db_manager=db_manager,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"同步结果:")
        print(f"  状态: {'成功' if result['success'] else '失败'}")
        print(f"  消息: {result['message']}")
        print(f"  总股票数: {result.get('total_stocks', 0)}")
        print(f"  成功数: {result.get('success_stocks', 0)}")
        print(f"  失败数: {result.get('failed_stocks', 0)}")
        print(f"  总记录数: {result.get('total_records', 0)}")
        
    except Exception as e:
        print(f"数据同步失败: {e}")
        raise
    finally:
        db_manager.close()

def main():
    parser = argparse.ArgumentParser(description='同步股票数据')
    parser.add_argument('--code', help='股票代码 (如: 000001.SZ)')
    parser.add_argument('--start', help='开始日期 (YYYYMMDD)')
    parser.add_argument('--end', help='结束日期 (YYYYMMDD)')
    parser.add_argument('--db', default='data/stock_data.duckdb',
                       help='数据库文件路径')
    
    args = parser.parse_args()
    
    sync_data(args.code, args.start, args.end, args.db)

if __name__ == "__main__":
    main()
