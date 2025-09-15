# !/usr/bin/python3
# -*- coding: utf-8 -*-
import pymysql
import dashscope
import json
import hashlib
from datetime import datetime

from openai import OpenAI
from tqdm import tqdm
from typing import List, Dict

# ================= 配置信息 =================
DB_CONFIG = {
    'host': '192.168.1.101',
    'port': 13306,
    'user': 'news_user',
    'password': 'km101',
    'database': 'stock_news'
}

mysql_config = {
    'host': '192.168.1.101',
    'port': 13306,
    'user': 'news_user',
    'password': 'km101',
    'database': 'market_data'
}

Y_DB_CONFIG = {
    'host': 'rm-bp1o58d170qizfa',
    'port': 3306,
    'user': 'kmzn',
    'password': 'pjBL!3TqkyBvTF7',
    'database': 'stock_news'
}




DASHSCOPE_API_KEY = 'sk-48d14c2089104d'

# 连接到MySQL数据库
def connect_mysql():
    try:
        conn = pymysql.connect(**mysql_config)
        print("成功连接到MySQL数据库")
        return conn
    except Exception as e:
        print(f"连接MySQL数据库失败: {e}")
        return None

# 从MySQL获取概念名称
def get_concept_names(conn):
    concept_names = []
    try:
        with conn.cursor() as cursor:
            sql = "SELECT DISTINCT concept_name FROM concept_dc_list WHERE concept_name IS NOT NULL"
            cursor.execute(sql)
            results = cursor.fetchall()
            for row in results:
                concept_names.append(row[0])
        print(f"从MySQL获取了 {len(concept_names)} 个概念名称")
    except Exception as e:
        print(f"获取概念名称失败: {e}")
    return concept_names

# 从MySQL获取公司名称
def get_company_names(conn):
    company_names = []
    try:
        with conn.cursor() as cursor:
            sql = "SELECT DISTINCT company_name FROM concept_dc_stock WHERE company_name IS NOT NULL"
            cursor.execute(sql)
            results = cursor.fetchall()
            for row in results:
                company_names.append(row[0])
        print(f"从MySQL获取了 {len(company_names)} 个公司名称")
    except Exception as e:
        print(f"获取概念名称失败: {e}")
    return company_names

# 从MySQL获取行业名称
def get_industry_names(conn):
    industry_names = []
    try:
        with conn.cursor() as cursor:
            sql = "SELECT DISTINCT industry_name FROM industry_component_list WHERE industry_name IS NOT NULL"
            cursor.execute(sql)
            results = cursor.fetchall()
            for row in results:
                industry_names.append(row[0])
        print(f"从MySQL获取了 {len(industry_names)} 个行业名称")
    except Exception as e:
        print(f"获取行业名称失败: {e}")
    return industry_names

mysql_conn = connect_mysql()

industries = get_industry_names(mysql_conn)

companies = get_company_names(mysql_conn)

concepts = get_concept_names(mysql_conn)


