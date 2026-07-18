# -*- coding: utf-8 -*-
"""
FinAssistant 个股分析智能体

整合配置、智能体初始化、对话循环于一体

用法:
    python agents/stock_agent.py

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

# 导入工具函数
from tools.stock_fundamental import (
    calc_fundamental_indicators,
    calc_fundamental_trend,
    get_financial_data,
    get_report_dates,
)
from tools.stock_valuation import (
    calc_valuation_percentile,
    calc_valuation_summary,
    get_valuation_history,
    get_latest_valuation,
)
from tools.stock_technical import (
    calc_technical_indicators,
    calc_technical_summary,
    get_kline_data,
)
from tools.stock_analysis import generate_stock_report


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
    """创建智能体"""

    print("[启动] FinAssistant 金融智能体")

    # ====================== 工具组定义 ======================

    # 1. 基本面分析工具
    fundamental_tools = [
        FunctionTool(calc_fundamental_indicators, is_read_only=True),
        FunctionTool(calc_fundamental_trend, is_read_only=True),
        FunctionTool(get_financial_data, is_read_only=True),
        FunctionTool(get_report_dates, is_read_only=True),
    ]

    # 2. 估值分析工具
    valuation_tools = [
        FunctionTool(calc_valuation_percentile, is_read_only=True),
        FunctionTool(calc_valuation_summary, is_read_only=True),
        FunctionTool(get_valuation_history, is_read_only=True),
        FunctionTool(get_latest_valuation, is_read_only=True),
    ]

    # 3. 技术指标工具
    technical_tools = [
        FunctionTool(calc_technical_indicators, is_read_only=True),
        FunctionTool(calc_technical_summary, is_read_only=True),
        FunctionTool(get_kline_data, is_read_only=True),
    ]

    # 4. 综合分析工具
    analysis_tools = [
        FunctionTool(generate_stock_report, is_read_only=True),
    ]

    # 创建工具组
    tool_groups = [
        ToolGroup(
            name="stock-fundamental",
            description="个股基本面分析工具组",
            tools=fundamental_tools,
        ),
        ToolGroup(
            name="stock-valuation",
            description="个股估值分析工具组",
            tools=valuation_tools,
        ),
        ToolGroup(
            name="stock-technical",
            description="个股技术指标工具组",
            tools=technical_tools,
        ),
        ToolGroup(
            name="stock-analysis",
            description="个股全景分析工具组",
            tools=analysis_tools,
            skills_or_loaders=[os.path.join(SKILLS_DIR, "stock-analysis")],
        ),
    ]

    # 构建工具包
    toolkit = Toolkit(tool_groups=tool_groups)

    # 创建智能体（使用 BYPASS 状态跳过工具调用确认）
    agent = Agent(
        name="FinAssistant",
        system_prompt="""你是专业的金融分析助手 FinAssistant。

# 核心能力
1. 基本面分析：计算 ROE、毛利率、资产负债率、经营现金流等指标
2. 估值分析：计算 PE/PB/PCF 百分位，判断高估/低估
3. 技术面分析：计算 MA、MACD、RSI、KDJ 等技术指标
4. 综合分析：整合三维数据，生成个股全景分析报告

# 核心规则
1. 【工具优先】
   - 用户询问股票相关问题时，必须调用工具获取实时数据
   - 禁止凭记忆或编造数据回答

2. 【数据准确性】
   - 所有指标数值必须来自工具返回
   - 引用数据时需注明来源（基本面/估值/技术面）

3. 【风险提示】
   - 涉及买卖建议时，必须提示风险
   - 明确声明：分析仅供参考，不构成投资建议

4. 【语言一致性】
   - 使用用户输入的语言回复
   - 用户中文 → 中文回复
   - 用户英文 → 英文回复

5. 【回答简洁】
   - 直接回答用户问题，不要过多解释
   - 数据展示使用表格或结构化格式

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
            compression_prompt="请总结以下对话的关键信息：",
        ),
    )

    print("[完成] 智能体初始化完成")
    return agent


# ====================== 对话循环 ======================

async def chat_loop(agent):
    """交互式对话循环"""
    print("=" * 60)
    print("FinAssistant — 金融智能体")
    print("=" * 60)
    print("输入股票代码或问题开始分析，输入 'quit' 退出")
    print("示例：")
    print("  - 分析一下600519.SH")
    print("  - 茅台估值高吗？")
    print("  - 比亚迪技术面怎么样？")
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
            show_thinking = False  # 是否显示思考过程
            tool_results = {}  # 存储工具结果 {tool_call_id: result_text}
            current_tool_id = None  # 当前正在执行的工具ID

            async for event in agent.reply_stream(user_msg):
                if isinstance(event, ReplyStartEvent):
                    # 回复开始
                    msg = AssistantMsg(name=event.name, content=[], id=event.reply_id)
                    print("\nFinAssistant: ", end="", flush=True)

                elif isinstance(event, ToolCallStartEvent):
                    # 工具调用开始
                    current_tool_id = event.tool_call_id
                    tool_results[current_tool_id] = ""
                    print(f"\n[调用工具: {event.tool_call_name}]", flush=True)

                elif isinstance(event, ToolResultStartEvent):
                    # 工具结果开始
                    pass

                elif isinstance(event, ToolResultTextDeltaEvent):
                    # 工具结果增量 - 收集结果
                    if event.tool_call_id in tool_results:
                        tool_results[event.tool_call_id] += event.delta

                elif isinstance(event, ToolResultEndEvent):
                    # 工具调用完成 - 打印结果摘要
                    if event.tool_call_id in tool_results:
                        result = tool_results[event.tool_call_id]
                        # 只显示前200个字符作为摘要
                        if len(result) > 1000:
                            print(f"[完成] 结果: {result[:1000]}...", flush=True)
                        else:
                            print(f"[完成] 结果: {result}", flush=True)
                    else:
                        print("[完成]", flush=True)
                    current_tool_id = None

                elif isinstance(event, TextBlockDeltaEvent):
                    # 文本增量 - 实时打印
                    print(event.delta, end="", flush=True)

                elif isinstance(event, ThinkingBlockDeltaEvent):
                    # 思考过程（可选显示）
                    if show_thinking:
                        print(event.delta, end="", flush=True)

                elif isinstance(event, ReplyEndEvent):
                    # 回复结束
                    pass

            print()  # 换行

        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"\n错误: {e}\n")


# ====================== 主函数 ======================

async def main():
    # 创建智能体
    agent = create_agent()

    # 启动对话循环
    await chat_loop(agent)


if __name__ == '__main__':
    asyncio.run(main())
