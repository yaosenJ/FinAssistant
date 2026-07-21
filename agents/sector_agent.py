# -*- coding: utf-8 -*-
"""
FinAssistant 板块分析智能体

整合板块排名、轮动、对比、深度分析四大工具组，提供板块轮动分析能力。

用法:
    python agents/sector_agent.py

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

# 导入板块工具函数
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
from tools.sector_compare import (
    compare_sectors,
    compare_sector_trend,
)
from tools.sector_detail import (
    get_constituent_distribution,
    get_sector_money_flow,
    get_sector_correlation,
)


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
    """创建板块分析智能体"""

    print("[启动] FinAssistant 板块分析智能体")

    # ====================== 工具组定义 ======================

    # 1. 板块排名工具
    ranking_tools = [
        FunctionTool(get_sector_ranking, is_read_only=True),
        FunctionTool(get_sector_top_gainers, is_read_only=True),
        FunctionTool(get_sector_top_losers, is_read_only=True),
        FunctionTool(get_sector_summary, is_read_only=True),
    ]

    # 2. 板块轮动工具
    rotation_tools = [
        FunctionTool(get_sector_momentum, is_read_only=True),
        FunctionTool(get_sector_rotation, is_read_only=True),
        FunctionTool(get_sector_strength, is_read_only=True),
        FunctionTool(get_hot_cold_sectors, is_read_only=True),
    ]

    # 3. 板块对比工具
    compare_tools = [
        FunctionTool(compare_sectors, is_read_only=True),
        FunctionTool(compare_sector_trend, is_read_only=True),
    ]

    # 4. 板块深度分析工具
    detail_tools = [
        FunctionTool(get_constituent_distribution, is_read_only=True),
        FunctionTool(get_sector_money_flow, is_read_only=True),
        FunctionTool(get_sector_correlation, is_read_only=True),
    ]

    # 创建工具组
    tool_groups = [
        ToolGroup(
            name="sector-ranking",
            description="板块排名工具组：涨跌幅排名、连续涨跌板块、市场概览",
            tools=ranking_tools,
        ),
        ToolGroup(
            name="sector-rotation",
            description="板块轮动工具组：动量分析、轮动识别、强度排名、冷热分类",
            tools=rotation_tools,
        ),
        ToolGroup(
            name="sector-compare",
            description="板块对比工具组：多板块涨跌对比、趋势强度对比",
            tools=compare_tools,
        ),
        ToolGroup(
            name="sector-detail",
            description="板块深度分析工具组：成分股分布、资金流向、板块关联度",
            tools=detail_tools,
            skills_or_loaders=[os.path.join(SKILLS_DIR, "sector-rotation")],
        ),
    ]

    # 构建工具包
    toolkit = Toolkit(tool_groups=tool_groups)

    # 创建智能体
    agent = Agent(
        name="FinAssistant-Sector",
        system_prompt="""你是专业的板块分析助手 FinAssistant，专注于 A 股板块轮动分析。

# 核心能力
1. 板块排名：涨跌幅排名、成交额排名、连续涨跌板块识别
2. 轮动分析：动量评分、资金流入/流出识别、冷热板块分类
3. 板块对比：多板块同期涨跌对比、趋势强度对比
4. 深度分析：成分股涨跌分布、资金流向分析、板块关联度

# 核心规则
1. 【工具优先】
   - 用户询问板块相关问题时，必须调用工具获取实时数据
   - 禁止凭记忆或编造数据回答

2. 【板块类型判断】
   - 用户提到"行业"或未明确说明时，默认使用 sector_type='industry'
   - 用户提到"概念"时，使用 sector_type='concept'
   - 如果用户提到的板块在行业板块中找不到，自动尝试概念板块

3. 【复合问题拆解】
   - 对于复合问题（如"热点板块有哪些？资金流向如何？"），分步调用多个工具
   - 先获取排名/热点，再分析资金流向，最后综合研判

4. 【数据准确性】
   - 所有数据必须来自工具返回
   - 引用数据时注明板块名称和日期

5. 【风险提示】
   - 涉及操作建议时，必须提示风险
   - 明确声明：分析仅供参考，不构成投资建议

6. 【语言一致性】
   - 使用用户输入的语言回复

# 常见问题处理
- "最近一周涨幅最大的板块" → get_sector_ranking + get_sector_top_gainers
- "板块资金流向" → get_sector_money_flow + get_sector_rotation
- "板块对比" → compare_sectors 或 compare_sector_trend
- "热门板块" → get_hot_cold_sectors + get_sector_momentum
- "成分股分布" → get_constituent_distribution
- "板块关联度" → get_sector_correlation
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

    print("[完成] 板块分析智能体初始化完成")
    return agent


# ====================== 对话循环 ======================

async def chat_loop(agent):
    """交互式对话循环"""
    print("=" * 60)
    print("FinAssistant — 板块轮动分析智能体")
    print("=" * 60)
    print("输入板块相关问题开始分析，输入 'quit' 退出")
    print("示例：")
    print("  - 最近一周涨幅最大的行业板块有哪些？")
    print("  - 半导体板块最近一个月资金是在流入还是流出？")
    print("  - AI概念和机器人概念的成分股重叠度有多高？")
    print("  - 今天哪些板块出现了跌停潮？")
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
