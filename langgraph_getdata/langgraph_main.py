# !/usr/bin/python3
# -*- coding: utf-8 -*-
import json
from typing import Literal
from query_concept_dc_day import get_concept_market_data, get_top_concepts
from query_concept_dc_stock import get_concept_stocks, get_stock_concepts
from query_fin_account import query_financial_data
from query_industry_component_list import get_industry_stocks, get_stock_industries
from query_industry_index_market import get_industry_by_stock, get_stocks_by_industry
from query_market_data_day_k import query_stock_market_data
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import ToolMessage


# 定义状态类型
class State(TypedDict):
    messages: Annotated[list, add_messages]


# 初始化模型和工具
chat_model = ChatTongyi(
    model="qwen-max",
    temperature=0,
    api_key="sk-064b2c7a65b"
)

tools = [get_concept_market_data, get_top_concepts, get_concept_stocks, get_stock_concepts,
         query_financial_data, get_industry_stocks, get_stock_industries, get_industry_by_stock,
         get_stocks_by_industry, query_stock_market_data]

# 构建状态图
graph_builder = StateGraph(State)
llm_with_tools = chat_model.bind_tools(tools)


def chatbot(state: State):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}


graph_builder.add_node("chatbot", chatbot)


class BasicToolNode:
    def __init__(self, tools: list) -> None:
        self.tools_by_name = {tool.name: tool for tool in tools}

    def __call__(self, inputs: dict):
        if messages := inputs.get("messages", []):
            message = messages[-1]
        else:
            raise ValueError("输入中未找到消息")

        outputs = []
        for tool_call in message.tool_calls:
            tool_result = self.tools_by_name[tool_call["name"]].invoke(tool_call["args"])
            outputs.append(
                ToolMessage(
                    content=json.dumps(tool_result),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )
        return {"messages": outputs}


tool_node = BasicToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)


def route_tools(state: State) -> Literal["tools", "__end__"]:
    if isinstance(state, list):
        ai_message = state[-1]
    elif messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"输入状态中未找到消息: {state}")

    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tools"
    return "__end__"


graph_builder.add_conditional_edges(
    "chatbot",
    route_tools,
    {"tools": "tools", "__end__": "__end__"},
)

graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)
graph = graph_builder.compile()


def get_model_response(query: str) -> str:
    """
    处理用户查询并返回模型的最终回复
    :param query: 用户输入的查询字符串
    :return: 模型的最终回复字符串
    """
    # 初始化对话状态
    initial_state = {"messages": [("user", query)]}

    # 执行对话流程
    final_state = graph.invoke(initial_state)

    # 提取最后一个AI生成的回复
    for msg in reversed(final_state["messages"]):
        if msg.type == "ai":
            return msg.content
    return "未能生成有效回复"


# 使用示例
if __name__ == "__main__":
    test_query = "帮我分析下最近的新能源板块走势"
    print("用户提问:", test_query)
    print("模型回复:", get_model_response(test_query))