# -*- coding: utf-8 -*-
"""
FinAssistant 市场日报智能体

整合大盘概览、趋势研判、板块轮动、异动检测、新闻关联、自选股日报等工具组，
支持市场日报/晨会简报的自然语言问答。

可回答的问题示例：
- "帮我生成今天的市场晨会简报"
- "今天有哪些股票涨停？分别属于什么板块？"
- "最近一周市场情绪怎么样？"
- "我的自选股今天表现如何？"
- "哪些板块资金在流入？"
- "今天有什么重要新闻？"

用法:
    python agents/daily_report_agent.py

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

# 导入市场日报相关工具函数
from tools.market_overview import get_market_overview, format_market_overview
from tools.market_trend import analyze_market_trend, format_market_trend
from tools.abnormal_detector import detect_abnormal, format_abnormal
from tools.daily_digest import generate_daily_digest
from tools.watchlist_report import get_watchlist_report, format_watchlist_report
from tools.sector_ranking import (
    get_sector_ranking,
    get_sector_top_gainers,
    get_sector_top_losers,
    get_sector_summary,
)
from tools.sector_rotation import (
    get_sector_momentum,
    get_sector_rotation,
    get_sector_strength,
    get_hot_cold_sectors,
)
from tools.news_stock_linker import find_news_by_keyword, search_news_with_market


# ====================== 配置 ======================
SKILLS_DIR = os.path.join(PROJECT_DIR, "skills")
LOG_DIR = os.path.join(PROJECT_DIR, "log")
os.makedirs(LOG_DIR, exist_ok=True)

# 模型配置（优先使用环境变量）
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


def create_agent():
    """创建市场日报智能体"""

    print("[启动] FinAssistant 市场日报智能体")

    # ====================== 工具组定义 ======================

    # 1. 大盘概览工具
    overview_tools = [
        FunctionTool(get_market_overview, is_read_only=True),
        FunctionTool(format_market_overview, is_read_only=True),
    ]

    # 2. 趋势研判工具
    trend_tools = [
        FunctionTool(analyze_market_trend, is_read_only=True),
        FunctionTool(format_market_trend, is_read_only=True),
    ]

    # 3. 板块分析工具
    sector_tools = [
        FunctionTool(get_sector_ranking, is_read_only=True),
        FunctionTool(get_sector_top_gainers, is_read_only=True),
        FunctionTool(get_sector_top_losers, is_read_only=True),
        FunctionTool(get_sector_summary, is_read_only=True),
        FunctionTool(get_sector_momentum, is_read_only=True),
        FunctionTool(get_sector_rotation, is_read_only=True),
        FunctionTool(get_sector_strength, is_read_only=True),
        FunctionTool(get_hot_cold_sectors, is_read_only=True),
    ]

    # 4. 异动检测工具
    abnormal_tools = [
        FunctionTool(detect_abnormal, is_read_only=True),
        FunctionTool(format_abnormal, is_read_only=True),
    ]

    # 5. 新闻工具
    news_tools = [
        FunctionTool(find_news_by_keyword, is_read_only=True),
        FunctionTool(search_news_with_market, is_read_only=True),
    ]

    # 6. 自选股日报工具
    watchlist_tools = [
        FunctionTool(get_watchlist_report, is_read_only=True),
        FunctionTool(format_watchlist_report, is_read_only=True),
    ]

    # 7. 一键日报工具
    digest_tools = [
        FunctionTool(generate_daily_digest, is_read_only=True),
    ]

    # 创建工具组
    tool_groups = [
        ToolGroup(
            name="market-overview",
            description="大盘概览工具组：查询全市场涨跌家数、涨停跌停、成交额、市场情绪等。"
                        "- get_market_overview: 返回结构化数据"
                        "- format_market_overview: 返回 Markdown 格式",
            tools=overview_tools,
        ),
        ToolGroup(
            name="market-trend",
            description="趋势研判工具组：基于近N日数据多维度评分，判断市场情绪（乐观/中性偏多/中性/中性偏空/悲观）。"
                        "- analyze_market_trend(days=5): 返回评分和各维度因子"
                        "- format_market_trend(days=5): 返回 Markdown 格式",
            tools=trend_tools,
        ),
        ToolGroup(
            name="sector-analysis",
            description="板块分析工具组：板块排名、轮动、冷热分类。"
                        "- get_sector_ranking: 板块涨跌幅/成交额排名"
                        "- get_sector_top_gainers/losers: 连续N天上涨/下跌的板块"
                        "- get_sector_summary: 板块市场概览"
                        "- get_sector_rotation: 资金流入/流出板块识别"
                        "- get_hot_cold_sectors: 热门/温热/平淡/冷门分类"
                        "- get_sector_momentum: 动量分析"
                        "- get_sector_strength: 强度排名",
            tools=sector_tools,
        ),
        ToolGroup(
            name="abnormal-detection",
            description="异动检测工具组：涨停/跌停股、放量突破、大幅异动、板块异动。"
                        "- detect_abnormal: 返回结构化异动数据"
                        "- format_abnormal: 返回 Markdown 格式",
            tools=abnormal_tools,
        ),
        ToolGroup(
            name="news",
            description="新闻工具组：按关键词搜索新闻，新闻关联个股/板块行情。"
                        "- find_news_by_keyword(keyword, limit): 关键词搜索新闻"
                        "- search_news_with_market(keyword, limit): 搜索新闻并关联匹配个股/板块的近期行情",
            tools=news_tools,
        ),
        ToolGroup(
            name="watchlist",
            description="自选股日报工具组：用户关注股票的当日行情、近5日涨跌、相关新闻。"
                        "- get_watchlist_report(ts_codes): 返回结构化数据"
                        "- format_watchlist_report(ts_codes): 返回 Markdown 格式"
                        "ts_codes 为股票代码列表，如 ['600519.SH', '300750.SZ']",
            tools=watchlist_tools,
        ),
        ToolGroup(
            name="daily-digest",
            description="一键日报工具组：汇总大盘概览、趋势研判、板块轮动、异动检测、新闻，生成完整日报。"
                        "- generate_daily_digest(trade_date, watchlist): 生成完整 Markdown 日报"
                        "watchlist 为可选的自选股代码列表",
            tools=digest_tools,
        ),
    ]

    # 构建工具包
    toolkit = Toolkit(tool_groups=tool_groups)

    # 创建智能体
    agent = Agent(
        name="FinAssistant-DailyReport",
        system_prompt="""你是专业的市场日报助手 FinAssistant，专注于 A 股市场每日行情分析和简报生成。

