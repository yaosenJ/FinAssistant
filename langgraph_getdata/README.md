## 基于langgraph实现数据调度agent
### 工具如下：
**get_concept_market_data**, **get_top_concepts**, **get_concept_stocks**, 
**get_stock_concepts**, **query_financial_data**, **get_industry_stocks**, 
**get_stock_industries**, **get_industry_by_stock**, **get_stocks_by_industry**,
**query_stock_market_data**

具体的工具功能请查看对应的代码，每一个python都支持单独测试（基于langchain实现），日志可以查询对应的日志
数据调度Agent详细内部运行过程，见**[数据调度Agent过程详细解读.pdf](./数据调度Agent过程详细解读.pdf)**

- langchain_main.py: 基于langchain实现的数据调度agent
- langgraph_main_new.py: 基于langgraph实现得到数据调度agent,并实现tool工具调用的结果存在图中的state中
- langchain_main_old.py: 基于langgraph实现得到数据调度agent,输入query，返回需要的数据
