# 股票分析平台

基于 DuckDB 的高性能股票数据分析和可视化平台，仿照 PandaAI QuantFlow 和 PandaFactor 设计风格构建。

## 功能特性

- **数据存储**: 使用 DuckDB 数据库存储股票历史数据，高性能查询
- **数据同步**: 支持从 Tushare 自动同步股票数据
- **定时更新**: 服务启动后自动每日定时抓取更新数据
- **REST API**: 基于 FastAPI 的高性能 API 服务
- **数据可视化**: 内置前端界面，支持股票查询和统计分析
- **增量更新**: 智能识别已存在数据，避免重复抓取

## 项目结构

```
.
├── src/
│   ├── api/              # FastAPI 后端服务
│   │   └── main.py       # API 主入口
│   ├── database/         # 数据库管理模块
│   │   └── db_manager.py # DuckDB 数据库操作
│   ├── data_sync/        # 数据同步模块
│   │   └── stock_data_sync.py  # Tushare 数据同步
│   └── scheduler/        # 定时任务模块
│       └── daily_update.py     # 每日更新调度器
├── scripts/              # 工具脚本
│   ├── init_database.py  # 数据库初始化
│   └── sync_data.py      # 手动数据同步
├── data/                 # 数据目录
│   └── stock_data.duckdb # DuckDB 数据库文件
├── main.py               # 服务启动入口
├── requirements.txt      # Python 依赖
└── README.md             # 项目说明
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 快速开始

### 1. 初始化数据库

将 CSV 数据导入 DuckDB 数据库：

```bash
python scripts/init_database.py --csv all_stock_history.csv all_stock_history_part2.csv
```

### 2. 启动服务

```bash
python main.py
```

服务启动后：
- API 文档: http://localhost:8000/docs
- 前端界面: http://localhost:8000/app

### 3. 手动同步数据

```bash
# 同步所有股票最新数据
python scripts/sync_data.py

# 同步指定股票
python scripts/sync_data.py --code 000001.SZ

# 同步指定日期范围
python scripts/sync_data.py --start 20240101 --end 20241231
```

## API 接口

### 股票数据查询

- `GET /api/stocks` - 获取所有股票列表
- `GET /api/stock/{ts_code}` - 获取指定股票历史数据
- `GET /api/stock/{ts_code}/latest` - 获取最新数据
- `GET /api/stock/{ts_code}/stats` - 获取统计信息

### 数据同步

- `POST /api/sync` - 手动同步数据
- `POST /api/sync/daily` - 执行每日更新

### 系统管理

- `GET /api/health` - 健康检查
- `GET /api/query` - 自定义 SQL 查询

## 环境变量

- `TUSHARE_TOKEN` - Tushare API Token
- `DB_PATH` - 数据库文件路径 (默认: data/stock_data.duckdb)

## 定时更新

服务启动后会自动启动定时更新调度器，默认每天 18:00 执行数据更新。

## 技术栈

- **后端**: FastAPI + DuckDB
- **数据源**: Tushare
- **前端**: HTML/JavaScript (原生)
- **定时任务**: schedule
