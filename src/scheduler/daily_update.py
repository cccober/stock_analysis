import schedule
import time
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional
import threading

from ..database import DuckDBManager
from ..data_sync import StockDataSync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DailyUpdateScheduler:
    """每日数据更新调度器"""
    
    def __init__(self, db_path: str = "data/stock_data.duckdb", 
                 update_time: str = "18:00",
                 token: Optional[str] = None):
        """
        初始化调度器
        
        :param db_path: 数据库路径
        :param update_time: 每日更新时间 (HH:MM)
        :param token: Tushare API token
        """
        self.db_path = db_path
        self.update_time = update_time
        self.token = token
        self.db_manager = None
        self.data_sync = None
        self._running = False
        self._thread = None
    
    def _init_components(self):
        """初始化组件"""
        try:
            self.db_manager = DuckDBManager(self.db_path)
            self.data_sync = StockDataSync(self.token)
            logger.info("调度器组件初始化完成")
        except Exception as e:
            logger.error(f"调度器组件初始化失败: {e}")
            raise
    
    def _do_update(self):
        """执行数据更新"""
        try:
            logger.info(f"开始执行定时数据更新 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
            
            if self.db_manager is None or self.data_sync is None:
                self._init_components()
            
            # 执行每日更新
            result = self.data_sync.sync_daily_update(self.db_manager)
            
            logger.info(f"定时更新完成: {result['message']}")
            
        except Exception as e:
            logger.error(f"定时更新失败: {e}")
        finally:
            # 保持连接以便下次使用
            pass
    
    def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("调度器已在运行中")
            return
        
        try:
            self._init_components()
            
            # 设置定时任务
            schedule.every().day.at(self.update_time).do(self._do_update)
            
            self._running = True
            logger.info(f"调度器已启动，每日 {self.update_time} 执行数据更新")
            
            # 在后台线程中运行调度器
            self._thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self._thread.start()
            
        except Exception as e:
            logger.error(f"启动调度器失败: {e}")
            self._running = False
            raise
    
    def _run_scheduler(self):
        """运行调度器循环"""
        while self._running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"调度器运行出错: {e}")
                time.sleep(60)
    
    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        
        if self.db_manager:
            self.db_manager.close()
        
        logger.info("调度器已停止")
    
    def run_once(self):
        """立即执行一次更新"""
        try:
            self._init_components()
            self._do_update()
        except Exception as e:
            logger.error(f"手动更新失败: {e}")
            raise
    
    def is_running(self) -> bool:
        """检查调度器是否正在运行"""
        return self._running
