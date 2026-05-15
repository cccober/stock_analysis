import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database import DuckDBManager
from datetime import datetime, timedelta
import logging
import random
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 目标价格映射表（2026-04-30 的真实/预期价格）
# 用户可以在这里添加更多股票的目标价格
TARGET_PRICES = {
    '002460.SZ': 88.68,   # 赣锋锂业
}

def cleanup_and_update():
    """清理旧数据并重新生成到目标价格"""
    db_path = os.getenv('DB_PATH', 'data/stock_data.duckdb')
    db_manager = DuckDBManager(db_path)
    
    try:
        today = datetime.now().date()
        logger.info(f"目标日期: {today}")
        
        # 1. 删除2026-01-17之后的数据（保留原始CSV导入的数据）
        logger.info("清理旧数据...")
        
        # 先统计要删除的记录数
        count_result = db_manager.conn.execute("""
            SELECT COUNT(*) FROM stock_daily WHERE trade_date > '2026-01-16'
        """).fetchone()
        deleted = count_result[0]
        
        # 执行删除
        db_manager.conn.execute("""
            DELETE FROM stock_daily WHERE trade_date > '2026-01-16'
        """)
        
        logger.info(f"已删除 {deleted} 条旧记录")
        
        # 2. 获取所有股票及其最后一天数据
        stocks_df = db_manager.conn.execute("""
            SELECT DISTINCT ts_code, MAX(trade_date) as last_date
            FROM stock_daily
            GROUP BY ts_code
        """).fetchdf()
        
        total_stocks = len(stocks_df)
        logger.info(f"共有 {total_stocks} 只股票需要更新")
        
        # 3. 准备批量插入的数据
        all_new_records = []
        
        for idx, row in stocks_df.iterrows():
            ts_code = row['ts_code']
            last_date = row['last_date']
            
            if last_date is None:
                continue
            
            # 确保 last_date 是 datetime.date 类型
            if hasattr(last_date, 'date'):
                last_date = last_date.date()
                
            # 计算需要补充的日期（从最后一天的下一天到今天）
            current_date = last_date + timedelta(days=1)
            days_to_add = []
            while current_date <= today:
                # 跳过周末
                if current_date.weekday() < 5:
                    days_to_add.append(current_date)
                current_date += timedelta(days=1)
            
            if not days_to_add:
                continue
            
            # 获取最后一天的记录作为模板
            last_record = db_manager.conn.execute("""
                SELECT open, high, low, close, pre_close, change, pct_chg, vol, amount
                FROM stock_daily
                WHERE ts_code = ? AND trade_date = ?
            """, [ts_code, last_date]).fetchone()
            
            if not last_record:
                continue
            
            last_close = float(last_record[3])  # close price
            last_vol = float(last_record[7])
            last_amount = float(last_record[8])
            
            # 检查是否有目标价格
            target_price = None
            if ts_code in TARGET_PRICES:
                target_price = TARGET_PRICES[ts_code]
            
            # 为每个缺失的日期生成数据
            prev_close = last_close
            num_days = len(days_to_add)
            
            for day_idx, trade_date in enumerate(days_to_add):
                # 如果有目标价格，计算向目标收敛的偏移
                if target_price and num_days > 1:
                    # 计算当前应该达到的价格（线性插值）
                    progress = (day_idx + 1) / num_days
                    expected_close = last_close + (target_price - last_close) * progress
                    
                    # 生成围绕预期价格的波动
                    noise = random.uniform(-0.015, 0.015)  # ±1.5% 的噪声
                    new_close = round(expected_close * (1 + noise), 2)
                else:
                    # 没有目标价格，使用随机游走
                    change_pct = random.uniform(-0.03, 0.03)
                    change = round(prev_close * change_pct, 2)
                    new_close = round(prev_close + change, 2)
                
                # 生成 OHLC
                open_price = round(prev_close * random.uniform(0.995, 1.005), 2)
                high_price = round(max(open_price, new_close) * random.uniform(1.0, 1.02), 2)
                low_price = round(min(open_price, new_close) * random.uniform(0.98, 1.0), 2)
                
                # 确保 high >= max(open, close) 且 low <= min(open, close)
                high_price = max(high_price, open_price, new_close)
                low_price = min(low_price, open_price, new_close)
                
                # 计算涨跌幅
                change = round(new_close - prev_close, 2)
                change_pct = round((change / prev_close) * 100, 2) if prev_close != 0 else 0
                
                vol = round(last_vol * random.uniform(0.8, 1.2), 2)
                amount = round(last_amount * random.uniform(0.8, 1.2), 2)
                
                all_new_records.append({
                    'ts_code': ts_code,
                    'trade_date': trade_date,
                    'open': open_price,
                    'high': high_price,
                    'low': low_price,
                    'close': new_close,
                    'pre_close': prev_close,
                    'change': change,
                    'pct_chg': change_pct,
                    'vol': vol,
                    'amount': amount
                })
                
                prev_close = new_close
            
            if (idx + 1) % 1000 == 0 or idx == total_stocks - 1:
                logger.info(f"进度: {idx + 1}/{total_stocks} 只股票已处理")
        
        # 4. 批量插入数据
        if all_new_records:
            logger.info(f"准备批量插入 {len(all_new_records)} 条新记录...")
            
            new_df = pd.DataFrame(all_new_records)
            
            # 注册DataFrame为临时视图
            db_manager.conn.register('temp_update_df', new_df)
            
            # 批量插入
            db_manager.conn.execute("""
                INSERT OR REPLACE INTO stock_daily 
                (ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount)
                SELECT ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
                FROM temp_update_df
            """)
            
            db_manager.conn.unregister('temp_update_df')
            
            logger.info(f"成功插入 {len(all_new_records)} 条新记录")
        
        # 5. 验证更新结果
        result = db_manager.conn.execute("""
            SELECT COUNT(DISTINCT ts_code) as stock_count,
                   MAX(trade_date) as max_date,
                   COUNT(*) as total_records
            FROM stock_daily
        """).fetchone()
        
        logger.info(f"数据库统计: {result[0]} 只股票, 最新日期: {result[1]}, 总记录: {result[2]}")
        
        # 6. 验证目标价格
        logger.info("目标价格验证:")
        for ts_code, target in TARGET_PRICES.items():
            actual = db_manager.conn.execute("""
                SELECT close FROM stock_daily 
                WHERE ts_code = ? AND trade_date = ?
            """, [ts_code, today]).fetchone()
            if actual:
                actual_price = actual[0]
                diff = abs(actual_price - target)
                diff_pct = (diff / target) * 100
                logger.info(f"  {ts_code}: 目标={target}, 实际={actual_price}, 偏差={diff_pct:.2f}%")
        
        # 7. 显示示例数据
        sample = db_manager.conn.execute("""
            SELECT s.ts_code, b.name, s.trade_date, s.close, s.pct_chg
            FROM stock_daily s
            LEFT JOIN stock_basic b ON s.ts_code = b.ts_code
            WHERE s.trade_date = ?
            LIMIT 10
        """, [today]).fetchdf()
        
        logger.info("示例数据（今天）:")
        print(sample.to_string(index=False))
        
    except Exception as e:
        logger.error(f"更新失败: {e}")
        raise
    finally:
        db_manager.close()

if __name__ == "__main__":
    cleanup_and_update()
