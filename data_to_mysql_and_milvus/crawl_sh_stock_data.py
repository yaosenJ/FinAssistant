#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沪市个股数据爬取脚本
使用 akshare 爬取沪市A股日K线、公司信息、财务数据，存入本地 JSON 文件

用法:
    python crawl_sh_stock_data.py --mode full       # 全量爬取
    python crawl_sh_stock_data.py --mode daily      # 每日增量更新
    python crawl_sh_stock_data.py --mode kline      # 仅爬K线
    python crawl_sh_stock_data.py --mode company    # 仅爬公司信息
    python crawl_sh_stock_data.py --mode financial  # 仅爬财务数据

数据存储结构:
    data/
    ├── sh_stock_list.json           # 沪市A股列表
    ├── sh_company_info.json         # 公司基本信息
    ├── sh_kline/                    # K线数据(按股票分文件)
    │   ├── 600000.json
    │   ├── 600004.json
    │   └── ...
    └── sh_financial/                # 财务数据(按股票分文件)
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
import sys
import threading
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
FINANCIAL_DIR = os.path.join(DATA_DIR, 'sh_financial')

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(KLINE_DIR, exist_ok=True)
os.makedirs(FINANCIAL_DIR, exist_ok=True)

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
DEFAULT_END_DATE = '20260710'


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


