import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """技术指标计算类"""
    
    @staticmethod
    def calculate_ma(data: pd.DataFrame, periods: list = [5, 10, 20, 60]) -> pd.DataFrame:
        """
        计算移动平均线
        
        :param data: 股票数据DataFrame
        :param periods: 移动平均周期列表
        :return: 包含移动平均线的DataFrame
        """
        df = data.copy()
        for period in periods:
            df[f'MA{period}'] = df['close'].rolling(window=period).mean()
        return df
    
    @staticmethod
    def calculate_ema(data: pd.DataFrame, periods: list = [12, 26]) -> pd.DataFrame:
        """
        计算指数移动平均线
        
        :param data: 股票数据DataFrame
        :param periods: EMA周期列表
        :return: 包含EMA的DataFrame
        """
        df = data.copy()
        for period in periods:
            df[f'EMA{period}'] = df['close'].ewm(span=period, adjust=False).mean()
        return df
    
    @staticmethod
    def calculate_macd(data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """
        计算MACD指标
        
        :param data: 股票数据DataFrame
        :param fast: 快线周期
        :param slow: 慢线周期
        :param signal: 信号线周期
        :return: 包含MACD的DataFrame
        """
        df = data.copy()
        
        # 计算EMA
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        
        # MACD线
        df['MACD'] = ema_fast - ema_slow
        
        # 信号线
        df['MACD_Signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
        
        # MACD柱状图
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        
        return df
    
    @staticmethod
    def calculate_rsi(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        计算RSI指标
        
        :param data: 股票数据DataFrame
        :param period: RSI周期
        :return: 包含RSI的DataFrame
        """
        df = data.copy()
        
        # 计算价格变化
        delta = df['close'].diff()
        
        # 分离上涨和下跌
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # 计算平均上涨和下跌
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        # 计算RS和RSI
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        return df
    
    @staticmethod
    def calculate_kdj(data: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
        """
        计算KDJ指标
        
        :param data: 股票数据DataFrame
        :param n: RSV周期
        :param m1: K值平滑周期
        :param m2: D值平滑周期
        :return: 包含KDJ的DataFrame
        """
        df = data.copy()
        
        # 计算RSV
        low_list = df['low'].rolling(window=n, min_periods=n).min()
        high_list = df['high'].rolling(window=n, min_periods=n).max()
        rsv = (df['close'] - low_list) / (high_list - low_list) * 100
        
        # 计算K、D、J值
        df['K'] = rsv.ewm(com=m1-1, adjust=False).mean()
        df['D'] = df['K'].ewm(com=m2-1, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']
        
        return df
    
    @staticmethod
    def calculate_bollinger(data: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
        """
        计算布林带
        
        :param data: 股票数据DataFrame
        :param period: 周期
        :param std_dev: 标准差倍数
        :return: 包含布林带的DataFrame
        """
        df = data.copy()
        
        # 中轨线（移动平均线）
        df['BOLL_MID'] = df['close'].rolling(window=period).mean()
        
        # 标准差
        rolling_std = df['close'].rolling(window=period).std()
        
        # 上轨线和下轨线
        df['BOLL_UP'] = df['BOLL_MID'] + (rolling_std * std_dev)
        df['BOLL_DOWN'] = df['BOLL_MID'] - (rolling_std * std_dev)
        
        return df
    
    @staticmethod
    def calculate_volume_ma(data: pd.DataFrame, periods: list = [5, 10, 20]) -> pd.DataFrame:
        """
        计算成交量移动平均线
        
        :param data: 股票数据DataFrame
        :param periods: 周期列表
        :return: 包含成交量MA的DataFrame
        """
        df = data.copy()
        for period in periods:
            df[f'VOL_MA{period}'] = df['vol'].rolling(window=period).mean()
        return df
    
    @staticmethod
    def calculate_obv(data: pd.DataFrame) -> pd.DataFrame:
        """
        计算OBV（On-Balance Volume）指标
        
        OBV是通过累积成交量来判断价格趋势的指标：
        - 如果当日收盘价 > 前一日收盘价，OBV = 前一日OBV + 当日成交量
        - 如果当日收盘价 < 前一日收盘价，OBV = 前一日OBV - 当日成交量
        - 如果当日收盘价 = 前一日收盘价，OBV = 前一日OBV
        
        :param data: 股票数据DataFrame
        :return: 包含OBV的DataFrame
        """
        df = data.copy()
        
        # 计算价格变化
        price_change = df['close'].diff()
        
        # 根据价格变化确定成交量方向
        direction = np.where(price_change > 0, 1, np.where(price_change < 0, -1, 0))
        
        # 计算每日OBV变化
        obv_change = df['vol'] * direction
        
        # 累积计算OBV
        df['OBV'] = obv_change.cumsum()
        
        # 计算OBV的移动平均线
        df['OBV_MA'] = df['OBV'].rolling(window=20).mean()
        
        return df
    
    @staticmethod
    def calculate_all_indicators(data: pd.DataFrame) -> pd.DataFrame:
        """
        计算所有技术指标
        
        :param data: 股票数据DataFrame
        :return: 包含所有技术指标的DataFrame
        """
        df = data.copy()
        
        # 移动平均线
        df = TechnicalIndicators.calculate_ma(df)
        
        # EMA
        df = TechnicalIndicators.calculate_ema(df)
        
        # MACD
        df = TechnicalIndicators.calculate_macd(df)
        
        # RSI
        df = TechnicalIndicators.calculate_rsi(df)
        
        # KDJ
        df = TechnicalIndicators.calculate_kdj(df)
        
        # 布林带
        df = TechnicalIndicators.calculate_bollinger(df)
        
        # 成交量MA
        df = TechnicalIndicators.calculate_volume_ma(df)
        
        # OBV指标
        df = TechnicalIndicators.calculate_obv(df)
        
        return df
    
    @staticmethod
    def get_indicator_summary(data: pd.DataFrame) -> Dict[str, Any]:
        """
        获取技术指标汇总
        
        :param data: 包含技术指标的DataFrame
        :return: 指标汇总字典
        """
        if data.empty:
            return {}
        
        latest = data.iloc[-1]
        
        summary = {
            'price': {
                'close': round(latest['close'], 2) if 'close' in latest else None,
                'open': round(latest['open'], 2) if 'open' in latest else None,
                'high': round(latest['high'], 2) if 'high' in latest else None,
                'low': round(latest['low'], 2) if 'low' in latest else None,
            },
            'moving_averages': {
                'MA5': round(latest['MA5'], 2) if 'MA5' in latest else None,
                'MA10': round(latest['MA10'], 2) if 'MA10' in latest else None,
                'MA20': round(latest['MA20'], 2) if 'MA20' in latest else None,
                'MA60': round(latest['MA60'], 2) if 'MA60' in latest else None,
            },
            'macd': {
                'macd': round(latest['MACD'], 4) if 'MACD' in latest else None,
                'signal': round(latest['MACD_Signal'], 4) if 'MACD_Signal' in latest else None,
                'hist': round(latest['MACD_Hist'], 4) if 'MACD_Hist' in latest else None,
            },
            'rsi': {
                'rsi': round(latest['RSI'], 2) if 'RSI' in latest else None,
            },
            'kdj': {
                'k': round(latest['K'], 2) if 'K' in latest else None,
                'd': round(latest['D'], 2) if 'D' in latest else None,
                'j': round(latest['J'], 2) if 'J' in latest else None,
            },
            'bollinger': {
                'upper': round(latest['BOLL_UP'], 2) if 'BOLL_UP' in latest else None,
                'mid': round(latest['BOLL_MID'], 2) if 'BOLL_MID' in latest else None,
                'lower': round(latest['BOLL_DOWN'], 2) if 'BOLL_DOWN' in latest else None,
            },
            'obv': {
                'OBV': round(latest['OBV'], 2) if 'OBV' in latest else None,
                'OBV_MA': round(latest['OBV_MA'], 2) if 'OBV_MA' in latest else None,
                'OBV_Trend': '上升' if 'OBV' in latest and 'OBV_MA' in latest and latest['OBV'] > latest['OBV_MA'] else '下降' if 'OBV' in latest and 'OBV_MA' in latest and latest['OBV'] < latest['OBV_MA'] else '持平',
            }
        }
        
        return summary
