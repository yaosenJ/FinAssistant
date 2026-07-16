#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沪市个股数据爬取脚本
使用 akshare 爬取沪市A股日K线、公司信息、财务数据，存入本地 JSON 文件

用法:
    python crawl_sh_stock_data.py --mode full       # 全量爬取
    python crawl_sh_stock_data.py --mode kline      # 增量更新K线
    python crawl_sh_stock_data.py --mode kline --add-indicators  # K线+估值指标
    python crawl_sh_stock_data.py --mode indicator  # 仅补充估值指标
    python crawl_sh_stock_data.py --mode company    # 仅爬公司信息

数据存储结构:
    data/
    ├── sh_company_info.json         # 公司基本信息（含股票列表）
    └── sh_kline/                    # K线数据(按股票分文件)
        ├── 600000.json
        ├── 600004.json
        └── ...
"""

import argparse
import json
import logging
import math
import os
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import akshare as ak
import pandas as pd
import socket
socket.setdefaulttimeout(30)  # 全局网络超时30秒

# ================= 日志配置 =================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, '..', 'log')
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'sh_stock')
KLINE_DIR = os.path.join(DATA_DIR, 'sh_kline')

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(KLINE_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'crawl_sh_stock.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ================= 限速配置 =================
REQUEST_DELAY = (0.5, 1.5)       # 每只股票间隔(秒)
BATCH_PAUSE_SIZE = 50            # 每N只股票暂停一次
BATCH_PAUSE_DELAY = (5, 10)      # 批次暂停时间(秒)
MAX_RETRIES = 3                  # 最大重试次数
RETRY_BASE_DELAY = 5             # 重试基础延迟(秒)

# ================= 默认日期 =================
DEFAULT_START_DATE = '20260101'
DEFAULT_END_DATE = datetime.now().strftime('%Y%m%d')


# ================= 工具函数 =================


def retry_with_backoff(func, *args, max_retries=MAX_RETRIES, base_delay=RETRY_BASE_DELAY, **kwargs):
    """指数退避重试"""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"第{attempt + 1}次重试, 等待{delay}秒: {e}")
                time.sleep(delay)
            else:
                raise


def rate_limit():
    """请求间限速"""
    time.sleep(random.uniform(*REQUEST_DELAY))


def batch_pause(idx: int):
    """批次暂停"""
    if idx > 0 and idx % BATCH_PAUSE_SIZE == 0:
        delay = random.uniform(*BATCH_PAUSE_DELAY)
        logger.info(f"--- 已处理{idx}只股票，暂停{delay:.1f}秒 ---")
        time.sleep(delay)


def safe_float(val) -> Optional[float]:
    """安全转换为 float，NaN/None 返回 None"""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def safe_str(val) -> Optional[str]:
    """安全转换为字符串"""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    s = str(val).strip()
    return s if s else None


def date_to_str(d) -> Optional[str]:
    """将 date/datetime/Timestamp 转为 YYYY-MM-DD 字符串"""
    if d is None:
        return None
    if isinstance(d, (datetime, pd.Timestamp)):
        return d.strftime('%Y-%m-%d')
    if isinstance(d, str):
        return d
    return str(d)


def load_json(filepath: str) -> any:
    """加载JSON文件，不存在则返回 None"""
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(filepath: str, data: any):
    """保存数据到JSON文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ================= JSON 存储类 =================
