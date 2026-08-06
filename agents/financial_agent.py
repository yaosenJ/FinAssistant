# -*- coding: utf-8 -*-
"""
FinAssistant 财务问答智能体

整合财务指标计算、趋势分析、财务对比、异常检测、财务评分、批量筛选等工具组，
支持复杂的财务分析问答。

可回答的问题示例：
- "近一年经营活动现金流持续为正的银行股有哪些？"
- "对比宁德时代和比亚迪的资产负债率变化趋势"
- "哪些公司最近一个季度毛利率下降超过10%？"
- "给我一份贵州茅台的杜邦分析"
- "找出ROE连续三年超过20%的公司"

用法:
    python agents/financial_agent.py

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

# 导入财务分析工具函数
from tools.stock_fundamental import (
    calc_fundamental_indicators,
    calc_fundamental_trend,
    get_financial_data,
    get_report_dates,
)
from tools.financial_compare import compare_companies, compare_periods
from tools.financial_anomaly import detect_anomalies
from tools.financial_score import calc_financial_score, format_financial_score
from tools.financial_query import (
    query_financial_data,
    screen_cashflow_positive_stocks,
    screen_margin_decline_stocks,
    screen_roe_stocks,
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
    """创建财务问答智能体"""

    print("[启动] FinAssistant 财务问答智能体")

    # ====================== 工具组定义 ======================

    # 1. 财务指标计算工具
    fundamental_tools = [
        FunctionTool(calc_fundamental_indicators, is_read_only=True),
        FunctionTool(calc_fundamental_trend, is_read_only=True),
        FunctionTool(get_financial_data, is_read_only=True),
        FunctionTool(get_report_dates, is_read_only=True),
    ]

    # 2. 财务对比与趋势工具
    compare_tools = [
        FunctionTool(compare_companies, is_read_only=True),
        FunctionTool(compare_periods, is_read_only=True),
    ]

    # 3. 财务健康度与异常检测工具
    score_tools = [
        FunctionTool(format_financial_score, is_read_only=True),
        FunctionTool(calc_financial_score, is_read_only=True),
        FunctionTool(detect_anomalies, is_read_only=True),
    ]

    # 4. 批量筛选工具
    screening_tools = [
        FunctionTool(screen_cashflow_positive_stocks, is_read_only=True),
        FunctionTool(screen_margin_decline_stocks, is_read_only=True),
        FunctionTool(screen_roe_stocks, is_read_only=True),
    ]

    # 5. 财务数据查询工具
    query_tools = [
        FunctionTool(query_financial_data, is_read_only=True),
    ]

    # 创建工具组
    tool_groups = [
        ToolGroup(
            name="fundamental",
            description="财务指标计算工具组：计算单只股票的ROE、毛利率、净利率、杜邦三因子、经营现金流/净利润、"
                        "应收账款占比、资产负债率、营收/净利润同比环比增长率等基本面指标。"
                        "支持单期(calc_fundamental_indicators)和多期趋势(calc_fundamental_trend)查询。",
            tools=fundamental_tools,
        ),
        ToolGroup(
            name="compare",
            description="财务对比工具组：多家公司横向对比(compare_companies)、"
                        "单家公司多期纵向对比(compare_periods，含趋势判断)。",
            tools=compare_tools,
        ),
        ToolGroup(
            name="score-anomaly",
            description="财务健康度评分与异常检测工具组：四维度综合评分(盈利+成长+安全+质量，0-100分，优/良/中/差评级)、"
                        "7类财务异常检测(现金流骤降、应收账款激增、商誉减值、存货异常、负债率飙升、利润现金流背离、毛利率波动)。",
            tools=score_tools,
        ),
        ToolGroup(
            name="screening",
            description="批量筛选工具组：跨全市场或指定板块进行财务筛选。"
                        "- screen_cashflow_positive_stocks: 筛选经营现金流持续为正的股票（如银行股）"
                        "- screen_margin_decline_stocks: 筛选毛利率大幅下降的公司"
                        "- screen_roe_stocks: 筛选ROE连续多年超过阈值的公司",
            tools=screening_tools,
        ),
        ToolGroup(
            name="query",
            description="财务数据查询工具：按股票代码查询三大报表数据，支持指定报表类型、报告日期范围、财务指标名称。",
            tools=query_tools,
        ),
    ]

    # 构建工具包
    toolkit = Toolkit(tool_groups=tool_groups)

    # 创建智能体
    agent = Agent(
        name="FinAssistant-Financial",
        system_prompt="""你是专业的财务分析助手 FinAssistant，专注于 A 股上市公司财务数据深度分析。

