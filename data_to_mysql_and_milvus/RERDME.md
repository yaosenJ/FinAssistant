### new_processed_daily_news.py
- 批量获取指定时间范围的待处理新闻（排除已处理过的）
- 识别主体（个股、行业和概念名称），并存到mysql库中

在下面的**fetch_news**函数，指定**dn.trade_date**和**dn.trade_date**即可完成该时间范围且未处理过的数据
```python
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
```

### text_embedding_to_milvus.py
- 批量获取指定时间范围的待处理新闻（排除已处理过的）
- title和content合并进行向量化以及连同trade_date存到milvus库中

在下面的代码中，指定**start_date**和**end_date**即可完成该时间范围且未处理过的数据

```python
 system.load_data(
        start_date="2025-04-1 00:00:00",
        end_date="2028-04-11 23:59:59"
    )
```

