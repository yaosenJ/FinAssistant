# !/usr/bin/python3
# -*- coding: utf-8 -*-
from query_concept_dc_day import get_concept_market_data,get_top_concepts
from query_concept_dc_stock import get_concept_stocks,get_stock_concepts
from query_fin_account import query_financial_data
from query_industry_component_list import get_industry_stocks,get_stock_industries
from query_industry_index_market import get_industry_by_stock,get_stocks_by_industry
from query_market_data_day_k import query_stock_market_data

if __name__ == "__main__":
    from langchain.tools import tool
    from langchain_community.chat_models.tongyi import ChatTongyi
    from langchain.agents import initialize_agent, AgentType
    import mysql.connector

    chatLLM = ChatTongyi(
        model="qwen-max",
        temperature=0,
        api_key="sk-064b2c7a65b9478")
    tools = [get_concept_market_data, get_top_concepts, get_concept_stocks, get_stock_concepts, query_financial_data, get_industry_stocks, get_stock_industries, get_industry_by_stock, get_stocks_by_industry,query_stock_market_data ]
    agent = initialize_agent(tools, chatLLM, agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                             verbose=True)
    # agent.run("贵州茅台最近5个交易日数据")
    # agent.run("贵州茅台最近5个交易日数据中的收盘价")
    # agent.run("贵州茅台股票最近能不能买")
    # agent.run("平安银行股票最近能不能买")
    # agent.run("沙河股份最近能不能买")
    agent.run("招商银行所属行业是什么？")

