# -*- coding: utf-8 -*-
"""
FinAssistant 研报分析智能体

支持个股研报、行业研报、对比研报、事件研报的自然语言生成。
工具层负责数据聚合，Agent 层负责研报文本生成。

可回答的问题示例：
- "帮我生成贵州茅台的个股研报"
- "白酒行业研究报告"
- "对比一下茅台和五粮液"
- "半导体最近有什么新闻，影响了哪些股票"

用法:
    python agents/report_agent.py

依赖:
    pip install agentscope>=2.0.3 pymysql python-dotenv
"""

import os
import sys
import asyncio

# 添加项目根目录到 Python 路径
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, '.env'))

from agentscope.agent import Agent, ContextConfig
from agentscope.model import OpenAIChatModel
from agentscope.credential import OpenAICredential
from agentscope.tool import FunctionTool, ToolGroup, Toolkit
from agentscope.message import Msg, UserMsg, AssistantMsg
from agentscope.state import AgentState
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.event import (
    ReplyStartEvent,
    ReplyEndEvent,
    ToolCallStartEvent,
    ToolCallEndEvent,
    ToolResultStartEvent,
    ToolResultTextDeltaEvent,
    ToolResultEndEvent,
    TextBlockDeltaEvent,
    ThinkingBlockDeltaEvent,
)

# 导入研报数据聚合工具
from tools.report_generator import (
    collect_stock_report_data,
    collect_industry_report_data,
    collect_comparison_report_data,
    collect_event_report_data,
    save_report,
)

# 导入底层数据查询工具
from tools.stock_fundamental import calc_fundamental_indicators, calc_fundamental_trend
from tools.stock_valuation import calc_valuation_percentile, get_latest_valuation
from tools.stock_technical import calc_technical_indicators, get_kline_data
from tools.news_stock_linker import find_news_by_keyword, search_news_with_market
from tools.sector_ranking import get_sector_ranking, get_sector_summary
from tools.sector_financial_agg import get_sector_financial_agg, get_sector_valuation_stats


# ====================== 配置 ======================
SKILLS_DIR = os.path.join(PROJECT_DIR, "skills")
TEMPLATES_DIR = os.path.join(PROJECT_DIR, "templates")
LOG_DIR = os.path.join(PROJECT_DIR, "log")
os.makedirs(LOG_DIR, exist_ok=True)

