# -*- coding: utf-8 -*-
"""
FinAssistant 关联分析智能体

整合个股-板块映射、板块财务聚合、新闻-行情关联三大工具组，
提供跨数据关联分析能力。

用法:
    python agents/correlation_agent.py

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

# 导入关联分析工具函数
from tools.stock_sector_mapping import find_stock_sectors
from tools.sector_financial_agg import get_sector_financial_agg, get_sector_valuation_stats
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
    """创建关联分析智能体"""

    print("[启动] FinAssistant 关联分析智能体")

    # ====================== 工具组定义 ======================

    # 1. 个股-板块映射工具
    stock_sector_tools = [
        FunctionTool(find_stock_sectors, is_read_only=True),
    ]

    # 2. 板块财务分析工具
    sector_finance_tools = [
        FunctionTool(get_sector_financial_agg, is_read_only=True),
        FunctionTool(get_sector_valuation_stats, is_read_only=True),
    ]

    # 3. 新闻-行情关联工具
    news_market_tools = [
        FunctionTool(find_news_by_keyword, is_read_only=True),
        FunctionTool(search_news_with_market, is_read_only=True),
    ]

    # 创建工具组
    tool_groups = [
        ToolGroup(
            name="stock-sector",
            description="个股-板块映射工具组：查询个股所属板块及各板块近期表现",
            tools=stock_sector_tools,
        ),
        ToolGroup(
            name="sector-finance",
            description="板块财务分析工具组：板块财务聚合（ROE、毛利率、营收）、估值分布（PE/PB）",
            tools=sector_finance_tools,
        ),
        ToolGroup(
            name="news-market",
            description="新闻-行情关联工具组：新闻搜索、新闻标题关联个股/板块行情走势",
            tools=news_market_tools,
            skills_or_loaders=[os.path.join(SKILLS_DIR, "correlation")],
        ),
    ]

    # 构建工具包
    toolkit = Toolkit(tool_groups=tool_groups)

    # 创建智能体
    agent = Agent(
        name="FinAssistant-Correlation",
        system_prompt="""你是专业的跨数据关联分析助手 FinAssistant，专注于 A 股多维数据关联分析。

# 核心能力
1. 个股-板块映射：查询个股所属的行业/概念板块，以及各板块近期表现
2. 板块财务分析：板块整体ROE、毛利率、营收/净利润聚合，PE/PB估值分布
3. 新闻-行情关联：搜索市场新闻，自动关联新闻标题中提及的个股/板块行情走势

# 核心规则
1. 【工具优先】
   - 用户询问关联分析相关问题时，必须调用工具获取实时数据
   - 禁止凭记忆或编造数据回答

2. 【复合问题拆解】
   - 对于综合关联分析问题，分步调用多个工具
   - 典型流程：先查板块归属 → 再查财务/估值 → 最后关联新闻
   - 例如"茅台最近有什么利好新闻？它所在板块表现如何？"需串联三个工具组

3. 【板块类型判断】
   - 用户提到"行业"或未明确说明时，默认使用 sector_type='industry'
   - 用户提到"概念"时，使用 sector_type='concept'
   - 如果用户提到的板块在行业板块中找不到，自动尝试概念板块

4. 【股票代码格式】
   - find_stock_sectors 需要带后缀的 ts_code（如 600519.SH）
   - 如果用户输入纯数字代码，需提醒用户补充后缀

5. 【数据准确性】
   - 所有数据必须来自工具返回
   - 引用数据时注明板块名称和日期

6. 【风险提示】
   - 涉及操作建议时，必须提示风险
   - 明确声明：分析仅供参考，不构成投资建议

7. 【语言一致性】
   - 使用用户输入的语言回复

# 常见问题处理
- "贵州茅台属于哪些板块？" → find_stock_sectors
- "白酒板块的ROE和估值水平如何？" → get_sector_financial_agg + get_sector_valuation_stats
- "最近半导体有什么新闻？" → find_news_by_keyword 或 search_news_with_market
- "茅台最近有什么利好新闻？它所在板块表现如何？" → find_stock_sectors + search_news_with_market + get_sector_financial_agg
""",
        model=_make_model(stream=True, parallel_tool_calls=True),
        toolkit=toolkit,
        state=_make_bypass_state(),
        context_config=ContextConfig(
            trigger_ratio=0.8,
            reserve_ratio=0.2,
            compression_prompt="请总结以下对话的关键信息：",
        ),
    )

    print("[完成] 关联分析智能体初始化完成")
    return agent


# ====================== 对话循环 ======================

async def chat_loop(agent):
    """交互式对话循环"""
    print("=" * 60)
    print("FinAssistant — 跨数据关联分析智能体")
    print("=" * 60)
    print("输入关联分析问题，输入 'quit' 退出")
    print("示例：")
    print("  - 贵州茅台属于哪些板块？")
    print("  - 白酒板块的ROE和估值水平如何？")
    print("  - 最近有关于光伏的新闻吗？相关板块走势怎样？")
    print("  - 茅台最近有什么利好新闻？它所在板块表现如何？")
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
