from typing import List, Dict, Any
import pymysql

class MySQLClient:
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.conn = pymysql.connect(host=host, port=port, user=user, password=password, database=database, charset='utf8mb4')

    def fetch_news(self, query: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        sql = """
        SELECT id, DATE_FORMAT(trade_date, '%Y-%m-%d') as trade_date, title, content, source
        FROM daily_news
        WHERE (title LIKE %s OR content LIKE %s)
        ORDER BY trade_date DESC
        LIMIT %s
        """
        kw = f"%{query}%"
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, (kw, kw, limit))
            return cur.fetchall()
