#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 DrissionPage (Chrome) 爬取同花顺板块成分股（仅代码+名称）
数据源: 同花顺 (THS)，与板块行情数据统一

用法:
    python crawl_sector_cons_ths.py industry    # 只爬行业板块
    python crawl_sector_cons_ths.py concept     # 只爬概念板块
    python crawl_sector_cons_ths.py all         # 全部
"""

import json
import os
import sys
import time
import random
import logging
import re

import akshare as ak

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'sector')
LOG_DIR = os.path.join(SCRIPT_DIR, '..', 'log')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'crawl_sector_cons_ths.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

REQUEST_DELAY = (1.5, 3.0)
PAGE_DELAY = (2.5, 4.0)
BATCH_PAUSE_SIZE = 15
BATCH_PAUSE_DELAY = (8, 15)
MAX_PAGE_RETRIES = 3
RESTART_BROWSER_EVERY = 15  # 每15个板块重启浏览器


def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_stocks_from_html(html):
    """从THS页面HTML中提取tbody里的股票代码和名称"""
    tbody = re.search(r'<tbody>(.*?)</tbody>', html, re.DOTALL)
    if not tbody:
        return []
    stocks = re.findall(
        r'<a href="http://stockpage\.10jqka\.com\.cn/(\d+)/?"[^>]*>(.*?)</a>',
        tbody.group(1)
    )
    seen = set()
    result = []
    for code, name in stocks:
        if code not in seen and not name.strip().isdigit():
            seen.add(code)
            result.append({'code': code, 'name': name.strip()})
    return result


def get_total_pages(page_obj):
    """获取分页显示的总页数"""
    pager = page_obj.ele('css:.m-pager')
    if not pager:
        return 1
    text = pager.text
    match = re.search(r'(\d+)/(\d+)', text)
    return int(match.group(2)) if match else 1


def crawl_sector_stocks(page, sector_name, sector_code, board_type):
    """爬取单个板块的全部成分股（仅代码+名称）"""
    url = f'https://q.10jqka.com.cn/{board_type}/detail/code/{sector_code}/'
    page.get(url)
    time.sleep(random.uniform(*REQUEST_DELAY))

    all_stocks = []
    total_pages = get_total_pages(page)

    for page_num in range(1, total_pages + 1):
        if page_num > 1:
            try:
                btn = page.ele(f'css:a[page="{page_num}"]')
                if btn:
                    btn.click()
                    time.sleep(random.uniform(*PAGE_DELAY))
                else:
                    break
            except Exception as e:
                logger.warning(f"{sector_name} 第{page_num}页点击失败: {e}")
                break

        stocks = extract_stocks_from_html(page.html)

        # 如果某页为空，重试几次
        if not stocks and page_num < total_pages:
            for retry in range(MAX_PAGE_RETRIES):
                time.sleep(random.uniform(3, 5))
                stocks = extract_stocks_from_html(page.html)
                if stocks:
                    break
                # 重新点击该页
                try:
                    btn = page.ele(f'css:a[page="{page_num}"]')
                    if btn:
                        btn.click()
                        time.sleep(random.uniform(*PAGE_DELAY))
                except Exception:
                    pass

        if stocks:
            all_stocks.extend(stocks)
        else:
            # 连续空页则停止
            break

    # 去重
    seen = set()
    unique = []
    for s in all_stocks:
        if s['code'] not in seen:
            seen.add(s['code'])
            unique.append(s)

    return unique


def create_browser():
    """创建新的浏览器实例"""
    from DrissionPage import ChromiumOptions, ChromiumPage
    co = ChromiumOptions()
    co.headless(True)
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    return ChromiumPage(co)


def crawl_sector_list(sector_list, board_type, output_file):
    """通用板块成分股爬取，自动重启浏览器"""
    all_data = []
    total = len(sector_list)
    page = create_browser()

    for idx, sector in enumerate(sector_list):
        # 定期重启浏览器
        if idx > 0 and idx % RESTART_BROWSER_EVERY == 0:
            page.quit()
            delay = random.uniform(*BATCH_PAUSE_DELAY)
            logger.info(f"--- 重启浏览器，暂停{delay:.1f}秒 ---")
            time.sleep(delay)
            page = create_browser()

        try:
            stocks = crawl_sector_stocks(page, sector['name'], sector['code'], board_type)
            info = {
                'name': sector['name'],
                'code': sector['code'],
                'stock_count': len(stocks),
                'stocks': stocks,
            }
            all_data.append(info)
            logger.info(f"[{idx+1}/{total}] {sector['name']}: {len(stocks)} 只成分股")

            # 连续多个板块返回0，提前重启浏览器
            if len(stocks) == 0 and idx > 0 and all_data[-2]['stock_count'] == 0:
                logger.warning("连续空结果，提前重启浏览器")
                page.quit()
                time.sleep(random.uniform(5, 10))
                page = create_browser()

        except Exception as e:
            logger.error(f"[{idx+1}/{total}] {sector['name']} 失败: {e}")

        if (idx + 1) % BATCH_PAUSE_SIZE == 0:
            delay = random.uniform(*BATCH_PAUSE_DELAY)
            logger.info(f"--- 已处理{idx+1}个，暂停{delay:.1f}秒 ---")
            time.sleep(delay)

    page.quit()
    save_json(os.path.join(DATA_DIR, output_file), all_data)
    logger.info(f"完成: {len(all_data)} 个板块，保存到 {output_file}")


def load_industry_list():
    """从已有数据文件加载行业板块列表"""
    filepath = os.path.join(DATA_DIR, 'industry_sectors.json')
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [{'name': d['industry_name'], 'code': d['industry_ts_code']} for d in data]
    # 如果没有缓存，尝试从akshare获取
    sectors = ak.stock_board_industry_name_ths()
    return [{'name': str(row['name']).strip(), 'code': str(row['code']).strip()} for _, row in sectors.iterrows()]


def load_concept_list():
    """从已有数据文件加载概念板块列表"""
    filepath = os.path.join(DATA_DIR, 'concept_sectors.json')
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [{'name': d['concept_name'], 'code': d['concept_ts_code']} for d in data]
    # 如果没有缓存，尝试从akshare获取
    sectors = ak.stock_board_concept_name_ths()
    return [{'name': str(row['name']).strip(), 'code': str(row['code']).strip()} for _, row in sectors.iterrows()]


def crawl_all_industry():
    """爬取全部行业板块成分股"""
    logger.info("加载行业板块列表...")
    sector_list = load_industry_list()
    logger.info(f"行业板块: {len(sector_list)} 个")
    crawl_sector_list(sector_list, 'thshy', 'industry_cons.json')


def crawl_all_concept():
    """爬取全部概念板块成分股"""
    logger.info("加载概念板块列表...")
    sector_list = load_concept_list()
    logger.info(f"概念板块: {len(sector_list)} 个")
    crawl_sector_list(sector_list, 'gn', 'concept_cons.json')


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if target not in ('industry', 'concept', 'all'):
        print("用法: python crawl_sector_cons_ths.py [industry|concept|all]")
        sys.exit(1)

    if target in ('industry', 'all'):
        crawl_all_industry()
    if target in ('concept', 'all'):
        crawl_all_concept()

    logger.info("全部完成!")


if __name__ == '__main__':
    main()
