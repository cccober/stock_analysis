import tushare as ts
import pandas as pd

# 设置你的 tushare token，需要在 tushare 官网注册获取
ts.set_token('1ff975ea535e82679de240fc493698506452ace8f002152c965aed01')
pro = ts.pro_api()

def get_all_stock_codes():
    """
    获取所有 A 股股票代码
    """
    data = pro.stock_basic(exchange='', list_status='L', fields='ts_code')
    return data['ts_code'].tolist()

def download_stock_data(ts_code, start_date, end_date):
    """
    下载指定股票的历史数据

    :param ts_code: 股票代码，例如 '000001.SZ'
    :param start_date: 开始日期，格式为 'YYYYMMDD'
    :param end_date: 结束日期，格式为 'YYYYMMDD'
    :return: 包含历史数据的 DataFrame
    """
    df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    return df

if __name__ == "__main__":
    # 获取所有 A 股股票代码
    stock_codes = get_all_stock_codes()
    start_date = '20030101'
    end_date = '20240501'

    all_stock_data = []
    for code in stock_codes:
        try:
            print(f"正在下载 {code} 的数据...")
            data = download_stock_data(code, start_date, end_date)
            all_stock_data.append(data)
        except Exception as e:
            print(f"下载 {code} 数据时出错: {e}")

    # 合并所有数据
    result_df = pd.concat(all_stock_data, ignore_index=True)

    # 保存数据到 CSV 文件
    result_df.to_csv('all_stock_history.csv', index=False)
    print("所有股票历史数据已保存到 all_stock_history_2.csv")
    # 示例：下载平安银行（000001.SZ）从 2023 年 1 月 1 日到 2023 年 12 月 31 日的数据
    stock_data = download_stock_data(ts_code='000001.SZ', start_date='20230101', end_date='20231231')
    print(stock_data)
    # 如果你想将数据保存为 CSV 文件，可以使用以下代码
    # stock_data.to_csv('000001_SZ_history.csv', index=False)