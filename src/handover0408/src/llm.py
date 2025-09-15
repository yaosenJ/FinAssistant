# !/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import os
from typing import List, Tuple

import yaml
from fuzzywuzzy import fuzz
from openai import OpenAI
from database import get_company_news_from_stock, get_company_news_from_industry, get_company_news_from_concept

# 定义全局变量
LOCAL_COMPANIES = []
LOCAL_INDUSTRIES = []
LOCAL_CONCEPTS = []


def load_stocks_from_json(json_file: str = '../data/stocks.json') -> List[str]:
    """
    从JSON文件加载公司股票列表
    """
    global LOCAL_COMPANIES
    try:
        if not os.path.exists(json_file):
            raise FileNotFoundError(f"JSON文件不存在: {json_file}")

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'stocks' not in data:
            raise ValueError("JSON文件格式不正确，缺少'stocks'字段")

        LOCAL_COMPANIES = data['stocks']
        print(f"成功加载 {len(LOCAL_COMPANIES)} 家公司数据")
        return LOCAL_COMPANIES
    except Exception as e:
        print(f"加载公司数据失败: {str(e)}")
        return []


def load_industries_from_json(json_file: str = '../data/industries.json') -> List[str]:
    """
    从JSON文件加载行业列表
    """
    global LOCAL_INDUSTRIES
    try:
        if not os.path.exists(json_file):
            raise FileNotFoundError(f"JSON文件不存在: {json_file}")

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'industries' not in data:
            raise ValueError("JSON文件格式不正确，缺少'industries'字段")

        LOCAL_INDUSTRIES = data['industries']
        print(f"成功加载 {len(LOCAL_INDUSTRIES)} 行业数据")
        return LOCAL_INDUSTRIES
    except Exception as e:
        print(f"加载公司数据失败: {str(e)}")
        return []


def load_concepts_from_json(json_file: str = '../data/concepts.json') -> List[str]:
    """
    从JSON文件加载概念列表
    """
    global LOCAL_CONCEPTS
    try:
        if not os.path.exists(json_file):
            raise FileNotFoundError(f"JSON文件不存在: {json_file}")

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'concepts' not in data:
            raise ValueError("JSON文件格式不正确，缺少'concepts'字段")

        LOCAL_CONCEPTS = data['concepts']
        print(f"成功加载 {len(LOCAL_CONCEPTS)} 概念数据")
        return LOCAL_CONCEPTS
    except Exception as e:
        print(f"加载概念数据失败: {str(e)}")
        return []


def get_local_companies() -> List[str]:
    """获取本地存储的公司列表"""
    global LOCAL_COMPANIES
    return LOCAL_COMPANIES.copy()


def get_local_industries() -> List[str]:
    """获取本地存储的行业列表"""
    global LOCAL_INDUSTRIES
    return LOCAL_INDUSTRIES.copy()


def get_local_concepts() -> List[str]:
    """获取本地存储的概念列表"""
    global LOCAL_CONCEPTS
    return LOCAL_CONCEPTS.copy()


# 初始化数据
companies = load_stocks_from_json()
local_companies = get_local_companies()
industries = load_industries_from_json()
local_industries = get_local_industries()
concepts = load_concepts_from_json()
local_concepts = get_local_concepts()


# ================= 配置加载 =================
def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


config = load_config('config.yaml')

# 初始化Qwen客户端
client = OpenAI(
    api_key=config['qwen']['api_key'],
    base_url=config['qwen']['base_url']
)


def detect_query_intent(user_input: str) -> Tuple[str, str]:
    """
    识别用户查询意图是股票、行业还是概念

    返回:
        Tuple[str, str]: (intent_type, entity)
            intent_type: "stock" 或 "industry" 或 "concept"
            entity: 识别到的实体名称
    """
    messages = [
        {"role": "system", "content": "你是一个金融领域专家，需要判断用户是想查询股票信息、行业信息还是概念信息。"},
        {"role": "user",
         "content": f"请分析以下用户查询的意图是股票(stock)、行业(industry)还是概念(concept)，并识别出对应的实体名称。只返回JSON格式结果，不要有其他内容。文本：{user_input}"}
    ]

    response = client.chat.completions.create(
        model=config['qwen']['chat_model'],
        messages=messages,
        temperature=0,
        response_format={"type": "json_object"},
        max_tokens=60
    )

    try:
        result = json.loads(response.choices[0].message.content)
        return result.get("intent", ""), result.get("entity", "")
    except:
        return "", ""


