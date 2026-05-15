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

### 1. 启动服务

```bash
python main.py
```

服务启动后：
- API 文档: http://localhost:8000/docs
- 前端界面: http://localhost:8000/app

### 2. 使用虚拟环境启动（推荐）

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python main.py
```

### 3. 指定主机和端口启动

```bash
python main.py --host 0.0.0.0 --port 8080
```

### 4. 开发模式启动（自动重载）

```bash
python main.py --reload
```

## 数据同步

### 通过前端界面同步

1. 打开 http://localhost:8000/app
2. 点击"全量同步"按钮同步所有股票数据
3. 点击"每日更新"按钮同步最新数据

### 通过 API 同步

```bash
# 全量同步（从数据库最新日期到今日）
curl -X POST http://localhost:8000/api/sync \
  -H "Content-Type: application/json" \
  -d '{}'

# 同步指定日期范围
curl -X POST http://localhost:8000/api/sync \
  -H "Content-Type: application/json" \
  -d '{"start_date": "20240101", "end_date": "20241231"}'

# 同步指定股票
curl -X POST http://localhost:8000/api/sync \
  -H "Content-Type: application/json" \
  -d '{"ts_code": "000001.SZ"}'

# 每日更新
curl -X POST http://localhost:8000/api/sync/daily
```

### 通过脚本同步

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
- `GET /api/stock/{ts_code}/kline` - 获取 K 线数据
- `GET /api/stock/{ts_code}/indicators` - 获取技术指标
- `GET /api/stock/{ts_code}/stats` - 获取统计信息

### 数据同步

- `POST /api/sync` - 手动同步数据
- `POST /api/sync/basic` - 同步股票基础信息
- `POST /api/sync/daily` - 执行每日更新

### 新闻资讯

- `GET /api/news` - 获取股票新闻
- `POST /api/news/favorites` - 获取自选股票新闻

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
