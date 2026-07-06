#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沪市个股数据爬取脚本
使用 akshare 爬取沪市A股日K线、公司信息、财务数据，存入本地 MySQL market_data 库

用法:
    python crawl_sh_stock_data.py --mode full       # 全量爬取
    python crawl_sh_stock_data.py --mode daily      # 每日增量更新
    python crawl_sh_stock_data.py --mode kline      # 仅爬K线
    python crawl_sh_stock_data.py --mode company    # 仅爬公司信息
    python crawl_sh_stock_data.py --mode financial  # 仅爬财务数据
"""

import argparse
import logging
import math
import os
import random
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import akshare as ak
import numpy as np
import pandas as pd
import pymysql

# ================= 日志配置 =================
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'log')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'crawl_sh_stock.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ================= 数据库配置 =================
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'news_user',
    'password': 'km101',
    'database': 'market_data',
    'charset': 'utf8mb4',
}

# ================= 限速配置 =================
REQUEST_DELAY = (0.5, 1.5)       # 每只股票间隔(秒)
BATCH_PAUSE_SIZE = 50            # 每N只股票暂停一次
BATCH_PAUSE_DELAY = (5, 10)      # 批次暂停时间(秒)
MAX_RETRIES = 3                  # 最大重试次数
RETRY_BASE_DELAY = 5             # 重试基础延迟(秒)

# ================= 默认日期 =================
DEFAULT_START_DATE = '20100101'


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
        return d[:10]
    return str(d)


# ================= 数据库操作类 =================
class MySQLMarketData:
    """market_data 数据库操作封装"""

    def __init__(self, config: dict):
        self.config = config
        self.conn = None

    def __enter__(self):
        self.conn = pymysql.connect(**self.config)
        logger.info(f"已连接到 MySQL {self.config['host']}:{self.config['port']}/{self.config['database']}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def _execute(self, sql: str, params=None, commit: bool = False):
        with self.conn.cursor() as cursor:
            cursor.execute(sql, params)
            if commit:
                self.conn.commit()
            return cursor

    def _execute_many(self, sql: str, data_list: list, commit: bool = True):
        if not data_list:
            return
        with self.conn.cursor() as cursor:
            cursor.executemany(sql, data_list)
            if commit:
                self.conn.commit()

    # ---------- 建表 ----------
    def init_tables(self):
        """创建所有需要的表"""
        # 1) sh_stock_list
        self._execute("""
            CREATE TABLE IF NOT EXISTS sh_stock_list (
                id INT AUTO_INCREMENT PRIMARY KEY,
                symbol VARCHAR(10) NOT NULL COMMENT '股票代码(无后缀)',
                ts_code VARCHAR(15) NOT NULL COMMENT '股票代码(带后缀)',
                stock_name VARCHAR(50) COMMENT '股票名称',
                market VARCHAR(10) DEFAULT 'SH' COMMENT '市场标识',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_ts_code (ts_code),
                INDEX idx_symbol (symbol)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """, commit=True)
        logger.info("表 sh_stock_list 就绪")

        # 2) sh_company_info
        self._execute("""
            CREATE TABLE IF NOT EXISTS sh_company_info (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ts_code VARCHAR(15) NOT NULL COMMENT '股票代码',
                symbol VARCHAR(10) NOT NULL COMMENT '股票代码(无后缀)',
                stock_name VARCHAR(50) COMMENT '股票简称',
                full_name VARCHAR(100) COMMENT '公司全称',
                industry VARCHAR(50) COMMENT '所属行业',
                list_date DATE COMMENT '上市日期',
                province VARCHAR(20) COMMENT '所在省份',
                city VARCHAR(20) COMMENT '所在城市',
                main_business TEXT COMMENT '主营业务',
                chairman VARCHAR(50) COMMENT '董事长',
                website VARCHAR(200) COMMENT '公司网址',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_ts_code (ts_code),
                INDEX idx_symbol (symbol),
                INDEX idx_industry (industry)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """, commit=True)
        logger.info("表 sh_company_info 就绪")

        # 3) sh_financial_data
        self._execute("""
            CREATE TABLE IF NOT EXISTS sh_financial_data (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ts_code VARCHAR(15) NOT NULL COMMENT '股票代码',
                symbol VARCHAR(10) NOT NULL COMMENT '股票代码(无后缀)',
                report_date DATE NOT NULL COMMENT '报告期',
                report_type VARCHAR(20) COMMENT '报告类型',
                revenue DECIMAL(20,4) COMMENT '营业总收入(元)',
                net_profit DECIMAL(20,4) COMMENT '净利润(元)',
                net_profit_deducted DECIMAL(20,4) COMMENT '扣非净利润(元)',
                gross_profit_margin DECIMAL(10,4) COMMENT '毛利率(%)',
                net_profit_margin DECIMAL(10,4) COMMENT '净利率(%)',
                total_assets DECIMAL(20,4) COMMENT '总资产(元)',
                total_liabilities DECIMAL(20,4) COMMENT '总负债(元)',
                total_equity DECIMAL(20,4) COMMENT '股东权益(元)',
                debt_asset_ratio DECIMAL(10,4) COMMENT '资产负债率(%)',
                operating_cashflow DECIMAL(20,4) COMMENT '经营性现金流(元)',
                investing_cashflow DECIMAL(20,4) COMMENT '投资性现金流(元)',
                financing_cashflow DECIMAL(20,4) COMMENT '筹资性现金流(元)',
                eps DECIMAL(10,4) COMMENT '每股收益(元)',
                bps DECIMAL(10,4) COMMENT '每股净资产(元)',
                cfps DECIMAL(10,4) COMMENT '每股经营现金流(元)',
                roe DECIMAL(10,4) COMMENT '净资产收益率(%)',
                roa DECIMAL(10,4) COMMENT '总资产收益率(%)',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_code_date (ts_code, report_date),
                INDEX idx_symbol (symbol),
                INDEX idx_report_date (report_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """, commit=True)
        logger.info("表 sh_financial_data 就绪")

        # 4) 为已有 market_data_day_k 添加唯一键(如不存在)
        self.ensure_kline_unique_key()

    def ensure_kline_unique_key(self):
        """为 market_data_day_k 表添加 ts_code+trade_date 唯一键"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("SHOW INDEX FROM market_data_day_k WHERE Key_name = 'uk_code_date'")
                if cursor.fetchone():
                    logger.info("market_data_day_k 已存在唯一键 uk_code_date")
                    return
            self._execute(
                "ALTER TABLE market_data_day_k ADD UNIQUE KEY uk_code_date (ts_code, trade_date)",
                commit=True
            )
            logger.info("已为 market_data_day_k 添加唯一键 uk_code_date")
        except Exception as e:
            logger.warning(f"添加唯一键时出错(可忽略): {e}")

    # ---------- 增量水位线 ----------
    def get_latest_k_date(self, ts_code: str) -> Optional[str]:
        """查询某只股票在 market_data_day_k 中最新交易日期"""
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT MAX(trade_date) FROM market_data_day_k WHERE ts_code = %s",
                (ts_code,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                return date_to_str(row[0])
        return None

    def get_latest_fin_date(self, ts_code: str) -> Optional[str]:
        """查询某只股票在 sh_financial_data 中最新报告期"""
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT MAX(report_date) FROM sh_financial_data WHERE ts_code = %s",
                (ts_code,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                return date_to_str(row[0])
        return None

    # ---------- 写入操作 ----------
    def upsert_stock_list(self, stocks: List[Dict]):
        """批量写入/更新股票列表"""
        if not stocks:
            return
        sql = """
            INSERT INTO sh_stock_list (symbol, ts_code, stock_name, market)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE stock_name = VALUES(stock_name), updated_at = CURRENT_TIMESTAMP
        """
        data = [(s['symbol'], s['ts_code'], s['stock_name'], s.get('market', 'SH')) for s in stocks]
        self._execute_many(sql, data)
        logger.info(f"写入 sh_stock_list: {len(data)} 条")

    def insert_kline_batch(self, records: List[Dict]):
        """批量写入K线数据到 market_data_day_k"""
        if not records:
            return
        sql = """
            INSERT INTO market_data_day_k
                (trade_date, symbol, ts_code, `open`, `close`, high, low, pre_close,
                 change_data, pct_chg, volume, amount, pe, pb, total_mv,
                 total_share, float_share, circ_mv, ln_pctchg)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                `open` = VALUES(`open`), `close` = VALUES(`close`),
                high = VALUES(high), low = VALUES(low),
                pre_close = VALUES(pre_close), change_data = VALUES(change_data),
                pct_chg = VALUES(pct_chg), volume = VALUES(volume),
                amount = VALUES(amount), pe = VALUES(pe), pb = VALUES(pb),
                total_mv = VALUES(total_mv), total_share = VALUES(total_share),
                float_share = VALUES(float_share), circ_mv = VALUES(circ_mv),
                ln_pctchg = VALUES(ln_pctchg)
        """
        data = []
        for r in records:
            data.append((
                r['trade_date'], r['symbol'], r['ts_code'],
                safe_float(r.get('open')), safe_float(r.get('close')),
                safe_float(r.get('high')), safe_float(r.get('low')),
                safe_float(r.get('pre_close')), safe_float(r.get('change_data')),
                safe_float(r.get('pct_chg')), safe_float(r.get('volume')),
                safe_float(r.get('amount')), safe_float(r.get('pe')),
                safe_float(r.get('pb')), safe_float(r.get('total_mv')),
                safe_float(r.get('total_share')), safe_float(r.get('float_share')),
                safe_float(r.get('circ_mv')), safe_float(r.get('ln_pctchg')),
            ))
        self._execute_many(sql, data)

    def upsert_company_info(self, info: Dict):
        """写入/更新单只股票的公司信息"""
        sql = """
            INSERT INTO sh_company_info
                (ts_code, symbol, stock_name, full_name, industry, list_date,
                 province, city, main_business, chairman, website)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                stock_name = VALUES(stock_name), full_name = VALUES(full_name),
                industry = VALUES(industry), list_date = VALUES(list_date),
                province = VALUES(province), city = VALUES(city),
                main_business = VALUES(main_business), chairman = VALUES(chairman),
                website = VALUES(website), updated_at = CURRENT_TIMESTAMP
        """
        self._execute(sql, (
            info['ts_code'], info['symbol'], safe_str(info.get('stock_name')),
            safe_str(info.get('full_name')), safe_str(info.get('industry')),
            info.get('list_date'), safe_str(info.get('province')),
            safe_str(info.get('city')), safe_str(info.get('main_business')),
            safe_str(info.get('chairman')), safe_str(info.get('website')),
        ), commit=True)

    def upsert_financial_data(self, records: List[Dict]):
        """批量写入/更新财务数据"""
        if not records:
            return
        sql = """
            INSERT INTO sh_financial_data
                (ts_code, symbol, report_date, report_type,
                 revenue, net_profit, net_profit_deducted,
                 gross_profit_margin, net_profit_margin,
                 total_assets, total_liabilities, total_equity, debt_asset_ratio,
                 operating_cashflow, investing_cashflow, financing_cashflow,
                 eps, bps, cfps, roe, roa)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                report_type = VALUES(report_type), revenue = VALUES(revenue),
                net_profit = VALUES(net_profit), net_profit_deducted = VALUES(net_profit_deducted),
                gross_profit_margin = VALUES(gross_profit_margin),
                net_profit_margin = VALUES(net_profit_margin),
                total_assets = VALUES(total_assets), total_liabilities = VALUES(total_liabilities),
                total_equity = VALUES(total_equity), debt_asset_ratio = VALUES(debt_asset_ratio),
                operating_cashflow = VALUES(operating_cashflow),
                investing_cashflow = VALUES(investing_cashflow),
                financing_cashflow = VALUES(financing_cashflow),
                eps = VALUES(eps), bps = VALUES(bps), cfps = VALUES(cfps),
                roe = VALUES(roe), roa = VALUES(roa), updated_at = CURRENT_TIMESTAMP
        """
        data = []
        for r in records:
            data.append((
                r['ts_code'], r['symbol'], r['report_date'], safe_str(r.get('report_type')),
                safe_float(r.get('revenue')), safe_float(r.get('net_profit')),
                safe_float(r.get('net_profit_deducted')),
                safe_float(r.get('gross_profit_margin')), safe_float(r.get('net_profit_margin')),
                safe_float(r.get('total_assets')), safe_float(r.get('total_liabilities')),
                safe_float(r.get('total_equity')), safe_float(r.get('debt_asset_ratio')),
                safe_float(r.get('operating_cashflow')), safe_float(r.get('investing_cashflow')),
                safe_float(r.get('financing_cashflow')),
                safe_float(r.get('eps')), safe_float(r.get('bps')),
                safe_float(r.get('cfps')), safe_float(r.get('roe')),
                safe_float(r.get('roa')),
            ))
        self._execute_many(sql, data)


# ================= 爬取逻辑类 =================
class ShanghaiStockCrawler:
    """沪市个股数据爬取器"""

    def __init__(self, db: MySQLMarketData):
        self.db = db

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
        """获取单只股票日K线"""
        df = retry_with_backoff(
            ak.stock_zh_a_hist,
            symbol=symbol, period="daily",
            start_date=start_date, end_date=end_date,
            adjust="qfq"
        )
        if df is None or df.empty:
            return None
        return df

    def fetch_indicator(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取估值指标(PE/PB/市值)"""
        try:
            df = retry_with_backoff(ak.stock_a_indicator_lg, symbol=symbol)
            return df
        except Exception as e:
            logger.warning(f"获取估值指标失败 {symbol}: {e}")
            return None

    def crawl_stock_list(self):
        """爬取并保存股票列表"""
        stocks = self.fetch_stock_list()
        self.db.upsert_stock_list(stocks)
        return stocks

    def crawl_kline(self, stocks: List[Dict], incremental: bool = True):
        """爬取所有股票K线数据"""
        today = datetime.now().strftime('%Y%m%d')
        total = len(stocks)
        success = 0
        fail = 0

        for idx, stock in enumerate(stocks):
            symbol = stock['symbol']
            ts_code = stock['ts_code']

            try:
                # 确定起始日期
                start_date = DEFAULT_START_DATE
                if incremental:
                    latest = self.db.get_latest_k_date(ts_code)
                    if latest:
                        # 从最新日期的下一天开始
                        next_day = (datetime.strptime(latest, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y%m%d')
                        start_date = next_day

                if start_date > today:
                    continue  # 已是最新

                # 获取K线
                rate_limit()
                df_kline = self.fetch_kline(symbol, start_date, today)
                if df_kline is None or df_kline.empty:
                    continue

                # 获取估值指标
                df_ind = self.fetch_indicator(symbol)

                # 构建记录
                records = self._merge_kline_and_indicator(symbol, ts_code, df_kline, df_ind)
                if records:
                    self.db.insert_kline_batch(records)
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
                                    df_kline: pd.DataFrame, df_ind: Optional[pd.DataFrame]) -> List[Dict]:
        """合并K线和估值指标数据"""
        records = []

        # 构建估值指标字典 {日期字符串: {pe, pb, total_mv, ...}}
        ind_map = {}
        if df_ind is not None and not df_ind.empty:
            for _, row in df_ind.iterrows():
                d = date_to_str(row.get('trade_date'))
                if d:
                    ind_map[d] = {
                        'pe': safe_float(row.get('pe')),
                        'pb': safe_float(row.get('pb')),
                        'total_mv': safe_float(row.get('total_mv')),
                    }

        for _, row in df_kline.iterrows():
            trade_date = date_to_str(row.get('日期'))
            if not trade_date:
                continue

            close = safe_float(row.get('收盘'))
            pre_close = safe_float(row.get('昨收'))
            pct_chg = safe_float(row.get('涨跌幅'))

            # 计算对数收益率
            ln_pctchg = None
            if close and pre_close and close > 0 and pre_close > 0:
                try:
                    ln_pctchg = round(math.log(close / pre_close), 6)
                except (ValueError, ZeroDivisionError):
                    pass

            # 从估值指标中获取 PE/PB/市值
            ind = ind_map.get(trade_date, {})

            records.append({
                'trade_date': trade_date,
                'symbol': symbol,
                'ts_code': ts_code,
                'open': safe_float(row.get('开盘')),
                'close': close,
                'high': safe_float(row.get('最高')),
                'low': safe_float(row.get('最低')),
                'pre_close': pre_close,
                'change_data': safe_float(row.get('涨跌额')),
                'pct_chg': pct_chg,
                'volume': safe_float(row.get('成交量')),
                'amount': safe_float(row.get('成交额')),
                'pe': ind.get('pe'),
                'pb': ind.get('pb'),
                'total_mv': ind.get('total_mv'),
                'total_share': None,
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

            # akshare 返回 item/value 两列，转为字典
            info_map = {}
            for _, row in df.iterrows():
                key = safe_str(row.get('item', ''))
                val = safe_str(row.get('value', ''))
                if key:
                    info_map[key] = val

            ts_code = f"{symbol}.SH"

            # 解析上市日期
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
                'full_name': info_map.get('股票简称', ''),  # 该接口无公司全称，用简称代替
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
                    self.db.upsert_company_info(info)
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

            # 增量：只取新报告期
            latest_date = None
            if incremental:
                latest_date = self.db.get_latest_fin_date(ts_code)

            records = []
            for _, row in df.iterrows():
                report_date = date_to_str(row.get('日期'))
                if not report_date:
                    continue
                if latest_date and report_date <= latest_date:
                    continue

                # 推断报告类型
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
                    self.db.upsert_financial_data(records)
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

    with MySQLMarketData(DB_CONFIG) as db:
        db.init_tables()
        crawler = ShanghaiStockCrawler(db)

        if args.mode == 'full':
            crawler.run_full_crawl()
        elif args.mode == 'daily':
            crawler.run_daily_update()
        elif args.mode == 'kline':
            stocks = crawler.crawl_stock_list()
            crawler.crawl_kline(stocks, incremental=True)
        elif args.mode == 'company':
            stocks = crawler.crawl_stock_list()
            crawler.crawl_company_info(stocks)
        elif args.mode == 'financial':
            stocks = crawler.crawl_stock_list()
            crawler.crawl_financial(stocks, incremental=True)

    logger.info("任务结束")


if __name__ == '__main__':
    main()
