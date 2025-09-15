# !/usr/bin/python3
# -*- coding: utf-8 -*-

# !/usr/bin/python3
# -*- coding: utf-8 -*-

from database import get_company_news_from_stock, get_company_news_from_industry, get_company_news_from_concept


def get_company_report_info_from_stock(stock):
    """根据公司股票名称查询股票新闻信息"""
    db_config = {
        'host': '192.168.1.101',
        'port': 13306,
        'user': 'news_user',
        'password': 'km101',
        'database': 'stock_news'
    }
    return get_company_news_from_stock(stock, db_config, days_ago=10)


def get_company_report_info_from_industry(industry):
    """根据行业名称查询行业新闻信息"""
    db_config = {
        'host': '192.168.1.101',
        'port': 13306,
        'user': 'news_user',
        'password': 'km101',
        'database': 'stock_news'
    }
    return get_company_news_from_industry(industry, db_config, days_ago=30)


def get_company_report_info_from_concept(concept):
    """根据行业名称查询概念新闻信息"""
    db_config = {
        'host': '192.168.1.101',
        'port': 13306,
        'user': 'news_user',
        'password': 'km101',
        'database': 'stock_news'
    }
    return get_company_news_from_concept(concept, db_config, days_ago=30)