class JsonFileStorage:
    """本地 JSON 文件存储封装"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.company_info_path = os.path.join(data_dir, 'sh_company_info.json')
        self.kline_dir = os.path.join(data_dir, 'sh_kline')

        # 内存缓存：公司信息 {ts_code: info}（同时作为股票列表使用）
        self._company_info: Optional[Dict] = None

    def init_storage(self):
        """确保存储目录存在"""
        os.makedirs(self.kline_dir, exist_ok=True)
        logger.info(f"存储目录就绪: {self.data_dir}")

    # ---------- 股票列表（从公司信息获取） ----------
    def get_all_stocks(self) -> List[Dict]:
        """获取所有股票列表（从 company_info 加载）"""
        return list(self.load_company_info().values())

    # ---------- K线数据 ----------
    def _kline_path(self, symbol: str) -> str:
        return os.path.join(self.kline_dir, f"{symbol}.json")

    def get_latest_k_date(self, symbol: str) -> Optional[str]:
        """查询某只股票最新交易日期"""
        data = load_json(self._kline_path(symbol))
        if not data:
            return None
        dates = [r['trade_date'] for r in data if 'trade_date' in r]
        return max(dates) if dates else None

    def insert_kline_batch(self, symbol: str, records: List[Dict]):
        """追加K线数据到对应股票文件（按日期去重）"""
        if not records:
            return
        filepath = self._kline_path(symbol)
        existing = load_json(filepath) or []

        # 用 trade_date 做 key 去重合并
        date_map = {r['trade_date']: r for r in existing}
        for r in records:
            date_map[r['trade_date']] = r

        merged = sorted(date_map.values(), key=lambda x: x['trade_date'])
        save_json(filepath, merged)

    # ---------- 公司信息 ----------
    def load_company_info(self) -> Dict[str, Dict]:
        """加载公司信息缓存"""
        if self._company_info is None:
            data = load_json(self.company_info_path)
            self._company_info = {item['ts_code']: item for item in data} if data else {}
        return self._company_info

    def upsert_company_info(self, info: Dict):
        """写入/更新单只股票公司信息"""
        existing = self.load_company_info()
        info['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        existing[info['ts_code']] = info
        save_json(self.company_info_path, list(existing.values()))
        self._company_info = existing

    # ---------- 统计 ----------
    def get_stats(self) -> Dict:
        """获取存储统计信息"""
        stock_count = len(self.load_company_info())
        kline_files = len([f for f in os.listdir(self.kline_dir) if f.endswith('.json')]) if os.path.exists(self.kline_dir) else 0
        return {
            'stock_count': stock_count,
            'kline_files': kline_files,
        }


# ================= 爬取逻辑类 =================
class ShanghaiStockCrawler:
    """沪市个股数据爬取器"""

    def __init__(self, store: JsonFileStorage):
        self.store = store

    # ---------- 爬取K线数据 ----------
    def fetch_kline(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """获取单只股票日K线（新浪数据源）"""
        sina_symbol = f"sh{symbol}"
        df = retry_with_backoff(
            ak.stock_zh_a_daily,
            symbol=sina_symbol,
            start_date=start_date, end_date=end_date,
            adjust="qfq"
        )
        if df is None or df.empty:
            return None
        return df

    def crawl_kline(self, stocks: List[Dict], incremental: bool = True):
        """爬取所有股票K线数据"""
        end_date = DEFAULT_END_DATE
        total = len(stocks)
        success = 0
        fail = 0
        logger.info(f"开始爬取K线, 共{total}只股票, end_date={end_date}")

        for idx, stock in enumerate(stocks):
            symbol = stock['symbol']
            ts_code = stock['ts_code']

            try:
                start_date = DEFAULT_START_DATE
                if incremental:
                    latest = self.store.get_latest_k_date(symbol)
                    if latest:
                        next_day = (datetime.strptime(latest, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y%m%d')
                        start_date = next_day

                if start_date > end_date:
                    continue

                rate_limit()
                df_kline = self.fetch_kline(symbol, start_date, end_date)
                if df_kline is None or df_kline.empty:
                    continue

                records = self._build_kline_records(symbol, ts_code, df_kline)
                if records:
                    self.store.insert_kline_batch(symbol, records)
                    success += 1
                    logger.info(f"[{idx + 1}/{total}] {ts_code} K线写入 {len(records)} 条")
                else:
                    success += 1

            except Exception as e:
                fail += 1
                logger.error(f"[{idx + 1}/{total}] {ts_code} K线爬取失败: {e}")

            batch_pause(idx + 1)

        logger.info(f"K线爬取完成: 成功 {success}, 失败 {fail}, 共 {total}")

    def _build_kline_records(self, symbol: str, ts_code: str, df_kline: pd.DataFrame) -> List[Dict]:
        """将K线DataFrame转为记录列表"""
        raw_rows = []
        for _, row in df_kline.iterrows():
            trade_date = date_to_str(row.get('date'))
            if not trade_date:
                continue
            raw_rows.append({
                'trade_date': trade_date,
                'open': safe_float(row.get('open')),
                'close': safe_float(row.get('close')),
                'high': safe_float(row.get('high')),
                'low': safe_float(row.get('low')),
                'volume': safe_float(row.get('volume')),
                'amount': safe_float(row.get('amount')),
                'outstanding_share': safe_float(row.get('outstanding_share')),
            })

        records = []
        for i, r in enumerate(raw_rows):
            close = r['close']
            pre_close = raw_rows[i - 1]['close'] if i > 0 else None

            pct_chg = None
            if close and pre_close and pre_close > 0:
                pct_chg = round((close - pre_close) / pre_close * 100, 4)

            change_data = None
            if close and pre_close:
                change_data = round(close - pre_close, 4)

            ln_pctchg = None
            if close and pre_close and close > 0 and pre_close > 0:
                try:
                    ln_pctchg = round(math.log(close / pre_close), 6)
                except (ValueError, ZeroDivisionError):
                    pass

            records.append({
                'trade_date': r['trade_date'],
                'symbol': symbol,
                'ts_code': ts_code,
                'open': r['open'],
                'close': close,
                'high': r['high'],
                'low': r['low'],
                'pre_close': pre_close,
                'change_data': change_data,
                'pct_chg': pct_chg,
                'volume': r['volume'],
                'amount': r['amount'],
                'total_share': r['outstanding_share'],
                'ln_pctchg': ln_pctchg,
            })
        return records

    # ---------- 爬取公司信息 ----------
    def fetch_all_company_info(self) -> List[Dict]:
        """一次性获取全部沪市公司基本信息（使用上交所公开接口，不会被封）"""
        result = []
        for symbol_name in ['主板A股', '科创板']:
            try:
                df = retry_with_backoff(ak.stock_info_sh_name_code, symbol=symbol_name)
                if df is None or df.empty:
                    continue
                for _, row in df.iterrows():
                    code = str(row['证券代码']).zfill(6)
                    list_date = None
                    raw_date = str(row.get('上市日期', ''))
                    if raw_date:
                        try:
                            list_date = datetime.strptime(raw_date, '%Y-%m-%d').strftime('%Y-%m-%d')
                        except ValueError:
                            list_date = raw_date
                    result.append({
                        'ts_code': f"{code}.SH",
                        'symbol': code,
                        'stock_name': safe_str(row.get('证券简称', '')),
                        'full_name': safe_str(row.get('公司全称', '')),
                        'industry': '',
                        'list_date': list_date,
                        'market': 'SH',
                    })
                logger.info(f"获取{symbol_name}公司信息: {len(df)} 条")
            except Exception as e:
                logger.warning(f"获取{symbol_name}公司信息失败: {e}")
        return result

    def crawl_company_info(self, stocks: List[Dict]):
        """爬取所有股票公司信息"""
        logger.info("正在获取沪市公司信息...")
        all_info = self.fetch_all_company_info()
        success = 0
        for info in all_info:
            try:
                self.store.upsert_company_info(info)
                success += 1
            except Exception as e:
                logger.error(f"{info.get('ts_code')} 保存失败: {e}")
        logger.info(f"公司信息完成: {success}/{len(all_info)}")

    # ---------- 编排入口 ----------
    def run_full_crawl(self):
        """全量爬取: 公司信息 -> K线"""
        logger.info("=" * 50)
        logger.info("开始全量爬取")
        logger.info("=" * 50)

        self.crawl_company_info([])
        stocks = self.store.get_all_stocks()
        if not stocks:
            logger.error("未获取到股票列表，终止")
            return

        self.crawl_kline(stocks, incremental=False)

        logger.info("全量爬取完成!")

    def run_add_indicators(self):
        """补充估值指标到K线数据"""
        from add_indicators_to_kline import process_single_stock
        logger.info("=" * 50)
        logger.info("开始补充估值指标")
        logger.info("=" * 50)

        kline_dir = self.store.kline_dir
        if not os.path.exists(kline_dir):
            logger.error(f"K线目录不存在: {kline_dir}")
            return

        files = sorted([f for f in os.listdir(kline_dir) if f.endswith('.json')])
        total = len(files)
        success = 0
        skip = 0
        fail = 0

        for idx, filename in enumerate(files):
            symbol = filename.replace('.json', '')
            filepath = os.path.join(kline_dir, filename)

            result = process_single_stock(symbol, filepath, idx, total)
            if result == 'success':
                success += 1
            elif result == 'skip':
                skip += 1
            else:
                fail += 1

            if (idx + 1) % BATCH_PAUSE_SIZE == 0:
                delay = random.uniform(*BATCH_PAUSE_DELAY)
                logger.info(f"--- 已处理{idx+1}只，暂停{delay:.1f}秒 ---")
                time.sleep(delay)

        logger.info(f"指标补充完成: 成功 {success}, 跳过 {skip}, 失败 {fail}, 共 {total}")

# ================= 主入口 =================
def main():
    parser = argparse.ArgumentParser(description='沪市个股数据爬取工具')
    parser.add_argument('--mode', type=str, default='kline',
                        choices=['full', 'kline', 'indicator', 'company'],
                        help='爬取模式: full=全量, kline=增量K线, indicator=补充估值指标, company=仅公司信息')
    parser.add_argument('--add-indicators', action='store_true',
                        help='K线爬取后自动补充估值指标（仅 --mode kline 时有效）')
    args = parser.parse_args()

    logger.info(f"启动模式: {args.mode}")
    logger.info(f"数据目录: {DATA_DIR}")

    store = JsonFileStorage(DATA_DIR)
    store.init_storage()
    crawler = ShanghaiStockCrawler(store)

    if args.mode == 'full':
        crawler.run_full_crawl()
    elif args.mode == 'kline':
        stocks = store.get_all_stocks()
        if not stocks:
            logger.error("请先运行 --mode company 获取股票列表")
            return
        crawler.crawl_kline(stocks, incremental=True)
        if args.add_indicators:
            crawler.run_add_indicators()
    elif args.mode == 'indicator':
        crawler.run_add_indicators()
    elif args.mode == 'company':
        crawler.crawl_company_info([])

    stats = store.get_stats()
    logger.info(f"任务结束 - 股票: {stats['stock_count']}, K线文件: {stats['kline_files']}")


if __name__ == '__main__':
    main()
