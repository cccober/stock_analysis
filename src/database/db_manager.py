import duckdb
import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DuckDBManager:
    """DuckDB数据库管理器，负责股票数据的存储、查询和更新"""
    
    def __init__(self, db_path: str = "data/stock_data.duckdb"):
        self.db_path = db_path
        self.conn = None
        self._ensure_db_directory()
        self._connect()
        self._init_tables()
    
    def _ensure_db_directory(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            logger.info(f"创建数据库目录: {db_dir}")
    
    def _connect(self):
        """建立数据库连接"""
        try:
            self.conn = duckdb.connect(self.db_path)
            logger.info(f"成功连接到数据库: {self.db_path}")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise
    
    def _init_tables(self):
        """初始化数据库表结构"""
        try:
            # 创建股票日线数据表
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_daily (
                    ts_code VARCHAR NOT NULL,
                    trade_date DATE NOT NULL,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    pre_close DOUBLE,
                    change DOUBLE,
                    pct_chg DOUBLE,
                    vol DOUBLE,
                    amount DOUBLE,
                    PRIMARY KEY (ts_code, trade_date)
                )
            """)
            
            # 创建股票基础信息表
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_basic (
                    ts_code VARCHAR PRIMARY KEY,
                    symbol VARCHAR,
                    name VARCHAR,
                    area VARCHAR,
                    industry VARCHAR,
                    market VARCHAR,
                    list_date DATE,
                    exchange VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建数据更新日志表
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS update_log (
                    id INTEGER PRIMARY KEY,
                    ts_code VARCHAR,
                    start_date DATE,
                    end_date DATE,
                    record_count INTEGER,
                    status VARCHAR,
                    message VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引以提高查询性能
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_stock_daily_ts_code 
                ON stock_daily(ts_code)
            """)
            
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_stock_daily_trade_date 
                ON stock_daily(trade_date)
            """)
            
            logger.info("数据库表初始化完成")
        except Exception as e:
            logger.error(f"数据库表初始化失败: {e}")
            raise
    
    def import_csv_data(self, csv_path: str, table_name: str = "stock_daily") -> int:
        """
        从CSV文件导入数据到数据库
        
        :param csv_path: CSV文件路径
        :param table_name: 目标表名
        :return: 导入的记录数
        """
        try:
            logger.info(f"开始从 {csv_path} 导入数据...")
            
            # 读取CSV文件
            df = pd.read_csv(csv_path)
            
            # 数据清洗和转换
            df = self._clean_data(df)
            
            # 检查重复记录
            existing_count = self.conn.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
            
            # 使用INSERT OR IGNORE方式插入数据（避免重复）
            # 先注册DataFrame为临时视图
            self.conn.register('temp_import_df', df)
            
            # 插入新数据，忽略重复的主键
            self.conn.execute(f"""
                INSERT OR IGNORE INTO {table_name} (ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount)
                SELECT ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
                FROM temp_import_df
            """)
            
            # 取消注册临时视图
            self.conn.unregister('temp_import_df')
            
            new_count = self.conn.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
            
            imported_count = new_count - existing_count
            logger.info(f"成功导入 {imported_count} 条记录到 {table_name}")
            
            return imported_count
            
        except Exception as e:
            logger.error(f"导入CSV数据失败: {e}")
            raise
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗和转换数据格式
        
        :param df: 原始DataFrame
        :return: 清洗后的DataFrame
        """
        # 转换日期格式
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.date
        
        # 确保数值列为正确的类型
        numeric_columns = ['open', 'high', 'low', 'close', 'pre_close', 
                          'change', 'pct_chg', 'vol', 'amount']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 删除完全重复的记录
        df = df.drop_duplicates(subset=['ts_code', 'trade_date'], keep='first')
        
        return df
    
    def get_stock_data(self, ts_code: str, start_date: Optional[str] = None, 
                      end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取指定股票的历史数据
        
        :param ts_code: 股票代码
        :param start_date: 开始日期 (YYYY-MM-DD)
        :param end_date: 结束日期 (YYYY-MM-DD)
        :return: 股票历史数据DataFrame
        """
        try:
            query = """
                SELECT * FROM stock_daily 
                WHERE ts_code = ?
            """
            params = [ts_code]
            
            if start_date:
                query += " AND trade_date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND trade_date <= ?"
                params.append(end_date)
            
            query += " ORDER BY trade_date ASC"
            
            df = self.conn.execute(query, params).fetchdf()
            return df
            
        except Exception as e:
            logger.error(f"获取股票数据失败: {e}")
            raise
    
    def get_all_stocks(self) -> pd.DataFrame:
        """
        获取所有股票列表，包含中文名称
        
        :return: 股票列表DataFrame
        """
        try:
            df = self.conn.execute("""
                SELECT DISTINCT 
                    s.ts_code, 
                    COALESCE(b.name, s.ts_code) as name,
                    COALESCE(b.symbol, '') as symbol,
                    COALESCE(b.industry, '') as industry,
                    MIN(s.trade_date) as start_date,
                    MAX(s.trade_date) as end_date,
                    COUNT(*) as record_count
                FROM stock_daily s
                LEFT JOIN stock_basic b ON s.ts_code = b.ts_code
                GROUP BY s.ts_code, b.name, b.symbol, b.industry
                ORDER BY s.ts_code
            """).fetchdf()
            return df
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            raise
    
    def get_stock_name(self, ts_code: str) -> str:
        """
        获取股票中文名称
        
        :param ts_code: 股票代码
        :return: 股票中文名称
        """
        try:
            result = self.conn.execute("""
                SELECT COALESCE(name, ?) as name 
                FROM stock_basic 
                WHERE ts_code = ?
            """, [ts_code, ts_code]).fetchone()
            return result[0] if result else ts_code
        except Exception as e:
            logger.error(f"获取股票名称失败: {e}")
            return ts_code
    
    def import_stock_basic(self, df: pd.DataFrame) -> int:
        """
        导入股票基础信息到数据库
        
        :param df: 股票基础信息DataFrame
        :return: 导入的记录数
        """
        try:
            if df.empty:
                logger.warning("股票基础信息为空")
                return 0
            
            # 确保列名正确
            required_cols = ['ts_code', 'symbol', 'name', 'area', 'industry', 'market', 'list_date', 'exchange']
            for col in required_cols:
                if col not in df.columns:
                    df[col] = None
            
            # 转换日期格式
            if 'list_date' in df.columns and df['list_date'].notna().any():
                df['list_date'] = pd.to_datetime(df['list_date'], format='%Y%m%d', errors='coerce').dt.date
            
            # 注册DataFrame为临时视图
            self.conn.register('temp_basic_df', df[required_cols])
            
            # 使用INSERT OR REPLACE更新数据
            self.conn.execute("""
                INSERT OR REPLACE INTO stock_basic (ts_code, symbol, name, area, industry, market, list_date, exchange)
                SELECT ts_code, symbol, name, area, industry, market, list_date, exchange
                FROM temp_basic_df
            """)
            
            self.conn.unregister('temp_basic_df')
            
            logger.info(f"成功导入 {len(df)} 条股票基础信息")
            return len(df)
            
        except Exception as e:
            logger.error(f"导入股票基础信息失败: {e}")
            raise
    
    def get_date_range(self, ts_code: str) -> Dict[str, Any]:
        """
        获取指定股票的数据时间范围
        
        :param ts_code: 股票代码
        :return: 包含开始日期和结束日期的字典
        """
        try:
            result = self.conn.execute("""
                SELECT 
                    MIN(trade_date) as start_date,
                    MAX(trade_date) as end_date,
                    COUNT(*) as total_days
                FROM stock_daily 
                WHERE ts_code = ?
            """, [ts_code]).fetchone()
            
            return {
                'ts_code': ts_code,
                'start_date': result[0],
                'end_date': result[1],
                'total_days': result[2]
            }
        except Exception as e:
            logger.error(f"获取日期范围失败: {e}")
            raise
    
    def get_latest_date(self) -> Optional[str]:
        """
        获取数据库中所有股票数据的最新日期
        
        :return: 最新日期 (YYYY-MM-DD)，如果没有数据则返回 None
        """
        try:
            result = self.conn.execute("""
                SELECT MAX(trade_date) as latest_date
                FROM stock_daily
            """).fetchone()
            
            return result[0] if result and result[0] else None
        except Exception as e:
            logger.error(f"获取最新日期失败: {e}")
            return None
    
    def get_missing_dates(self, ts_code: str, start_date: str, end_date: str) -> List:
        """
        获取指定时间段内缺失的交易日期
        
        :param ts_code: 股票代码
        :param start_date: 开始日期 (YYYY-MM-DD)
        :param end_date: 结束日期 (YYYY-MM-DD)
        :return: 缺失的日期列表
        """
        try:
            result = self.conn.execute("""
                WITH date_range AS (
                    SELECT generate_series(
                        ?::DATE, 
                        ?::DATE, 
                        INTERVAL '1 day'
                    )::DATE AS trade_date
                ),
                trading_days AS (
                    SELECT trade_date FROM date_range
                    WHERE EXTRACT(DOW FROM trade_date) NOT IN (0, 6)
                ),
                existing_data AS (
                    SELECT trade_date 
                    FROM stock_daily 
                    WHERE ts_code = ?
                )
                SELECT t.trade_date
                FROM trading_days t
                LEFT JOIN existing_data e ON t.trade_date = e.trade_date
                WHERE e.trade_date IS NULL
                ORDER BY t.trade_date
            """, [start_date, end_date, ts_code]).fetchdf()
            
            return result['trade_date'].tolist()
        except Exception as e:
            logger.error(f"获取缺失日期失败: {e}")
            raise
    
    def insert_stock_data(self, df: pd.DataFrame, table_name: str = "stock_daily") -> int:
        """
        插入股票数据到数据库
        
        :param df: 股票数据DataFrame
        :param table_name: 目标表名
        :return: 插入的记录数
        """
        try:
            if df.empty:
                logger.warning("插入的数据为空")
                return 0
            
            # 数据清洗
            df = self._clean_data(df)
            
            # 注册DataFrame为临时视图
            self.conn.register('temp_df', df)
            
            # 使用INSERT OR IGNORE避免重复，明确指定列名
            result = self.conn.execute(f"""
                INSERT OR IGNORE INTO {table_name} (ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount)
                SELECT ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
                FROM temp_df
            """)
            
            # 取消注册临时视图
            self.conn.unregister('temp_df')
            
            inserted_count = result.fetchone()[0] if result else 0
            logger.info(f"成功插入 {inserted_count} 条记录到 {table_name}")
            
            return inserted_count
            
        except Exception as e:
            logger.error(f"插入股票数据失败: {e}")
            raise
    
    def log_update(self, ts_code: str, start_date: str, end_date: str, 
                   record_count: int, status: str, message: str = ""):
        """
        记录数据更新日志
        
        :param ts_code: 股票代码
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param record_count: 记录数
        :param status: 更新状态
        :param message: 附加消息
        """
        try:
            self.conn.execute("""
                INSERT INTO update_log (ts_code, start_date, end_date, record_count, status, message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [ts_code, start_date, end_date, record_count, status, message])
            logger.info(f"更新日志已记录: {ts_code} {status}")
        except Exception as e:
            logger.error(f"记录更新日志失败: {e}")
    
    def get_update_logs(self, ts_code: Optional[str] = None, 
                       limit: int = 100) -> pd.DataFrame:
        """
        获取更新日志
        
        :param ts_code: 股票代码（可选）
        :param limit: 返回记录数限制
        :return: 更新日志DataFrame
        """
        try:
            if ts_code:
                df = self.conn.execute("""
                    SELECT * FROM update_log 
                    WHERE ts_code = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, [ts_code, limit]).fetchdf()
            else:
                df = self.conn.execute("""
                    SELECT * FROM update_log 
                    ORDER BY created_at DESC
                    LIMIT ?
                """, [limit]).fetchdf()
            
            return df
        except Exception as e:
            logger.error(f"获取更新日志失败: {e}")
            raise
    
    def execute_query(self, query: str, params: Optional[list] = None) -> pd.DataFrame:
        """
        执行自定义SQL查询
        
        :param query: SQL查询语句
        :param params: 查询参数
        :return: 查询结果DataFrame
        """
        try:
            if params:
                return self.conn.execute(query, params).fetchdf()
            else:
                return self.conn.execute(query).fetchdf()
        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            raise
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("数据库连接已关闭")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
