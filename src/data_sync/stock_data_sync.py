import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging
import time
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 尝试导入 AKShare，如果失败则标记为不可用
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    logger.warning("AKShare 未安装，将使用 Tushare 作为唯一新闻源")

class StockDataSync:
    NEWS_SOURCES = ['eastmoney', 'sina', '10jqka', 'wallstreetcn', 'yuncaijing']
    """股票数据同步器，负责从Tushare获取数据并同步到数据库"""
    
    def __init__(self, token: Optional[str] = None):
        """
        初始化数据同步器
        
        :param token: Tushare API token，如果为None则从环境变量获取
        """
        if token is None:
            token = os.getenv('TUSHARE_TOKEN', '1ff975ea535e82679de240fc493698506452ace8f002152c965aed01')
        
        self.token = token
        self.pro = None
        self._init_tushare()
        # 新闻缓存: {(ts_code, keyword, src): (timestamp, df)}
        self._news_cache = {}
        self._cache_ttl = 300  # 缓存5分钟
        # AKShare 缓存
        self._akshare_cache = {}
        self._akshare_cache_ttl = 300  # 缓存5分钟
    
    def _get_cache_key(self, ts_code, keyword, src):
        """生成缓存键"""
        return (ts_code or '', keyword or '', src or 'all')
    
    def _get_cached_news(self, ts_code, keyword, src):
        """获取缓存的新闻"""
        key = self._get_cache_key(ts_code, keyword, src)
        if key in self._news_cache:
            timestamp, df = self._news_cache[key]
            if time.time() - timestamp < self._cache_ttl:
                logger.info(f"使用缓存的新闻数据: {key}")
                return df
            else:
                del self._news_cache[key]
        return None
    
    def _set_cached_news(self, ts_code, keyword, src, df):
        """设置缓存的新闻"""
        key = self._get_cache_key(ts_code, keyword, src)
        self._news_cache[key] = (time.time(), df)
        logger.info(f"缓存新闻数据: {key}")
    
    def _get_akshare_cache_key(self, symbol):
        """生成 AKShare 缓存键"""
        return symbol
    
    def _get_cached_akshare_news(self, symbol):
        """获取缓存的 AKShare 新闻"""
        key = self._get_akshare_cache_key(symbol)
        if key in self._akshare_cache:
            timestamp, df = self._akshare_cache[key]
            if time.time() - timestamp < self._akshare_cache_ttl:
                logger.info(f"使用缓存的 AKShare 新闻数据: {key}")
                return df
            else:
                del self._akshare_cache[key]
        return None
    
    def _set_cached_akshare_news(self, symbol, df):
        """设置缓存的 AKShare 新闻"""
        key = self._get_akshare_cache_key(symbol)
        self._akshare_cache[key] = (time.time(), df)
        logger.info(f"缓存 AKShare 新闻数据: {key}")
    
    def get_akshare_news(self, ts_code: str = None, limit: int = 80) -> pd.DataFrame:
        """
        使用 AKShare 获取东方财富网的股票新闻
        
        :param ts_code: 股票代码（如 000001.SZ）
        :param limit: 返回条数限制
        :return: 新闻数据DataFrame
        """
        if not AKSHARE_AVAILABLE:
            logger.warning("AKShare 未安装，无法获取新闻")
            return pd.DataFrame()
        
        # 提取纯数字代码
        symbol = ts_code.split('.')[0] if ts_code else None
        if not symbol:
            logger.warning("未提供股票代码，无法获取 AKShare 新闻")
            return pd.DataFrame()
        
        # 检查缓存
        cached = self._get_cached_akshare_news(symbol)
        if cached is not None:
            return cached.head(limit) if len(cached) > limit else cached
        
        try:
            import akshare as ak
            df = ak.stock_news_em(symbol=symbol)
            
            if df is not None and not df.empty:
                # 重命名列以匹配 Tushare 格式
                column_mapping = {
                    '关键词': 'keyword',
                    '新闻标题': 'title',
                    '新闻内容': 'content',
                    '发布时间': 'datetime',
                    '文章来源': 'src',
                    '新闻链接': 'url'
                }
                
                # 只保留存在的列
                existing_cols = {k: v for k, v in column_mapping.items() if k in df.columns}
                df = df.rename(columns=existing_cols)
                
                # 添加来源标识
                if 'src' not in df.columns:
                    df['src'] = 'eastmoney'
                
                # 缓存数据
                self._set_cached_akshare_news(symbol, df)
                
                logger.info(f"AKShare 成功获取 {len(df)} 条新闻")
                return df.head(limit) if len(df) > limit else df
            else:
                logger.info("AKShare 未找到相关新闻")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"AKShare 获取新闻失败: {e}")
            return pd.DataFrame()
    
    def _init_tushare(self):
        """初始化Tushare API"""
        try:
            # 设置token文件路径到当前目录，避免权限问题
            token_file = os.path.join(os.path.dirname(__file__), '..', '..', 'data', '.tushare_token')
            os.makedirs(os.path.dirname(token_file), exist_ok=True)
            
            # 临时修改tushare的token文件路径
            import tushare.util.upass as upass
            upass.set_token = lambda token: self._set_token_custom(token, token_file)
            
            # 直接设置token而不写入文件
            self.pro = ts.pro_api(self.token)
            logger.info("Tushare API 初始化成功")
        except Exception as e:
            logger.error(f"Tushare API 初始化失败: {e}")
            # 如果初始化失败，创建一个模拟的pro_api
            self.pro = None
            logger.warning("使用离线模式，无法获取实时数据")
    
    def _set_token_custom(self, token, filepath):
        """自定义token设置，避免写入系统目录"""
        try:
            with open(filepath, 'w') as f:
                f.write(token)
        except Exception as e:
            logger.warning(f"无法写入token文件: {e}")
    
    @staticmethod
    def merge_news_frames(frames: List[pd.DataFrame], limit: int = 50) -> pd.DataFrame:
        valid_frames = [frame for frame in frames if frame is not None and not frame.empty]
        if not valid_frames:
            return pd.DataFrame()

        merged = pd.concat(valid_frames, ignore_index=True, sort=False)
        for column in ['title', 'url', 'datetime', 'time', 'pub_time', 'src']:
            if column not in merged.columns:
                merged[column] = None

        dedupe_key = merged['url'].fillna('')
        fallback_key = merged['title'].fillna('') + '|' + merged['datetime'].fillna(merged['time'].fillna(''))
        merged['_dedupe_key'] = dedupe_key.where(dedupe_key != '', fallback_key)
        merged = merged.drop_duplicates(subset=['_dedupe_key'], keep='first')

        time_text = merged['datetime'].fillna(merged['time'].fillna(merged['pub_time'].fillna('')))
        merged['_sort_time'] = pd.to_datetime(time_text, errors='coerce')
        merged = merged.sort_values(
            by=['_sort_time', 'datetime', 'time', 'pub_time'],
            ascending=[False, False, False, False],
            na_position='last'
        )
        merged = merged.drop(columns=['_dedupe_key', '_sort_time'])
        return merged.head(limit).reset_index(drop=True)

    def get_all_stock_codes(self) -> List[str]:
        """
        获取所有A股股票代码
        
        :return: 股票代码列表
        """
        if self.pro is None:
            logger.warning("Tushare API 未初始化，无法获取股票代码")
            return []
        try:
            data = self.pro.stock_basic(exchange='', list_status='L', fields='ts_code')
            return data['ts_code'].tolist()
        except Exception as e:
            logger.error(f"获取股票代码列表失败: {e}")
            return []
    
    def get_stock_basic_info(self) -> pd.DataFrame:
        """
        获取所有股票的基础信息
        
        :return: 股票基础信息DataFrame
        """
        if self.pro is None:
            logger.warning("Tushare API 未初始化，无法获取股票信息")
            return pd.DataFrame()
        try:
            df = self.pro.stock_basic(
                exchange='', 
                list_status='L', 
                fields='ts_code,symbol,name,area,industry,market,list_date,exchange'
            )
            return df
        except Exception as e:
            logger.error(f"获取股票基础信息失败: {e}")
            return pd.DataFrame()
    
    def download_stock_data(self, ts_code: str, start_date: str, end_date: str, 
                           max_retries: int = 3) -> pd.DataFrame:
        """
        下载指定股票的历史数据
        
        :param ts_code: 股票代码，例如 '000001.SZ'
        :param start_date: 开始日期，格式为 'YYYYMMDD'
        :param end_date: 结束日期，格式为 'YYYYMMDD'
        :param max_retries: 最大重试次数
        :return: 包含历史数据的DataFrame
        """
        # 优先使用 Tushare
        if self.pro is not None:
            for attempt in range(max_retries):
                try:
                    logger.info(f"使用 Tushare 下载 {ts_code} 数据 ({start_date} 至 {end_date})，第 {attempt + 1} 次尝试...")
                    
                    df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                    
                    if df is not None and not df.empty:
                        logger.info(f"Tushare 成功下载 {ts_code} 的 {len(df)} 条记录")
                        return df
                    else:
                        logger.warning(f"{ts_code} 在指定时间段内没有数据")
                        return pd.DataFrame()
                        
                except Exception as e:
                    logger.error(f"Tushare 下载 {ts_code} 数据时出错 (尝试 {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # 指数退避
                        logger.info(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    else:
                        logger.warning(f"Tushare 下载失败，尝试使用 AKShare")
        
        # Tushare 失败或未初始化，尝试使用 AKShare
        return self._download_stock_data_akshare(ts_code, start_date, end_date)
    
    def _download_stock_data_akshare(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        使用 AKShare 下载股票历史数据（作为 Tushare 的备选）
        
        :param ts_code: 股票代码，例如 '000001.SZ'
        :param start_date: 开始日期，格式为 'YYYYMMDD'
        :param end_date: 结束日期，格式为 'YYYYMMDD'
        :return: 包含历史数据的DataFrame
        """
        if not AKSHARE_AVAILABLE:
            logger.warning("AKShare 未安装，无法作为备选数据源")
            return pd.DataFrame()
            
        try:
            import akshare as ak
            
            # 转换日期格式
            start_date_str = start_date[:4] + '-' + start_date[4:6] + '-' + start_date[6:]
            end_date_str = end_date[:4] + '-' + end_date[4:6] + '-' + end_date[6:]
            
            # 提取交易所代码
            exchange = 'sh' if ts_code.endswith('.SH') else 'sz'
            symbol = ts_code.split('.')[0]
            
            logger.info(f"使用 AKShare 下载 {ts_code} 数据 ({start_date} 至 {end_date})...")
            
            # 使用 AKShare 获取数据
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                   start_date=start_date_str, end_date=end_date_str,
                                   adjust="")
            
            if df is not None and not df.empty:
                # 转换列名以匹配 Tushare 格式
                df = self._convert_akshare_to_tushare_format(df, ts_code)
                logger.info(f"AKShare 成功下载 {ts_code} 的 {len(df)} 条记录")
                return df
            else:
                logger.warning(f"AKShare 未获取到 {ts_code} 的数据")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"AKShare 下载 {ts_code} 数据时出错: {e}")
            return pd.DataFrame()
    
    def _convert_akshare_to_tushare_format(self, df: pd.DataFrame, ts_code: str) -> pd.DataFrame:
        """
        将 AKShare 数据格式转换为 Tushare 格式
        
        :param df: AKShare 返回的DataFrame
        :param ts_code: 股票代码
        :return: 转换后的DataFrame
        """
        if df.empty:
            return df
            
        # AKShare 列名到 Tushare 列名的映射
        column_mapping = {
            '日期': 'trade_date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '前收盘': 'pre_close',
            '涨跌额': 'change',
            '涨跌幅': 'pct_chg',
            '成交量': 'vol',
            '成交额': 'amount'
        }
        
        # 只保留需要的列并重命名
        df = df.rename(columns=column_mapping)
        
        # 添加 ts_code 列
        df['ts_code'] = ts_code
        
        # 转换日期格式
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y%m%d')
        
        # 确保列顺序正确
        required_columns = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 
                           'pre_close', 'change', 'pct_chg', 'vol', 'amount']
        df = df[required_columns]
        
        return df
    
    def download_multiple_stocks(self, stock_codes: List[str], start_date: str, 
                                end_date: str, delay: float = 0.5) -> pd.DataFrame:
        """
        批量下载多只股票的历史数据
        
        :param stock_codes: 股票代码列表
        :param start_date: 开始日期 (YYYYMMDD)
        :param end_date: 结束日期 (YYYYMMDD)
        :param delay: 每次请求之间的延迟（秒）
        :return: 合并后的历史数据DataFrame
        """
        all_data = []
        total = len(stock_codes)
        
        for i, code in enumerate(stock_codes, 1):
            try:
                df = self.download_stock_data(code, start_date, end_date)
                if not df.empty:
                    all_data.append(df)
                
                # 显示进度
                if i % 10 == 0 or i == total:
                    logger.info(f"下载进度: {i}/{total} ({i/total*100:.1f}%)")
                
                # 添加延迟以避免API限制
                if delay > 0 and i < total:
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"处理 {code} 时出错: {e}")
                continue
        
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            logger.info(f"批量下载完成，共 {len(result)} 条记录")
            return result
        else:
            logger.warning("没有下载到任何数据")
            return pd.DataFrame()
    
    def get_latest_trade_date(self) -> str:
        """
        获取最新的交易日
        
        :return: 最新交易日 (YYYYMMDD)
        """
        if self.pro is None:
            return datetime.now().strftime('%Y%m%d')
        try:
            df = self.pro.trade_cal(exchange='SSE', is_open='1', 
                                   start_date=(datetime.now() - timedelta(days=30)).strftime('%Y%m%d'),
                                   end_date=datetime.now().strftime('%Y%m%d'))
            if not df.empty:
                latest_date = df['cal_date'].max()
                return str(latest_date)
            else:
                return datetime.now().strftime('%Y%m%d')
        except Exception as e:
            logger.error(f"获取最新交易日失败: {e}")
            return datetime.now().strftime('%Y%m%d')
    
    def is_trading_day(self, date: Optional[str] = None) -> bool:
        """
        判断指定日期是否为交易日
        
        :param date: 日期 (YYYYMMDD)，默认为今天
        :return: 是否为交易日
        """
        if self.pro is None:
            return True  # 离线模式下默认允许更新
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        try:
            df = self.pro.trade_cal(exchange='SSE', start_date=date, end_date=date)
            if not df.empty:
                return df.iloc[0]['is_open'] == 1
            return False
        except Exception as e:
            logger.error(f"判断交易日失败: {e}")
            return False
    
    def sync_stock_data(self, db_manager, ts_code: Optional[str] = None,
                       start_date: Optional[str] = None, 
                       end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        同步股票数据到数据库
        
        :param db_manager: 数据库管理器实例
        :param ts_code: 股票代码，如果为None则同步所有股票
        :param start_date: 开始日期 (YYYYMMDD)
        :param end_date: 结束日期 (YYYYMMDD)
        :return: 同步结果统计
        """
        result = {
            'success': False,
            'total_stocks': 0,
            'success_stocks': 0,
            'failed_stocks': 0,
            'total_records': 0,
            'message': ''
        }
        
        try:
            # 确定要同步的股票列表
            if ts_code:
                stock_codes = [ts_code]
            else:
                stock_codes = self.get_all_stock_codes()
            
            result['total_stocks'] = len(stock_codes)
            
            # 确定日期范围
            if end_date is None:
                end_date = self.get_latest_trade_date()
            
            if start_date is None:
                # 如果未指定开始日期，从数据库中最新日期开始
                # 获取数据库中所有股票的最大日期作为起始点
                latest_db_date = db_manager.get_latest_date()
                if latest_db_date:
                    # 从数据库最新日期的下一天开始
                    last_date = datetime.strptime(str(latest_db_date), '%Y-%m-%d')
                    start_date = (last_date + timedelta(days=1)).strftime('%Y%m%d')
                else:
                    start_date = '20100101'  # 默认开始日期
            
            logger.info(f"开始同步数据: {start_date} 至 {end_date}，共 {len(stock_codes)} 只股票")
            
            # 批量下载数据
            df = self.download_multiple_stocks(stock_codes, start_date, end_date)
            
            if not df.empty:
                # 插入到数据库
                inserted_count = db_manager.insert_stock_data(df)
                result['total_records'] = inserted_count
                result['success_stocks'] = df['ts_code'].nunique()
                result['failed_stocks'] = len(stock_codes) - result['success_stocks']
                result['success'] = True
                result['message'] = f"成功同步 {result['success_stocks']} 只股票，共 {inserted_count} 条记录"
                
                # 记录更新日志
                for code in df['ts_code'].unique():
                    code_data = df[df['ts_code'] == code]
                    db_manager.log_update(
                        ts_code=code,
                        start_date=start_date,
                        end_date=end_date,
                        record_count=len(code_data),
                        status='success',
                        message='数据同步成功'
                    )
            else:
                result['message'] = '没有新数据需要同步'
                
        except Exception as e:
            result['message'] = f"同步失败: {str(e)}"
            logger.error(result['message'])
        
        return result
    
    def sync_daily_update(self, db_manager) -> Dict[str, Any]:
        """
        执行每日数据更新
        
        :param db_manager: 数据库管理器实例
        :return: 更新结果统计
        """
        logger.info("开始执行每日数据更新...")
        
        # 检查今天是否为交易日
        if not self.is_trading_day():
            logger.info("今天不是交易日，跳过更新")
            return {
                'success': True,
                'message': '今天不是交易日，无需更新'
            }
        
        # 获取昨天和今天的日期
        today = datetime.now().strftime('%Y%m%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        
        # 执行同步
        result = self.sync_stock_data(
            db_manager=db_manager,
            start_date=yesterday,
            end_date=today
        )
        
        logger.info(f"每日更新完成: {result['message']}")
        return result
    
    def get_stock_news(self, ts_code: str = None, keyword: str = None, 
                       start_date: str = None, end_date: str = None,
                       src: str = 'eastmoney', limit: int = 20) -> pd.DataFrame:
        """
        获取股票相关新闻资讯
        
        :param ts_code: 股票代码（可选，用于过滤特定股票新闻）
        :param keyword: 关键词（可选，用于搜索特定主题）
        :param start_date: 开始日期 (YYYY-MM-DD)
        :param end_date: 结束日期 (YYYY-MM-DD)
        :param src: 新闻来源 (eastmoney/sina/wallstreetcn/10jqka/yuncaijing)
        :param limit: 返回条数限制
        :return: 新闻数据DataFrame
        """
        # 检查缓存
        cached = self._get_cached_news(ts_code, keyword, src)
        if cached is not None:
            return cached
        
        # 如果 Tushare API 可用，优先使用 Tushare
        if self.pro is not None:
            try:
                # 构建参数
                if src == 'all':
                    frames = []
                    per_source_limit = max(limit, 20)
                    for source in self.NEWS_SOURCES:
                        frame = self.get_stock_news(
                            ts_code=ts_code,
                            keyword=keyword,
                            start_date=start_date,
                            end_date=end_date,
                            src=source,
                            limit=per_source_limit
                        )
                        if frame is not None and not frame.empty:
                            frame = frame.copy()
                            if 'src' not in frame.columns:
                                frame['src'] = source
                            frame['src'] = frame['src'].fillna(source)
                            frames.append(frame)
                        time.sleep(0.2)
                    result = self.merge_news_frames(frames, limit=limit)
                    self._set_cached_news(ts_code, keyword, src, result)
                    return result

                params = {
                    'src': src,
                    'limit': limit
                }
                
                if start_date:
                    params['start_date'] = start_date
                if end_date:
                    params['end_date'] = end_date
                
                # 如果有股票代码，转换为股票名称作为关键词
                if ts_code and not keyword:
                    try:
                        stock_info = self.pro.stock_basic(ts_code=ts_code, fields='name')
                        if not stock_info.empty:
                            keyword = stock_info.iloc[0]['name']
                    except Exception as e:
                        logger.warning(f"获取股票名称失败: {e}")
                        keyword = ts_code
                
                if keyword:
                    params['keyword'] = keyword
                
                df = self.pro.news(**params)
                
                if df is not None and not df.empty:
                    if 'src' not in df.columns:
                        df['src'] = src
                    else:
                        df['src'] = df['src'].fillna(src)
                    logger.info(f"Tushare 成功获取 {len(df)} 条新闻")
                    self._set_cached_news(ts_code, keyword, src, df)
                    return df
                else:
                    logger.info("Tushare 未找到相关新闻，尝试使用 AKShare")
                    
            except Exception as e:
                logger.warning(f"Tushare 获取新闻失败: {e}，尝试使用 AKShare")
        else:
            logger.warning("Tushare API 未初始化，尝试使用 AKShare")
        
        # 如果 Tushare 失败或未初始化，尝试使用 AKShare
        if AKSHARE_AVAILABLE and ts_code:
            try:
                df = self.get_akshare_news(ts_code=ts_code, limit=limit)
                if df is not None and not df.empty:
                    # 转换 AKShare 数据格式以匹配 Tushare
                    if 'title' in df.columns and 'content' not in df.columns:
                        df['content'] = df['title']
                    if 'datetime' in df.columns and 'time' not in df.columns:
                        df['time'] = df['datetime']
                    if 'url' in df.columns and 'link' not in df.columns:
                        df['link'] = df['url']
                    
                    self._set_cached_news(ts_code, keyword, src, df)
                    return df
            except Exception as e:
                logger.error(f"AKShare 获取新闻失败: {e}")
        
        # 如果所有方法都失败，返回空 DataFrame
        logger.warning("所有新闻源都不可用，返回空数据")
        self._set_cached_news(ts_code, keyword, src, pd.DataFrame())
        return pd.DataFrame()
    
    def get_major_news(self, limit: int = 50) -> pd.DataFrame:
        """
        获取重大新闻/公告（信息地雷）
        
        :param limit: 返回条数限制
        :return: 重大新闻DataFrame
        """
        if self.pro is None:
            logger.warning("Tushare API 未初始化，无法获取重大新闻")
            return pd.DataFrame()
        
        try:
            # 获取最近的重要公告
            today = datetime.now()
            start = (today - timedelta(days=7)).strftime('%Y%m%d')
            end = today.strftime('%Y%m%d')
            
            df = self.pro.major_news(start_date=start, end_date=end, limit=limit)
            
            if df is not None and not df.empty:
                logger.info(f"成功获取 {len(df)} 条重大新闻")
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"获取重大新闻失败: {e}")
            return pd.DataFrame()