# 核心能力
1. 大盘概览：涨跌家数、涨停跌停、成交额、市场情绪判断
2. 趋势研判：多维度评分（涨跌比/涨停比/成交额/板块/连续趋势），给出乐观~悲观判断
3. 板块轮动：涨跌排名、资金流入/流出板块、冷热板块分类
4. 异动检测：涨停/跌停股、放量突破、大幅异动、板块异动
5. 新闻摘要：关键词搜索新闻，新闻关联个股/板块
6. 自选股日报：用户关注股票的行情和相关新闻
7. 一键日报：汇总全部模块生成完整每日简报

# 核心规则
1. 【一键日报】
   - 用户说"帮我生成今天的日报/晨会简报"时，直接调用 generate_daily_digest
   - 如果用户提到自选股，传入 watchlist 参数
   - generate_daily_digest 会自动调用所有子模块

2. 【按需查询】
   - 用户问具体问题时，调用对应的工具组
   - "今天涨停的股票" → detect_abnormal 或 format_abnormal
   - "最近市场情绪怎么样" → analyze_market_trend
   - "哪些板块在涨" → get_sector_ranking 或 get_hot_cold_sectors
   - "资金流入哪些板块" → get_sector_rotation
   - "我的自选股表现" → format_watchlist_report

3. 【新闻查询】
   - 用户问新闻相关：find_news_by_keyword(keyword, limit)
   - 用户问新闻对市场的影响：search_news_with_market(keyword, limit)

4. 【输出格式】
   - 使用 Markdown 表格展示数据
   - 关键数据加粗或高亮
   - 给出简明的分析结论

5. 【风险提示】
   - 涉及操作建议时，必须提示风险
   - 明确声明：分析仅供参考，不构成投资建议

# 常见问题与工具映射
- "帮我生成今天的晨会简报" → generate_daily_digest()
- "今天有哪些涨停股" → format_abnormal()
- "最近一周市场情绪怎么样" → format_market_trend(days=5)
- "哪些板块在涨" → get_sector_ranking(top_n=10)
- "资金流入哪些板块" → get_sector_rotation(top_n=5)
- "热门板块有哪些" → get_hot_cold_sectors(days=5)
- "今天有什么重要新闻" → find_news_by_keyword("A股", limit=10)
- "半导体最近有什么新闻" → find_news_by_keyword("半导体", limit=5)
- "新闻对茅台的影响" → search_news_with_market("贵州茅台")
- "我的自选股今天表现" → format_watchlist_report(['600519.SH', ...])
""",
        model=_make_model(stream=True, parallel_tool_calls=True),
        toolkit=toolkit,
        state=_make_bypass_state(),
        context_config=ContextConfig(
            trigger_ratio=0.8,
            reserve_ratio=0.2,
            compression_prompt="请总结以下对话的关键市场分析信息：",
        ),
    )

    print("[完成] 市场日报智能体初始化完成")
    return agent


# ====================== 对话循环 ======================

async def chat_loop(agent):
    """交互式对话循环"""
    print("=" * 60)
    print("FinAssistant — 市场日报智能体")
    print("=" * 60)
    print("输入市场相关问题，输入 'quit' 退出")
    print("示例：")
    print("  - 帮我生成今天的市场晨会简报")
    print("  - 今天有哪些股票涨停？分别属于什么板块？")
    print("  - 最近一周市场情绪怎么样？")
    print("  - 哪些板块资金在流入？")
    print("  - 今天有什么重要新闻？")
    print("  - 我的自选股今天表现如何？")
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