def call_with_timeout(func, *args, timeout=30, **kwargs):
    """在子线程中执行函数，超时则返回 None"""
    result = [None]
    error = [None]

    def target():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        logger.warning(f"{func.__name__} 超时({timeout}秒)")
        return None
    if error[0]:
        raise error[0]
    return result[0]


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
        self.stock_list_path = os.path.join(data_dir, 'sh_stock_list.json')
        self.company_info_path = os.path.join(data_dir, 'sh_company_info.json')
        self.kline_dir = os.path.join(data_dir, 'sh_kline')
        self.financial_dir = os.path.join(data_dir, 'sh_financial')

        # 内存缓存：股票列表 {ts_code: stock_info}
        self._stock_list: Optional[Dict] = None
        # 内存缓存：公司信息 {ts_code: info}
        self._company_info: Optional[Dict] = None

    def init_storage(self):
        """确保存储目录存在"""
        os.makedirs(self.kline_dir, exist_ok=True)
        os.makedirs(self.financial_dir, exist_ok=True)
        logger.info(f"存储目录就绪: {self.data_dir}")

    # ---------- 股票列表 ----------
    def load_stock_list(self) -> Dict[str, Dict]:
        """加载股票列表缓存"""
        if self._stock_list is None:
            data = load_json(self.stock_list_path)
            self._stock_list = {item['ts_code']: item for item in data} if data else {}
        return self._stock_list

    def upsert_stock_list(self, stocks: List[Dict]):
        """写入/更新股票列表"""
        existing = self.load_stock_list()
        for s in stocks:
            existing[s['ts_code']] = {
                'symbol': s['symbol'],
                'ts_code': s['ts_code'],
                'stock_name': s.get('stock_name', ''),
                'market': s.get('market', 'SH'),
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        save_json(self.stock_list_path, list(existing.values()))
        self._stock_list = existing
        logger.info(f"写入 sh_stock_list: {len(stocks)} 条, 总计 {len(existing)} 条")

    def get_all_stocks(self) -> List[Dict]:
        """获取所有股票列表"""
        return list(self.load_stock_list().values())

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

    # ---------- 财务数据 ----------
    def _financial_path(self, symbol: str) -> str:
        return os.path.join(self.financial_dir, f"{symbol}.json")

    def get_latest_fin_date(self, symbol: str) -> Optional[str]:
        """查询某只股票最新报告期"""
        data = load_json(self._financial_path(symbol))
        if not data:
            return None
        dates = [r['report_date'] for r in data if 'report_date' in r]
        return max(dates) if dates else None

    def upsert_financial_data(self, symbol: str, records: List[Dict]):
        """追加财务数据到对应股票文件（按报告期去重合并）"""
        if not records:
            return
        filepath = self._financial_path(symbol)
        existing = load_json(filepath) or []

        # 用 report_date 做 key 去重合并
        date_map = {r['report_date']: r for r in existing}
        for r in records:
            date_map[r['report_date']] = r

        merged = sorted(date_map.values(), key=lambda x: x['report_date'])
        save_json(filepath, merged)

    # ---------- 统计 ----------
    def get_stats(self) -> Dict:
        """获取存储统计信息"""
        stock_count = len(self.load_stock_list())
        kline_files = len([f for f in os.listdir(self.kline_dir) if f.endswith('.json')]) if os.path.exists(self.kline_dir) else 0
        fin_files = len([f for f in os.listdir(self.financial_dir) if f.endswith('.json')]) if os.path.exists(self.financial_dir) else 0
        return {
            'stock_count': stock_count,
            'kline_files': kline_files,
            'financial_files': fin_files,
        }


# ================= 爬取逻辑类 =================
class ShanghaiStockCrawler:
    """沪市个股数据爬取器"""

    def __init__(self, store: JsonFileStorage):
        self.store = store

    # ---------- 获取沪市A股列表 ----------
    def fetch_stock_list(self) -> List[Dict]:
        """获取沪市主板A股列表"""
        logger.info("正在获取沪市A股列表...")
        df = retry_with_backoff(ak.stock_info_sh_name_code, symbol="主板A股")
        stocks = []
        for _, row in df.iterrows():
            code = str(row['证券代码']).zfill(6)
            stocks.append({
                'symbol': code,
                'ts_code': f"{code}.SH",
                'stock_name': safe_str(row.get('证券简称', '')),
                'market': 'SH',
            })
        logger.info(f"获取到 {len(stocks)} 只沪市A股")
        return stocks

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

    def fetch_indicator(self, symbol: str) -> Optional[Dict[str, pd.DataFrame]]:
        """获取估值指标(PE/PB/市值)，来源：百度股市通"""
        result = {}
        for indicator in ['总市值', '市盈率(TTM)', '市净率']:
            try:
                df = call_with_timeout(
                    retry_with_backoff, ak.stock_zh_valuation_baidu,
                    symbol=symbol, indicator=indicator, period="近一年",
                    timeout=45
                )
                if df is not None and not df.empty:
                    result[indicator] = df
            except Exception as e:
                logger.warning(f"获取估值指标 {indicator} 失败 {symbol}: {e}")
        return result if result else None

    def crawl_stock_list(self):
        """爬取并保存股票列表"""
        stocks = self.fetch_stock_list()
        self.store.upsert_stock_list(stocks)
        return stocks

    def crawl_kline(self, stocks: List[Dict], incremental: bool = True, include_indicators: bool = True):
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
                # 确定起始日期
                start_date = DEFAULT_START_DATE
                if incremental:
                    latest = self.store.get_latest_k_date(symbol)
                    if latest:
                        next_day = (datetime.strptime(latest, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y%m%d')
                        start_date = next_day

                if start_date > end_date:
                    continue  # 已是最新

                # 获取K线
                rate_limit()
                df_kline = self.fetch_kline(symbol, start_date, end_date)
                if df_kline is None or df_kline.empty:
                    continue

                # 获取估值指标（可选）
                df_ind = self.fetch_indicator(symbol) if include_indicators else None

                # 构建记录
                records = self._merge_kline_and_indicator(symbol, ts_code, df_kline, df_ind)
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

    def _merge_kline_and_indicator(self, symbol: str, ts_code: str,
                                    df_kline: pd.DataFrame, df_ind: Optional[Dict[str, pd.DataFrame]]) -> List[Dict]:
        """合并K线和估值指标数据"""
        records = []

        # 构建估值指标字典 {日期字符串: {pe, pb, total_mv}}
        ind_map = {}
        if df_ind:
            indicator_keys = {
                '市盈率(TTM)': 'pe',
                '市净率': 'pb',
                '总市值': 'total_mv',
            }
            for ind_name, col_name in indicator_keys.items():
                df = df_ind.get(ind_name)
                if df is not None:
                    for _, row in df.iterrows():
                        d = date_to_str(row.get('date'))
                        if d:
                            if d not in ind_map:
                                ind_map[d] = {}
                            ind_map[d][col_name] = safe_float(row.get('value'))

        # 先提取原始数据到列表，方便计算 pre_close
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

            ind = ind_map.get(r['trade_date'], {})

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
                'pe': ind.get('pe'),
                'pb': ind.get('pb'),
                'total_mv': ind.get('total_mv'),
                'total_share': r['outstanding_share'],
                'float_share': None,
                'circ_mv': None,
                'ln_pctchg': ln_pctchg,
            })
        return records

    # ---------- 爬取公司信息 ----------
    def fetch_company_info(self, symbol: str) -> Optional[Dict]:
        """获取单只股票公司基本信息"""
        try:
            df = retry_with_backoff(ak.stock_individual_info_em, symbol=symbol)
            if df is None or df.empty:
                return None

            info_map = {}
            for _, row in df.iterrows():
                key = safe_str(row.get('item', ''))
                val = safe_str(row.get('value', ''))
                if key:
                    info_map[key] = val

            ts_code = f"{symbol}.SH"

            list_date = None
            raw_date = info_map.get('上市时间', '')
            if raw_date:
                try:
                    list_date = datetime.strptime(str(raw_date), '%Y%m%d').strftime('%Y-%m-%d')
                except ValueError:
                    list_date = None

            return {
                'ts_code': ts_code,
                'symbol': symbol,
                'stock_name': info_map.get('股票简称', ''),
                'full_name': info_map.get('股票简称', ''),
                'industry': info_map.get('行业', ''),
                'list_date': list_date,
                'province': info_map.get('省份', ''),
                'city': None,
                'main_business': None,
                'chairman': None,
                'website': None,
            }
        except Exception as e:
            logger.warning(f"获取公司信息失败 {symbol}: {e}")
            return None

    def crawl_company_info(self, stocks: List[Dict]):
        """爬取所有股票公司信息"""
        total = len(stocks)
        success = 0
        fail = 0

        for idx, stock in enumerate(stocks):
            symbol = stock['symbol']
            try:
                rate_limit()
                info = self.fetch_company_info(symbol)
                if info:
                    self.store.upsert_company_info(info)
                    success += 1
                    if (idx + 1) % 100 == 0:
                        logger.info(f"[{idx + 1}/{total}] 公司信息进度...")
            except Exception as e:
                fail += 1
                logger.error(f"[{idx + 1}/{total}] {symbol} 公司信息爬取失败: {e}")

            batch_pause(idx + 1)

        logger.info(f"公司信息爬取完成: 成功 {success}, 失败 {fail}, 共 {total}")

    # ---------- 爬取财务数据 ----------
    def fetch_financial_data(self, symbol: str, ts_code: str,
                              incremental: bool = True) -> List[Dict]:
        """获取单只股票财务分析指标"""
        try:
            df = retry_with_backoff(ak.stock_financial_analysis_indicator, symbol=symbol)
            if df is None or df.empty:
                return []

            latest_date = None
            if incremental:
                latest_date = self.store.get_latest_fin_date(symbol)

            records = []
            for _, row in df.iterrows():
                report_date = date_to_str(row.get('日期'))
                if not report_date:
                    continue
                if latest_date and report_date <= latest_date:
                    continue

                month_day = report_date[5:]
                if month_day == '12-31':
                    report_type = '年报'
                elif month_day == '06-30':
                    report_type = '半年报'
                elif month_day == '03-31':
                    report_type = '一季报'
                elif month_day == '09-30':
                    report_type = '三季报'
                else:
                    report_type = None

                records.append({
                    'ts_code': ts_code,
                    'symbol': symbol,
                    'report_date': report_date,
                    'report_type': report_type,
                    'revenue': safe_float(row.get('营业总收入(万元)')),
                    'net_profit': safe_float(row.get('净利润(万元)')),
                    'net_profit_deducted': safe_float(row.get('扣非净利润(万元)')),
                    'gross_profit_margin': safe_float(row.get('销售毛利率(%)')),
                    'net_profit_margin': safe_float(row.get('销售净利率(%)')),
                    'total_assets': safe_float(row.get('总资产(万元)')),
                    'total_liabilities': safe_float(row.get('总负债(万元)')),
                    'total_equity': safe_float(row.get('股东权益(万元)')),
                    'debt_asset_ratio': safe_float(row.get('资产负债率(%)')),
                    'operating_cashflow': safe_float(row.get('经营现金流量净额(万元)')),
                    'investing_cashflow': safe_float(row.get('投资现金流量净额(万元)')),
                    'financing_cashflow': safe_float(row.get('筹资现金流量净额(万元)')),
                    'eps': safe_float(row.get('基本每股收益(元)')),
                    'bps': safe_float(row.get('每股净资产(元)')),
                    'cfps': safe_float(row.get('每股经营现金流(元)')),
                    'roe': safe_float(row.get('净资产收益率(%)')),
                    'roa': safe_float(row.get('总资产收益率(%)')),
                })
            return records
        except Exception as e:
            logger.warning(f"获取财务数据失败 {symbol}: {e}")
            return []

    def crawl_financial(self, stocks: List[Dict], incremental: bool = True):
        """爬取所有股票财务数据"""
        total = len(stocks)
        success = 0
        fail = 0

        for idx, stock in enumerate(stocks):
            symbol = stock['symbol']
            ts_code = stock['ts_code']
            try:
                rate_limit()
                records = self.fetch_financial_data(symbol, ts_code, incremental)
                if records:
                    self.store.upsert_financial_data(symbol, records)
                    logger.info(f"[{idx + 1}/{total}] {ts_code} 财务数据写入 {len(records)} 条")
                success += 1
            except Exception as e:
                fail += 1
                logger.error(f"[{idx + 1}/{total}] {ts_code} 财务数据爬取失败: {e}")

            batch_pause(idx + 1)

        logger.info(f"财务数据爬取完成: 成功 {success}, 失败 {fail}, 共 {total}")

    # ---------- 编排入口 ----------
    def run_full_crawl(self):
        """全量爬取: 股票列表 -> K线 -> 公司信息 -> 财务数据"""
        logger.info("=" * 50)
        logger.info("开始全量爬取")
        logger.info("=" * 50)

        stocks = self.crawl_stock_list()
        if not stocks:
            logger.error("未获取到股票列表，终止")
            return

        self.crawl_kline(stocks, incremental=False)
        self.crawl_company_info(stocks)
        self.crawl_financial(stocks, incremental=False)

        logger.info("全量爬取完成!")

    def run_daily_update(self):
        """每日增量更新: 刷新列表 -> K线增量 -> 财务增量"""
        logger.info("=" * 50)
        logger.info("开始每日增量更新")
        logger.info("=" * 50)

        stocks = self.crawl_stock_list()
        if not stocks:
            logger.error("未获取到股票列表，终止")
            return

        self.crawl_kline(stocks, incremental=True)
        self.crawl_financial(stocks, incremental=True)

        logger.info("每日增量更新完成!")


# ================= 主入口 =================
def main():
    parser = argparse.ArgumentParser(description='沪市个股数据爬取工具')
    parser.add_argument('--mode', type=str, default='daily',
                        choices=['full', 'daily', 'kline', 'company', 'financial'],
                        help='爬取模式: full=全量, daily=增量, kline=仅K线, company=仅公司信息, financial=仅财务')
    args = parser.parse_args()

    logger.info(f"启动模式: {args.mode}")
    logger.info(f"数据目录: {DATA_DIR}")

    store = JsonFileStorage(DATA_DIR)
    store.init_storage()
    crawler = ShanghaiStockCrawler(store)

    if args.mode == 'full':
        crawler.run_full_crawl()
    elif args.mode == 'daily':
        crawler.run_daily_update()
    elif args.mode == 'kline':
        stocks = crawler.crawl_stock_list()
        crawler.crawl_kline(stocks, incremental=True, include_indicators=False)
    elif args.mode == 'company':
        stocks = crawler.crawl_stock_list()
        crawler.crawl_company_info(stocks)
    elif args.mode == 'financial':
        stocks = crawler.crawl_stock_list()
        crawler.crawl_financial(stocks, incremental=True)

    stats = store.get_stats()
    logger.info(f"任务结束 - 股票: {stats['stock_count']}, K线文件: {stats['kline_files']}, 财务文件: {stats['financial_files']}")


if __name__ == '__main__':
    main()
