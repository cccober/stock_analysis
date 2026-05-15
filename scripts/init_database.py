#!/usr/bin/env python3
"""
数据库初始化脚本
用于将CSV数据导入DuckDB数据库
"""

import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import DuckDBManager
from src.data_sync import StockDataSync

def init_database(csv_files: list, db_path: str = "data/stock_data.duckdb"):
    """
    初始化数据库并导入CSV数据
    
    :param csv_files: CSV文件路径列表
    :param db_path: 数据库文件路径
    """
    print(f"开始初始化数据库: {db_path}")
    
    # 确保数据目录存在
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
    
    # 创建数据库管理器
    db_manager = DuckDBManager(db_path)
    
    total_imported = 0
    
    try:
        for csv_file in csv_files:
            if not os.path.exists(csv_file):
                print(f"警告: 文件不存在 {csv_file}")
                continue
            
            print(f"正在导入: {csv_file}")
            imported = db_manager.import_csv_data(csv_file)
            total_imported += imported
            print(f"成功导入 {imported} 条记录")
        
        print(f"\n数据库初始化完成!")
        print(f"总计导入: {total_imported} 条记录")
        
        # 显示数据库统计信息
        stocks = db_manager.get_all_stocks()
        print(f"股票数量: {len(stocks)}")
        
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        raise
    finally:
        db_manager.close()

def main():
    parser = argparse.ArgumentParser(description='初始化股票数据库')
    parser.add_argument('--csv', nargs='+', default=['all_stock_history.csv', 'all_stock_history_part2.csv'],
                       help='CSV文件路径')
    parser.add_argument('--db', default='data/stock_data.duckdb',
                       help='数据库文件路径')
    
    args = parser.parse_args()
    
    init_database(args.csv, args.db)

if __name__ == "__main__":
    main()