# def recognize_entity(user_input: str, entity_type: str) -> str:
#     """识别用户输入中的实体（公司或行业）"""
#     if entity_type == "stock":
#         system_content = "你是一个金融领域专家，擅长从文本中识别公司股票名称。请只返回公司股票名称本身，不要有其他内容。"
#     else:
#         system_content = "你是一个金融领域专家，擅长从文本中识别行业名称。请只返回行业名称本身，不要有其他内容。"
#
#     messages = [
#         {"role": "system", "content": system_content},
#         {"role": "user",
#          "content": f"请从以下文本中识别提到的{'公司股票名称' if entity_type == 'stock' else '行业名称'}，只返回名称本身，不要有其他内容。文本：{user_input}"}
#     ]
#
#     response = client.chat.completions.create(
#         model="qwen-plus",
#         messages=messages,
#         temperature=0,
#         max_tokens=20
#     )
#
#     return response.choices[0].message.content.strip()

def recognize_entity(user_input: str, entity_type: str) -> str:
    """识别用户输入中的实体（公司、行业或概念）"""
    # 定义实体类型映射
    entity_map = {
        "stock": ("公司股票名称", "擅长从文本中识别公司股票名称"),
        "industry": ("行业名称", "擅长从文本中识别行业名称"),
        "concept": ("概念名称", "擅长从文本中识别概念名称")
    }

    # 验证实体类型有效性
    if entity_type not in entity_map:
        raise ValueError(f"无效的实体类型: {entity_type}，支持类型: stock/industry/concept")

    entity_name, ability_desc = entity_map[entity_type]

    # 构建系统提示
    system_content = f"你是一个金融领域专家，{ability_desc}。请只返回{entity_name}本身，不要有其他内容。"

    # 构建用户提示
    user_content = f"请从以下文本中识别提到的{entity_name}，只返回名称本身，不要有其他内容。文本：{user_input}"

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content}
    ]

    # 获取模型响应
    response = client.chat.completions.create(
        model=config['qwen']['chat_model'],
        messages=messages,
        temperature=0,
        max_tokens=20
    )

    return response.choices[0].message.content.strip()


def standardize_name(input_name: str, entity_type: str) -> str:
    """标准化实体名称（公司或行业）"""
    if entity_type == "stock":
        candidates = local_companies
    elif entity_type == "industry":
        candidates = local_industries
    elif entity_type == "concept":  # 新增概念处理
        candidates = local_concepts
    else:
        return None

    best_match = None
    highest_score = 0
    # fuzz.ratio: 进行基于 Levenshtein 距离的简单字符串比较的函数。这个函数返回一个表示相似程度的百分比，范围从0到100，值越高表示字符串越相似。
    # fuzz.partial_ratio: 基于最佳的子串（substrings）进行匹配
    # token_set_ratio: 对字符串进行标记（tokenizes）并在匹配之前按字母顺序对它们进行排序
    # token_set_ratio: 对字符串进行标记（tokenizes）并比较交集和余数
    for candidate in candidates:
        score = max(
            fuzz.ratio(input_name, candidate),
            fuzz.partial_ratio(input_name, candidate) * 1.2
        )
        if score > highest_score and score > 20:
            highest_score = score
            best_match = candidate

    return best_match


def get_completion(messages, model="qwen-plus"):
    """获取QWen模型的回复"""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        seed=1024,
        tool_choice="auto",
        tools=[{
            "type": "function",
            "function": {
                "name": "get_company_report_info_from_stock",
                "description": "根据公司股票名称stock,获取对应的股票新闻信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "stock": {
                            "type": "string",
                            "description": "公司股票名称",
                        }
                    },
                    "required": ["stock"]
                }
            }
        }, {
            "type": "function",
            "function": {
                "name": "get_company_report_info_from_industry",
                "description": "根据行业名称industry,获取对应的行业新闻信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "industry": {
                            "type": "string",
                            "description": "行业名称",
                        }
                    },
                    "required": ["industry"]
                }
            }
        }, {
            "type": "function",
            "function": {
                "name": "get_company_report_info_from_concept",
                "description": "根据概念名称concept,获取对应的概念新闻信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concept": {
                            "type": "string",
                            "description": "概念名称",
                        }
                    },
                    "required": ["concept"]
                }
            }
        }],
    )
    return response.choices[0].message