# ================= 数据库操作类 =================
class MySQLConnector:
    def __init__(self, config):
        self.config = config
        self.connection = None

    def __enter__(self):
        self.connection = pymysql.connect(**self.config)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()

    def fetch_news(self, batch_size=500) -> List[Dict]:
        """批量获取2025年待处理新闻（排除已处理过的）"""
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
            SELECT
                dn.id,
                DATE_FORMAT(dn.trade_date, '%%Y-%%m-%%d %%H:%%i:%%S') as trade_date,
                dn.title,
                dn.content,
                dn.channels,
                dn.source
            FROM daily_news dn
            LEFT JOIN new_processed_daily_news pdn ON dn.id = pdn.news_id
            WHERE
                dn.trade_date >= '2025-04-02'
                AND dn.trade_date < '2025-12-31'
                AND pdn.news_id IS NULL  -- 只选择未处理的记录
            LIMIT %s
            """
            cursor.execute(sql, (batch_size,))
            return cursor.fetchall()

    def init_processed_news_table(self):
        with self.connection.cursor() as cursor:
            sql = """
            CREATE TABLE IF NOT EXISTS new_processed_daily_news (
                id INT AUTO_INCREMENT PRIMARY KEY,
                news_id INT,
                trade_date DATETIME,
                title VARCHAR(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                content VARCHAR(1024) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                channels VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                source VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                stock_name VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                stock_confidence FLOAT,
                industry_name VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                industry_confidence FLOAT,
                concept_name VARCHAR(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,  -- 新增字段
                concept_confidence FLOAT,                                                   -- 新增字段
                raw_response TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_news_id (news_id),
                INDEX idx_stock_name (stock_name),
                INDEX idx_industry_name (industry_name),
                INDEX idx_concept_name (concept_name)                                       -- 新增索引
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(sql)
            self.connection.commit()

    def save_entity(self, data: Dict):
        """保存识别结果到MySQL，同时写入本地和远程数据库"""
        # 本地数据库连接
        with self.connection.cursor() as cursor:
            sql = """
            INSERT INTO new_processed_daily_news (
                news_id, trade_date, title, content,
                channels, source, stock_name, stock_confidence,
                industry_name, industry_confidence, concept_name, concept_confidence, raw_response
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            try:
                # 插入本地数据库
                cursor.execute(sql, (
                    data['news_id'],
                    data['trade_date'],
                    data['title'][:128].encode('utf-8', 'ignore').decode('utf-8'),
                    data['content'][:1024].encode('utf-8', 'ignore').decode('utf-8'),
                    data.get('channels', ''),
                    data.get('source', ''),
                    data.get('stock_name', ''),
                    data.get('stock_confidence', 0.0),
                    data.get('industry_name', ''),
                    data.get('industry_confidence', 0.0),
                    data.get('concept_name', ''),
                    data.get('concept_confidence', 0.0),
                    data.get('raw_response', '')
                ))
                self.connection.commit()
                
                # 插入远程数据库
                y_conn = pymysql.connect(**Y_DB_CONFIG)
                with y_conn.cursor() as y_cursor:
                    y_cursor.execute(sql, (
                        data['news_id'],
                        data['trade_date'],
                        data['title'][:128].encode('utf-8', 'ignore').decode('utf-8'),
                        data['content'][:1024].encode('utf-8', 'ignore').decode('utf-8'),
                        data.get('channels', ''),
                        data.get('source', ''),
                        data.get('stock_name', ''),
                        data.get('stock_confidence', 0.0),
                        data.get('industry_name', ''),
                        data.get('industry_confidence', 0.0),
                        data.get('concept_name', ''),
                        data.get('concept_confidence', 0.0),
                        data.get('raw_response', '')
                    ))
                    y_conn.commit()
                y_conn.close()
                
            except Exception as e:
                print(f"插入失败 ID:{data['news_id']} - {str(e)}")

# ================= 实体识别服务 =================
class EntityRecognizer:
    def __init__(self):
        dashscope.api_key = DASHSCOPE_API_KEY

    def extract_entities(self, text: str) -> Dict:
        """
        同时识别股票、行业和概念实体
        返回结构示例：
        {
            "stock": {"name": "...", "confidence": 0.95},
            "industry": {"name": "...", "confidence": 0.88},
            "concept": {"name": "...", "confidence": 0.90}
        }
        """
        prompt = f"""
        请从以下分析文本中准确识别对应的：
        1. 股票名称（只从以下列表选择）：{companies}
        2. 行业名称（只从以下列表选择）：{industries}
        3. 概念名称（只从以下列表选择）：{concepts}

        返回严格JSON格式：
        {{
            "stock": {{
                "name": "股票名称（没有则空字符串）",
                "confidence": 0.0-1.0
            }},
            "industry": {{
                "name": "行业名称（没有则空字符串）",
                "confidence": 0.0-1.0
            }},
            "concept": {{
                "name": "概念名称（没有则空字符串）",
                "confidence": 0.0-1.0
            }}
        }}

        分析文本：{text[:3000]}
        """

        try:
            client = OpenAI(
                api_key=DASHSCOPE_API_KEY,
                base_url="http://192.168.1.119:8004/v1"
            )
            response = client.chat.completions.create(
                model="Qwen2.5-7B-Instruct",
                messages=[
                    {'role': 'system', 'content': '你是一个专业的金融信息抽取助手，严格按要求返回JSON格式数据'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0,
                max_tokens=200
            )

            result = json.loads(response.choices[0].message.content.strip('```json').strip('```').strip())
            # 重新序列化为不转义中文的JSON字符串
            formatted_raw_response = json.dumps(result, ensure_ascii=False, indent=4)
            return {
                'stock_name': result['stock']['name'].strip(),
                'stock_confidence': float(result['stock']['confidence']),
                'industry_name': result['industry']['name'].strip(),
                'industry_confidence': float(result['industry']['confidence']),
                'concept_name': result['concept']['name'].strip(),  # 新增字段
                'concept_confidence': float(result['concept']['confidence']),  # 新增字段
                'raw_response': formatted_raw_response
            }
        except Exception as e:
            print(f"实体解析失败: {str(e)}")
            return self._default_response()

    def _default_response(self):
        """默认返回值（新增概念字段）"""
        return {
            'stock_name': '',
            'stock_confidence': 0.0,
            'industry_name': '',
            'industry_confidence': 0.0,
            'concept_name': '',  # 新增字段
            'concept_confidence': 0.0,  # 新增字段
            'raw_response': json.dumps({})
        }
# ================= 主流程 =================
def process_news_batch():
    recognizer = EntityRecognizer()

    with MySQLConnector(DB_CONFIG) as mysql:
        # 初始化处理结果表
        mysql.init_processed_news_table()

        while True:
            news_items = mysql.fetch_news()
            if not news_items:
                print("没有待处理数据")
                break

            for item in tqdm(news_items, desc="处理进度"):
                try:
                    # 实体抽取
                    combined_text = f"{item['title']}\n{item['content']}"
                    entities = recognizer.extract_entities(combined_text)

                    # 构建存储数据
                    record = {
                        'news_id': item['id'],
                        'trade_date': item['trade_date'],
                        'title': item['title'][:128],
                        'content': item['content'][:1024],
                        'channels': item.get('channels', ''),
                        'source': item.get('source', ''),
                        **entities
                    }

                    # 存入MySQL
                    mysql.save_entity(record)
                except Exception as e:
                    print(f"处理失败 ID:{item['id']} - {str(e)}")

            print(f"本批次完成: {len(news_items)}条")

if __name__ == "__main__":

    mysql_conn = connect_mysql()
    industries = get_industry_names(mysql_conn)
    companies = get_company_names(mysql_conn)
    concepts = get_concept_names(mysql_conn)
    print(f"加载行业数量: {len(industries)}")
    print(f"加载公司数量: {len(companies)}")
    print(f"加载概念数量: {len(concepts)}")

    process_news_batch()
    print("处理完成！结果已保存到MySQL数据库")