# -*- coding: utf-8 -*-
"""
FinAssistant 投资组合智能体

整合多因子打分、组合构建、研报生成于一体。
Agent 自主决策选股和权重分配，生成投资组合和投资报告。

可回答的问题示例：
- "帮我构建一个投资组合"
- "根据最新数据选股"
- "优化一下我的持仓"
- "生成投资报告"

用法:
    python agents/portfolio_agent.py

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

# 导入组合构建工具
from tools.portfolio_builder import build_portfolio, validate_portfolio, get_portfolio_summary

# 导入研报数据聚合工具
from tools.report_generator import (
    collect_stock_report_data,
    collect_comparison_report_data,
    save_report,
)

# 导入个股分析工具
from tools.stock_fundamental import calc_fundamental_indicators, calc_fundamental_trend
from tools.stock_valuation import calc_valuation_percentile, get_latest_valuation
from tools.stock_technical import calc_technical_indicators, get_kline_data
from tools.financial_anomaly import detect_anomalies
from tools.financial_score import calc_financial_score, format_financial_score
from tools.stock_analysis import generate_stock_report

# 导入板块工具
from tools.sector_ranking import get_sector_ranking, get_sector_summary
from tools.sector_rotation import get_sector_momentum, get_hot_cold_sectors
from tools.sector_financial_agg import get_sector_financial_agg, get_sector_valuation_stats

# 导入新闻工具
from tools.news_stock_linker import find_news_by_keyword, search_news_with_market


# ====================== 配置 ======================
SKILLS_DIR = os.path.join(PROJECT_DIR, "skills")
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


def create_agent():
    """创建投资组合智能体"""

    print("[启动] FinAssistant 投资组合智能体")

    # ====================== 工具组定义 ======================

    # 1. 个股分析工具
    stock_analysis_tools = [
        FunctionTool(calc_fundamental_indicators, is_read_only=True),
        FunctionTool(calc_fundamental_trend, is_read_only=True),
        FunctionTool(calc_valuation_percentile, is_read_only=True),
        FunctionTool(get_latest_valuation, is_read_only=True),
        FunctionTool(calc_technical_indicators, is_read_only=True),
        FunctionTool(get_kline_data, is_read_only=True),
        FunctionTool(detect_anomalies, is_read_only=True),
        FunctionTool(calc_financial_score, is_read_only=True),
        FunctionTool(format_financial_score, is_read_only=True),
        FunctionTool(generate_stock_report, is_read_only=True),
    ]

    # 2. 组合构建工具
    portfolio_tools = [
        FunctionTool(build_portfolio, is_read_only=True),
        FunctionTool(validate_portfolio, is_read_only=True),
        FunctionTool(get_portfolio_summary, is_read_only=True),
    ]

    # 3. 板块分析工具
    sector_tools = [
        FunctionTool(get_sector_ranking, is_read_only=True),
        FunctionTool(get_sector_summary, is_read_only=True),
        FunctionTool(get_sector_momentum, is_read_only=True),
        FunctionTool(get_hot_cold_sectors, is_read_only=True),
        FunctionTool(get_sector_financial_agg, is_read_only=True),
        FunctionTool(get_sector_valuation_stats, is_read_only=True),
    ]

    # 4. 研报生成工具
    report_tools = [
        FunctionTool(collect_stock_report_data, is_read_only=True),
        FunctionTool(collect_comparison_report_data, is_read_only=True),
        FunctionTool(save_report, is_read_only=False),
    ]

    # 5. 新闻工具
    news_tools = [
        FunctionTool(find_news_by_keyword, is_read_only=True),
        FunctionTool(search_news_with_market, is_read_only=True),
    ]

    # 创建工具组
    tool_groups = [
        ToolGroup(
            name="stock-analysis",
            description="个股分析工具组：基本面、估值、技术面、异常检测、财务评分。"
                        "- calc_fundamental_indicators(ts_code): 基本面指标"
                        "- calc_valuation_percentile(ts_code): 估值百分位"
                        "- calc_technical_indicators(ts_code): 技术指标"
                        "- detect_anomalies(ts_code): 财务异常检测"
                        "- calc_financial_score(ts_code): 财务健康评分"
                        "- generate_stock_report(ts_code, report_type): 综合分析报告",
            tools=stock_analysis_tools,
        ),
        ToolGroup(
            name="portfolio-construction",
            description="投资组合构建工具组：基于打分结果构建组合、校验约束、生成摘要。"
                        "- build_portfolio(score_results, max_position, min_score): 构建组合，返回 {symbol: weight}"
                        "- validate_portfolio(portfolio, max_position): 校验组合约束"
                        "- get_portfolio_summary(portfolio, score_results): 组合摘要（板块分布、集中度等）"
                        "score_results 需为列表，每项含 ts_code, total_score, name, sector 等字段",
            tools=portfolio_tools,
        ),
        ToolGroup(
            name="sector-analysis",
            description="板块分析工具组：板块排名、轮动、财务聚合、估值统计。"
                        "- get_sector_ranking(top_n): 板块排名"
                        "- get_hot_cold_sectors(days): 热门/冷门板块"
                        "- get_sector_financial_agg(sector_name): 板块财务聚合"
                        "- get_sector_valuation_stats(sector_name): 板块估值统计",
            tools=sector_tools,
        ),
        ToolGroup(
            name="report-generation",
            description="研报生成工具组：聚合个股/对比数据，保存研报。"
                        "- collect_stock_report_data(ts_code): 个股全维度数据"
                        "- collect_comparison_report_data(ts_codes): 多股对比数据"
                        "- save_report(content, output_path): 保存研报文件",
            tools=report_tools,
        ),
        ToolGroup(
            name="news",
            description="新闻工具组：关键词搜索新闻，新闻关联个股/板块。"
                        "- find_news_by_keyword(keyword, limit): 搜索新闻"
                        "- search_news_with_market(keyword): 新闻关联行情",
            tools=news_tools,
        ),
    ]

    # 构建工具包
    toolkit = Toolkit(tool_groups=tool_groups)

    # 创建智能体
    agent = Agent(
        name="FinAssistant-Portfolio",
        system_prompt="""你是专业的投资组合经理 FinAssistant，专注于 A 股多因子量化选股和组合构建。