def get_company_report_info_from_stock(stock):
    """根据公司股票名称查询股票新闻信息"""
    db_config = {
        'host': '192.168.1.101',
        'port': 13306,
        'user': 'news_user',
        'password': 'km101',
        'database': 'stock_news'
    }
    return get_company_news_from_stock(stock, db_config, days_ago=10)


def get_company_report_info_from_industry(industry):
    """根据行业名称查询行业新闻信息"""
    db_config = {
        'host': '192.168.1.101',
        'port': 13306,
        'user': 'news_user',
        'password': 'km101',
        'database': 'stock_news'
    }
    return get_company_news_from_industry(industry, db_config, days_ago=30)


def get_company_report_info_from_concept(concept):
    """根据行业名称查询概念新闻信息"""
    db_config = {
        'host': '192.168.1.101',
        'port': 13306,
        'user': 'news_user',
        'password': 'km101',
        'database': 'stock_news'
    }
    return get_company_news_from_concept(concept, db_config, days_ago=30)


def process_request(prompt: str) -> str:
    """处理用户请求的完整流程"""
    try:
        # 1. 识别查询意图
        intent_type, recognized_entity = detect_query_intent(prompt)
        print(f"识别到的意图类型: {intent_type}, 实体: {recognized_entity}")

        if not intent_type or not recognized_entity:
            # 如果自动识别失败，尝试手动识别
            recognized_entity = recognize_entity(prompt, "stock")
            if recognized_entity:
                intent_type = "stock"
            else:
                recognized_entity = recognize_entity(prompt, "industry")
                if recognized_entity:
                    intent_type = "industry"
                else:
                    # 新增概念识别
                    recognized_entity = recognize_entity(prompt, "concept")
                    if recognized_entity:
                        intent_type = "concept"

        if not intent_type or not recognized_entity:
            return "未识别到有效的查询内容，请尝试更明确的表述，如'查询阿里巴巴的新闻'或'房地产行业有什么动态'"

        # 2. 标准化实体名称
        standardized_name = standardize_name(recognized_entity, intent_type)
        if not standardized_name:
            if intent_type == "stock":
                return f"未找到'{recognized_entity}'对应的公司信息，支持查询：{', '.join(LOCAL_COMPANIES)}"
            elif intent_type == "industry":
                return f"未找到'{recognized_entity}'对应的行业信息，支持查询：{', '.join(LOCAL_INDUSTRIES)}"
            else:  # 新增概念错误提示
                return f"未找到'{recognized_entity}'对应的概念信息，支持查询：{', '.join(LOCAL_CONCEPTS)}"

        print(f"标准化后的名称: {standardized_name}")

        # 3. 准备对话消息
        query_type = "公司" if intent_type == "stock" else "行业" if intent_type == "industry" else "概念"
        messages = [
            {"role": "system", "content": "你是一个金融领域专家"},
            {"role": "user", "content": f"请查询{query_type} {standardized_name}的新闻信息"}
        ]

        response = get_completion(messages)
        if response.content is None:
            response.content = ""
        messages.append(response)
        print("=====GPT回复=====")
        print(response)
        # 4. 处理函数调用
        while response.tool_calls is not None:
            for tool_call in response.tool_calls:

                args = json.loads(tool_call.function.arguments)
                print(args)

                if tool_call.function.name == "get_company_report_info_from_stock":
                    print("Call: get_company_report_info_from_stock")
                    result = get_company_report_info_from_stock(**args)
                elif tool_call.function.name == "get_company_report_info_from_industry":
                    print("Call: get_company_report_info_from_industry")
                    result = get_company_report_info_from_industry(**args)
                elif tool_call.function.name == "get_company_report_info_from_concept":
                    print("Call: get_company_report_info_from_concept")
                    result = get_company_report_info_from_concept(**args)

                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": str(result)
                })

            response = get_completion(messages)
            if response.content is None:
                response.content = ""
            messages.append(response)

        # return response.content
        return result

    except Exception as e:
        print(f"处理请求时出错: {str(e)}")
        return "查询过程中出现错误，请稍后再试"


if __name__ == "__main__":
    test_cases = [
        # "想了解万润股份最近的一些信息",
        # "房地产行业目前面临哪些风险？",
        # "半导体行业的估值是否处于历史低位？"
        # "宁德时代有什么新消息",
        # "科技行业最近有什么发展趋势",
        "DeepSeek概念最近为啥这么火"
    ]
    for query in test_cases:
        print(f"\n用户查询: {query}")
        result = process_request(query)
        print("查询结果:")
        print(result)
        print("-" * 50)
