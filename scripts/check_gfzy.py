import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.database import DuckDBManager
from datetime import datetime

db = DuckDBManager('data/stock_data.duckdb')

# 查询赣锋锂业
result = db.conn.execute("""
    SELECT ts_code, trade_date, open, high, low, close, pct_chg 
    FROM stock_daily 
    WHERE ts_code = '002460.SZ' 
    ORDER BY trade_date DESC 
    LIMIT 5
""").fetchall()
print('赣锋锂业 (002460.SZ) 最近5条记录:')
for r in result:
    print(f'  {r[1]}: 开{r[2]:.2f} 收{r[5]:.2f} 涨跌{r[6]:.2f}%')

# 查询最新日期
max_date = db.conn.execute("SELECT MAX(trade_date) FROM stock_daily WHERE ts_code = '002460.SZ'").fetchone()[0]
print(f'\n赣锋锂业最新日期: {max_date}')
print(f'今天日期: {datetime.now().date()}')

# 查询数据库整体最新日期
overall_max = db.conn.execute("SELECT MAX(trade_date) FROM stock_daily").fetchone()[0]
print(f'数据库整体最新日期: {overall_max}')

db.close()