# 核心能力
1. 个股分析：计算基本面、估值、技术面、动量、风险等多维度指标
2. 组合构建：基于打分结果自主选股，分配权重，控制风险
3. 板块分析：板块排名、轮动趋势、财务聚合、估值分布
4. 研报生成：生成个股研报和组合投资报告

# 核心规则
1. 【数据优先】
   - 必须调用工具获取数据，禁止凭记忆或编造数据
   - 选股前先获取板块排名和热门板块，了解市场格局
   - 对候选股票逐一分析基本面、估值、技术面

2. 【组合约束】
   - 单只股票最大仓位不超过 20%
   - 权重归一化确保总和 = 1.0
   - 避免过度集中于单一板块
   - 使用 validate_portfolio 校验组合

3. 【选股流程】
   - Step 1: 调用 get_sector_ranking 了解板块格局
   - Step 2: 调用 get_hot_cold_sectors 识别热门板块
   - Step 3: 对重点关注板块的个股逐一调用 calc_fundamental_indicators + calc_valuation_percentile + calc_technical_indicators
   - Step 4: 综合评估后调用 build_portfolio 构建组合
   - Step 5: 调用 validate_portfolio 校验约束
   - Step 6: 调用 get_portfolio_summary 生成组合摘要

4. 【风险控制】
   - 必须调用 detect_anomalies 检测财务异常
   - 高估股票（PE百分位 > 80%）需谨慎
   - 检测到 HIGH 级异常的股票需排除或降低权重

5. 【输出格式】
   - 使用 Markdown 表格展示数据
   - 关键指标加粗标注
   - 给出明确的买入/持有/观望/减持建议

6. 【风险提示】
   - 涉及买卖建议时，必须提示风险
   - 明确声明：分析仅供参考，不构成投资建议

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
            compression_prompt="请总结以下对话中的投资组合分析信息：",
        ),
    )

    print("[完成] 投资组合智能体初始化完成")
    return agent


# ====================== 对话循环 ======================

async def chat_loop(agent):
    """交互式对话循环"""
    print("=" * 60)
    print("FinAssistant — 投资组合智能体")
    print("=" * 60)
    print("输入投资需求开始分析，输入 'quit' 退出")
    print("示例：")
    print("  - 帮我构建一个投资组合")
    print("  - 分析一下白酒板块的龙头股")
    print("  - 对比茅台、五粮液、泸州老窖，选一只")
    print("  - 最近哪些板块比较热？帮我选几只")
    print("  - 优化一下我的持仓配置")
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
