#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL 数据库连接工具
"""

import pymysql

try:
    from tools.local_config import DB_CONFIG
except ImportError:
    from local_config import DB_CONFIG


def get_connection():
    """获取 MySQL 连接"""
    return pymysql.connect(**DB_CONFIG)
