#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL 数据库连接工具
"""

import pymysql

DB_CONFIG = {
    'host': 'rm-2ze5t97h00ik9az147o.mysql.rds.aliyuncs.com',
    'user': 'root',
    'password': 'root@101',
    'database': 'market_data',
    'charset': 'utf8mb4',
}


def get_connection():
    """获取 MySQL 连接"""
    return pymysql.connect(**DB_CONFIG)
