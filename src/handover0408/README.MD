### 目录说明
1. **data**  
   - `concepts.json`: 所有概念名称数据
   - `industries.json`: 所有行业名称数据
   - `stocks.json`: 所有个股名称数据
   - `test.txt`: 测试问题数据集
   - `time.csv`: 股票交易日日期
2. **img**  
   - 问题和检索文本块相似度分布情况
3. **log**  
   - 相关代码运行日志
4. **src**  
   - `ask_service.py`: Python 客户端，用于调用本地部署的行业摘要生成服务。
   - `config.yaml`: milvus、mysql、qwen相关配置
   - `database.py`: 基于交易日历计算日期范围，从MySQL数据库获取指定个股/行业/概念的新闻数据的工具
   - `evaluate_similarity_distribution.py`: 评估文本相似度分布情况
   - `generate_concepts.py`: 获取所用概念名称存入到**concepts.json**中
   - `generate_industries.py`: 获取所用行业名称存入到**industries.json**中
   - `generate_stocks.py`: 获取所用个股名称存入到**stocks.json**中
   - `llm.py`: 提供基于自然语言的金融信息查询服务，支持股票、行业、概念三类信息的智能识别与检索。
   - `main.py`: 主函数，获取对应相似的文本块以及基于这些文本块生成摘要
   - `ner_to_mysql_use_local_model.py`: 使用本地部署的**Qwen2.5-7B-Instruct**进行主体识别及入mysql库
   - `rag_consine_date.py`: 基于余弦相似度算法，召回相似文本块
   - `service_api.py`: 基于**FastAPI**构建的行业分析摘要生成服务，支持通过自然语言查询生成行业报告摘要。
   - `summary_generation.py`: 基于详细版的提示词工程，整合多路召回（**milvus**和**mysql**）文本的整合，然后生成对应的简报
   - `summary_generation2.py`: 基于简约版的提示词工程，整合多路召回（**milvus**和**mysql**）文本的整合，然后生成对应的简报
  

### 关键文件说明

#### llm.py

##### 金融信息智能查询系统

本系统提供基于自然语言的金融信息查询服务，支持股票、行业、概念三类信息的智能识别与检索。

##### 主要功能

1. **智能意图识别**  
   - 自动判断用户查询类型（股票/行业/概念）
   - 示例：
     ```python
     detect_query_intent("宁德时代有什么新消息")  # 返回 ('stock', '宁德时代')
     ```

2. **实体标准化**  
   - 使用模糊匹配技术校正用户输入
   - 支持：
     - 股票列表：从`stocks.json`加载
     - 行业列表：从`industries.json`加载 
     - 概念列表：从`concepts.json`加载

3. **mysql数据检索**  
   - 股票信息：查询最近10天新闻
   - 行业/概念：查询最近30天动态
   - 数据库配置：
     ```python
     db_config = {
         'host': '192.168.1.101',
         'port': 13306,
         'user': 'news_user',
         'password': 'km101',
         'database': 'stock_news'
     }
     ```

4. **大模型集成**  
   - 使用QWen大模型进行语义理解
   - 支持函数调用：
     ```python
     get_company_report_info_from_stock(stock_name)
     get_company_report_info_from_industry(industry_name)
     ```

###### 快速使用

```python
# 示例查询
result = process_request("DeepSeek概念最近动态")
print(result)  # 返回相关概念的最新资讯
```

#### service_api.py

请求参数

字段	类型	必填	说明

**query**	string	是	分析查询语句（示例："新能源汽车行业未来5年发展趋势"）


#### ask_service.py
##### 输入
```json
{
    "query": "新能源汽车行业未来5年的发展前景如何？",
}
```
##### 成功响应

```json
 {'summary_content': '新能源汽车行业未来5年的发展前景分析如下：\n\n1. **市场需求旺盛**：根据宁德时代的业绩说明会，当前市场需求旺盛，公司产能利用率处于饱和状态。这表明全球范围内对新能源汽车电池的需求持续增长。\n\n2. **销量增长显著**：比亚迪和吉利等国内主要车企在2025年第一季度的新能源汽车销量表现强劲。其中，比亚迪3月的新能源汽车销量继续攀升，而吉利控股集团第一季度总销量中新能源汽车占比也有所提升，同比增长31%。\n\n3. **新产品推出频繁**：法拉第未来计划年底推出首款FX车型，比亚迪腾势N9车型也将于近期上市。这些新产品的推出将进一步丰富市场选择，推动行业技术进步和市场竞争。\n\n4. **政策支持与国际化趋势**：张兴海委员提出，新能源汽车产业需要通过持续创新走向国际化。中国作为新能源汽车的核心领导者，在国内外政策环境变化的情况下，仍需保持领先地位并拓展国际市场。\n\n5. **市场结构变化**：乘联分会数据显示，新能源汽车已成为中国乘用车市场的核心增长主力。尽管燃油车市场走势较弱，但新能源汽车零售和批发量均呈现显著增长，累计零售和批发量分别同比增长35%和超过30%。\n\n综上所述，未来5年新能源汽车行业将继续受益于市场需求的增长、技术创新以及政策支持。随着更多新车型的推出和国际市场的拓展，行业有望实现更快速的发展。同时，产业链上下游企业如宁德时代等也将持续受益于行业的高景气度。'}
```

#### rag_consine_date.py

检索召回核心代码
- 支持指定最近交易日期范围，只需要在**search_news**函数中传入时间范围天数即可
- 相似度阈值设置为0.4，返回top20

```python
 def search_news(self, query: str, days: int = None) -> List[Dict]:
     _, target_end = get_dynamic_dates(self.search_days)
     end_dt = datetime.strptime(target_end, "%Y-%m-%d %H:%M:%S")

     if days is not None:
         start_date = TRADE_CALENDAR.get_n_days_back(end_dt.date(), days)
         # 修复：将date转换为datetime
         start_dt = datetime.combine(start_date, datetime.min.time())
         start_ts = int(start_dt.timestamp() * 1000)
     else:
         start_ts = int(end_dt.timestamp() * 1000 - 365 * 24 * 3600 * 1000)

     end_ts = int(end_dt.timestamp() * 1000)
     time_filter = f"trade_date >= {start_ts} && trade_date <= {end_ts}"

     query_embedding = self.embedding.get_embedding(query)
     if not query_embedding:
         return []

     semantic_results = self.vector_db.search_news(query_embedding, time_filter)
     # Filter results with score >= 0.4
     filtered_results = [res for res in semantic_results if res['score'] >= 0.4]
     # Sort by score in descending order and take top 10
     return sorted(filtered_results, key=lambda x: x['score'], reverse=True)[:20]
```