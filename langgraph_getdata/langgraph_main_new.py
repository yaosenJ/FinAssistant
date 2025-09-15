#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import operator
from typing import Literal, Dict, Any, List
from query_concept_dc_day import get_concept_market_data, get_top_concepts
from query_concept_dc_stock import get_concept_stocks, get_stock_concepts
from query_fin_account import query_financial_data
from query_industry_component_list import get_industry_stocks, get_stock_industries
from query_industry_index_market import get_industry_by_stock, get_stocks_by_industry
from query_market_data_day_k import query_stock_market_data
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import ToolMessage, HumanMessage, SystemMessage

def merge_dicts(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并字典"""
    for k, v in new.items():
        if isinstance(v, dict) and k in old:
            old[k] = merge_dicts(old[k], v)
        else:
            old[k] = v
    return old

class AgentState(TypedDict):
    messages: Annotated[List, operator.add]
    status: str
    other: Annotated[Dict[str, Any], merge_dicts]

chat_model = ChatTongyi(
    model="qwen-max",
    temperature=0,
    api_key=" "
)

tools = [get_concept_market_data, get_top_concepts, get_concept_stocks, get_stock_concepts,
         query_financial_data, get_industry_stocks, get_stock_industries, get_industry_by_stock,
         get_stocks_by_industry, query_stock_market_data]

graph_builder = StateGraph(AgentState)
llm_with_tools = chat_model.bind_tools(tools)

def chatbot(state: AgentState):
    ai_message = llm_with_tools.invoke(state["messages"])
    return {
        "messages": [ai_message],
        "status": "awaiting_tools",
        "other": state["other"]
    }

class EnhancedToolNode:
    def __init__(self, tools: list) -> None:
        self.tools_by_name = {tool.name: tool for tool in tools}

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        tool_results = {}
        messages = state["messages"]
        existing_tool_results = state["other"].get("tool_results", {}).copy()
        new_messages = []  # 用于收集新增的ToolMessage

        if messages and (ai_message := next(
                (msg for msg in reversed(messages) if hasattr(msg, 'tool_calls')), None)):
            for tool_call in ai_message.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_result = self.tools_by_name[tool_name].invoke(tool_args)
                # 合并工具结果
                if tool_name in existing_tool_results:
                    existing_tool_results[tool_name].append(tool_result)
                else:
                    existing_tool_results[tool_name] = [tool_result]
                # 创建新的ToolMessage并添加到new_messages
                tool_message = ToolMessage(
                    content=json.dumps(tool_result, ensure_ascii=False),
                    name=tool_name,
                    tool_call_id=tool_call["id"],
                )
                new_messages.append(tool_message)

        # 返回新增的ToolMessage，而不是整个消息列表
        return {
            "messages": new_messages,  # 只包含新增的消息
            "status": "tools_processed",
            "other": {**state["other"], "tool_results": existing_tool_results}
        }

tool_node = EnhancedToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)
# 在添加 tools 节点后，添加 chatbot 节点
graph_builder.add_node("chatbot", chatbot)

def route_tools(state: AgentState) -> Literal["tools", "__end__"]:
    if state["status"] == "awaiting_tools":
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
    return "__end__"

graph_builder.add_conditional_edges(
    "chatbot",
    route_tools,
    {"tools": "tools", "__end__": END},
)
graph_builder.add_edge("tools", "chatbot")
# graph_builder.add_edge("chatbot", END)
graph_builder.set_entry_point("chatbot")
graph = graph_builder.compile() # 增加递归限制

def initialize_state() -> AgentState:
    structure_info = """以下是结构化数据说明：
1. ie_data（信息提取数据）:
   - company: 公司名称列表（如：["金力永磁","火星人","三丰智能"]）
   - content: 主要分析点（如：["热点"]）
   - sectors: 板块名称（如：["人形机器人"]）
   - sectors_type: 板块类型（industry/concept）

2. reportdate_data（时间数据）:
   - market: 市场时间范围（start_date/end_date）
   - fin_account: 财报日期列表（如季度末日期）

3. tool_results: 工具调用结果（自动更新）"""

    initial_other = {
        "ie_data": {
            "company": ["金力永磁","火星人"],
            "content": ["热点", "资产负债表"],
            "sectors": ["人形机器人"],
            "sectors_type": "concept"
        },
        "reportdate_data": {
            "market": {"start_date": "2025-03-06", "end_date": "2025-04-06"},
            "fin_account": ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"]
        }
    }

    system_msg = SystemMessage(
        content=f"{structure_info}\n\n当前数据状态：\n{json.dumps(initial_other, indent=2, ensure_ascii=False)}"
    )
    return {
        "messages": [system_msg],
        "status": "start",
        "other": initial_other
    }

def get_model_response() -> dict:
    """获取模型回复及工具调用结果"""
    initial_state = initialize_state()
    final_state = graph.invoke(initial_state)
    # print(final_state["messages"])
    # 提取AI回复
    ai_response = "未能生成有效回复"
    for msg in reversed(final_state["messages"]):
        if msg.type == "ai":
            ai_response = msg.content
            break

    # 提取工具调用结果
    tool_results = final_state["other"].get("tool_results", {})

    return {
        "response": ai_response,
        "tool_results": tool_results
    }

if __name__ == "__main__":
    result = get_model_response()
    # print("\n模型回复:", result["response"])
    print("\n工具调用结果:")
    if result["tool_results"]:
        print(json.dumps(
            result["tool_results"],
            indent=2,
            ensure_ascii=False,  # 禁用ASCII转义
            default=str  # 处理非序列化对象
        ))
    else:
        print("本次调用未使用工具")