# 核心能力
1. 财务指标计算：ROE、毛利率、净利率、杜邦三因子、经营现金流/净利润、应收账款占比、资产负债率、增长率
2. 多期趋势分析：近4-8期财务指标变化趋势，判断上升/下降/平稳
3. 公司横向对比：同板块或指定公司的财务指标并排对比
4. 批量筛选：跨全市场筛选符合特定财务条件的股票（现金流、ROE、毛利率等）
5. 财务健康度评分：四维度加权评分（盈利30%+成长25%+安全25%+质量20%），异常检测扣分
6. 异常检测：7类财务异常信号（现金流骤降、应收账款激增等）

# 核心规则
1. 【工具优先】
   - 所有财务数据必须通过工具获取，禁止编造数据
   - 杜邦分析 = calc_fundamental_indicators（返回杜邦_净利率、杜邦_总资产周转率、杜邦_权益乘数）

2. 【复合问题拆解】
   - 筛选类问题：先用 screening 工具批量筛选，再对结果中的重点股票深入分析
   - 对比类问题：用 compare_companies（横向）或 compare_periods（纵向）
   - 单股深度：calc_fundamental_indicators + calc_fundamental_trend + detect_anomalies + format_financial_score

3. 【板块筛选】
   - screening 工具的 sector_name 参数支持板块名（如"银行"、"白酒"、"半导体"）
   - 不传 sector_name 则筛选全市场

4. 【趋势分析】
   - calc_fundamental_trend 返回最近N期的趋势数据
   - 对比两家公司的趋势：分别调用 calc_fundamental_trend，然后人工对比

5. 【杜邦分析】
   - 杜邦分析 = ROE = 净利率 × 总资产周转率 × 权益乘数
   - 调用 calc_fundamental_indicators 获取这三个因子
   - 结合 calc_fundamental_trend 看多期变化

6. 【输出格式】
   - 使用表格展示对比数据
   - 关键数据加粗或高亮
   - 给出明确的分析结论

7. 【风险提示】
   - 涉及操作建议时，必须提示风险
   - 明确声明：分析仅供参考，不构成投资建议

# 常见问题与工具映射
- "近一年现金流持续为正的银行股" → screen_cashflow_positive_stocks(sector_name='银行', periods=4)
- "对比A和B的资产负债率趋势" → calc_fundamental_trend(ts_code) 各调一次
- "哪些公司毛利率下降超过10%" → screen_margin_decline_stocks(threshold=10)
- "给我一份茅台的杜邦分析" → calc_fundamental_indicators(ts_code='600519.SH')
- "找出ROE连续三年超20%的公司" → screen_roe_stocks(min_roe=20, years=3)
- "茅台财务健康度如何" → format_financial_score(ts_code='600519.SH')
- "对比白酒板块各公司财务" → compare_companies(sector_name='白酒')
""",
        model=_make_model(stream=True, parallel_tool_calls=True),
        toolkit=toolkit,
        state=_make_bypass_state(),
        context_config=ContextConfig(
            trigger_ratio=0.8,
            reserve_ratio=0.2,
            compression_prompt="请总结以下对话的关键财务分析信息：",
        ),
    )

    print("[完成] 财务问答智能体初始化完成")
    return agent


# ====================== 对话循环 ======================

async def chat_loop(agent):
    """交互式对话循环"""
    print("=" * 60)
    print("FinAssistant — 财务问答智能体")
    print("=" * 60)
    print("输入财务分析问题，输入 'quit' 退出")
    print("示例：")
    print("  - 近一年经营活动现金流持续为正的银行股有哪些？")
    print("  - 对比宁德时代和比亚迪的资产负债率变化趋势")
    print("  - 哪些公司最近一个季度毛利率下降超过10%？")
    print("  - 给我一份贵州茅台的杜邦分析")
    print("  - 找出ROE连续三年超过20%的公司")
    print("  - 茅台的财务健康度评分是多少？")
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