# 模型配置
DOUBAO_API_KEY = os.environ.get("DOUBAO_API_KEY", "")
DOUBAO_BASE_URL = os.environ.get("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
DOUBAO_MODEL_NAME = os.environ.get("DOUBAO_MODEL_NAME", "doubao-seed-1-8-251228")


# ====================== 智能体初始化 ======================

def _make_bypass_state() -> AgentState:
    """创建自动跳过权限确认的 AgentState"""
    return AgentState(permission_context=PermissionContext(mode=PermissionMode.BYPASS))


def _make_model(stream: bool = True, parallel_tool_calls: bool = True):
    """创建 OpenAI 兼容模型"""
    return OpenAIChatModel(
        credential=OpenAICredential(
            api_key=DOUBAO_API_KEY,
            base_url=DOUBAO_BASE_URL,
        ),
        model=DOUBAO_MODEL_NAME,
        stream=stream,
        parameters=OpenAIChatModel.Parameters(
            parallel_tool_calls=parallel_tool_calls,
        ),
    )


def _load_template(template_name):
    """加载研报模板"""
    template_path = os.path.join(TEMPLATES_DIR, template_name)
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


def create_agent():
    """创建研报分析智能体"""

    print("[启动] FinAssistant 研报分析智能体")

    # 加载模板用于系统提示词
    individual_tpl = _load_template('individual_report.md')
    industry_tpl = _load_template('industry_report.md')
    comparison_tpl = _load_template('comparison_report.md')
    event_tpl = _load_template('event_report.md')

    # ====================== 工具组定义 ======================

    # 1. 个股研报工具
    stock_report_tools = [
        FunctionTool(collect_stock_report_data, is_read_only=True),
    ]

    # 2. 行业研报工具
    industry_report_tools = [
        FunctionTool(collect_industry_report_data, is_read_only=True),
    ]

    # 3. 对比研报工具
    comparison_report_tools = [
        FunctionTool(collect_comparison_report_data, is_read_only=True),
    ]

    # 4. 事件研报工具
    event_report_tools = [
        FunctionTool(collect_event_report_data, is_read_only=True),
    ]

    # 5. 底层数据查询工具
    data_tools = [
        FunctionTool(calc_fundamental_indicators, is_read_only=True),
        FunctionTool(calc_fundamental_trend, is_read_only=True),
        FunctionTool(calc_valuation_percentile, is_read_only=True),
        FunctionTool(get_latest_valuation, is_read_only=True),
        FunctionTool(calc_technical_indicators, is_read_only=True),
        FunctionTool(get_kline_data, is_read_only=True),
        FunctionTool(find_news_by_keyword, is_read_only=True),
        FunctionTool(search_news_with_market, is_read_only=True),
        FunctionTool(get_sector_ranking, is_read_only=True),
        FunctionTool(get_sector_summary, is_read_only=True),
        FunctionTool(get_sector_financial_agg, is_read_only=True),
        FunctionTool(get_sector_valuation_stats, is_read_only=True),
    ]

    # 6. 报告保存工具
    save_tools = [
        FunctionTool(save_report, is_read_only=False),
    ]

    # 创建工具组
    tool_groups = [
        ToolGroup(
            name="stock-report",
            description="个股研报数据聚合工具组。"
                        "- collect_stock_report_data(ts_code): 聚合个股全维度数据（基本面+估值+技术面+异常检测+板块对比），返回结构化 dict",
            tools=stock_report_tools,
        ),
        ToolGroup(
            name="industry-report",
            description="行业研报数据聚合工具组。"
                        "- collect_industry_report_data(sector_name): 聚合板块数据（成分股+排名+财务聚合+估值分布+轮动趋势）",
            tools=industry_report_tools,
        ),
        ToolGroup(
            name="comparison-report",
            description="对比研报数据聚合工具组。"
                        "- collect_comparison_report_data(ts_codes): 多只股票横向对比数据（ts_codes 为代码列表，如 ['600519.SH', '000858.SZ']）",
            tools=comparison_report_tools,
        ),
        ToolGroup(
            name="event-report",
            description="事件研报数据聚合工具组。"
                        "- collect_event_report_data(keyword): 事件影响数据（新闻+受影响个股行情），keyword 为事件关键词",
            tools=event_report_tools,
        ),
        ToolGroup(
            name="data-query",
            description="底层数据查询工具组：直接查询基本面、估值、技术面、新闻、板块数据。"
                        "当需要获取单只股票的详细数据时使用。",
            tools=data_tools,
        ),
        ToolGroup(
            name="report-save",
            description="报告保存工具组。"
                        "- save_report(content, output_path): 将研报内容保存为 Markdown 文件",
            tools=save_tools,
        ),
    ]

    # 构建工具包
    toolkit = Toolkit(tool_groups=tool_groups)

    # 创建智能体
    agent = Agent(
        name="FinAssistant-Report",
        system_prompt=f"""你是专业的金融研报分析师 FinAssistant，专注于生成高质量的 A 股投资研究报告。

# 核心能力
1. 个股研报：调用 collect_stock_report_data 获取全维度数据，生成 12 节个股研报
2. 行业研报：调用 collect_industry_report_data 获取板块数据，生成行业研究报告
3. 对比研报：调用 collect_comparison_report_data 获取多只股票数据，生成横向对比报告
4. 事件研报：调用 collect_event_report_data 获取新闻和行情数据，生成事件影响分析

# 核心规则
1. 【工具优先】
   - 必须调用工具获取数据，禁止凭记忆或编造数据
   - 个股研报 → collect_stock_report_data(ts_code)
   - 行业研报 → collect_industry_report_data(sector_name)
   - 对比研报 → collect_comparison_report_data(ts_codes_list)
   - 事件研报 → collect_event_report_data(keyword)

2. 【研报质量】
   - 使用专业金融术语，结构清晰
   - 所有数据必须来自工具返回，引用时注明来源
   - 给出明确的评级和投资建议（买入/持有/观望/减持）
   - 必须包含风险提示和免责声明

3. 【输出格式】
   - 使用 Markdown 格式
   - 数据展示使用表格
   - 关键指标加粗标注
   - 图表引用使用相对路径

4. 【语言一致性】
   - 始终使用中文生成研报

# 研报模板结构

## 个股研报结构（参考）
{individual_tpl[:2000] if individual_tpl else '投资要点→公司概况→盈利分析→盈利质量→成长性→估值→技术面→动量→风险→综合评估→行业对比→盈利预测'}

## 行业研报结构（参考）
{industry_tpl[:1000] if industry_tpl else '板块概况→成分股排名→财务聚合→估值分布→轮动趋势→投资建议'}

## 对比研报结构（参考）
{comparison_tpl[:1000] if comparison_tpl else '公司概况对比→盈利对比→估值对比→技术面对比→动量对比→风险对比→综合结论'}

## 事件研报结构（参考）
{event_tpl[:1000] if event_tpl else '事件概述→影响分析→受影响个股→历史类比→投资建议'}

# 股票代码格式
- 沪市：600xxx.SH（如 600519.SH 贵州茅台）
- 深市：000xxx.SZ（如 000858.SZ 五粮液）
- 创业板：300xxx.SZ（如 300750.SZ 宁德时代）
- 科创板：688xxx.SH（如 688981.SH 中芯国际）
""",
        model=_make_model(stream=True, parallel_tool_calls=True),
        toolkit=toolkit,
        state=_make_bypass_state(),
        context_config=ContextConfig(
            trigger_ratio=0.8,
            reserve_ratio=0.2,
            compression_prompt="请总结以下对话中的研报分析信息：",
        ),
    )

    print("[完成] 研报分析智能体初始化完成")
    return agent


# ====================== 对话循环 ======================

async def chat_loop(agent):
    """交互式对话循环"""
    print("=" * 60)
    print("FinAssistant — 研报分析智能体")
    print("=" * 60)
    print("输入研报需求开始生成，输入 'quit' 退出")
    print("示例：")
    print("  - 帮我生成贵州茅台的个股研报")
    print("  - 白酒行业研究报告")
    print("  - 对比一下茅台和五粮液")
    print("  - 半导体最近有什么新闻，影响了哪些股票")
    print("  - 宁德时代的投资研究报告")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("你: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("再见！")
                break

            # 调用智能体（流式输出）
            user_msg = UserMsg(name="user", content=user_input)
            msg = None
            show_thinking = False
            tool_results = {}
            current_tool_id = None

            async for event in agent.reply_stream(user_msg):
                if isinstance(event, ReplyStartEvent):
                    msg = AssistantMsg(name=event.name, content=[], id=event.reply_id)
                    print("\nFinAssistant: ", end="", flush=True)

                elif isinstance(event, ToolCallStartEvent):
                    current_tool_id = event.tool_call_id
                    tool_results[current_tool_id] = ""
                    print(f"\n[调用工具: {event.tool_call_name}]", flush=True)

                elif isinstance(event, ToolResultStartEvent):
                    pass

                elif isinstance(event, ToolResultTextDeltaEvent):
                    if event.tool_call_id in tool_results:
                        tool_results[event.tool_call_id] += event.delta

                elif isinstance(event, ToolResultEndEvent):
                    if event.tool_call_id in tool_results:
                        result = tool_results[event.tool_call_id]
                        if len(result) > 1000:
                            print(f"[完成] 结果: {result[:1000]}...", flush=True)
                        else:
                            print(f"[完成] 结果: {result}", flush=True)
                    else:
                        print("[完成]", flush=True)
                    current_tool_id = None

                elif isinstance(event, TextBlockDeltaEvent):
                    print(event.delta, end="", flush=True)

                elif isinstance(event, ThinkingBlockDeltaEvent):
                    if show_thinking:
                        print(event.delta, end="", flush=True)

                elif isinstance(event, ReplyEndEvent):
                    pass

            print()

        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"\n错误: {e}\n")


# ====================== 主函数 ======================

async def main():
    agent = create_agent()
    await chat_loop(agent)


if __name__ == '__main__':
    asyncio.run(main())
