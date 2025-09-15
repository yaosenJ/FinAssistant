# !/usr/bin/python3
# -*- coding: utf-8 -*-

import mysql.connector
from openai import OpenAI
from tqdm import tqdm

# 数据库配置（请根据实际情况修改）
DB_CONFIG = {
    'host': '192.168.1.101',
    'port': 13306,
    'user': 'news_user',
    'password': 'km101',
    'database': 'stock_news'
}

# OpenAI客户端配置
client = OpenAI(
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key="sk-48d14c208910",
)


def qa_generator_llm(context: str, client: OpenAI, model: str = "qwen-plus"):
    """问答对生成函数"""
    generation_prompt = """
你的任务是根据提供的上下文内容，生成一个事实型问题及其答案。
所提问题必须能够通过上下文中具体、简洁的事实信息进行回答。
问题应当模仿搜索引擎用户可能使用的自然提问方式，这意味着问题中一定不要出现"根据文章"或"上下文"等学术性表述。

请按照以下格式输出：

输出:::
事实型问题：（你生成的问题）
答案：（对应问题的答案）

以下是提供的上下文内容：

上下文：{context}\n
输出:::"""

    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "你是一个问答对生成器"},
            {"role": "user", "content": generation_prompt.format(context=context)},
        ],
        model=model,
        temperature=0.5,
        top_p=0.99,
        max_tokens=500
    )
    return chat_completion.choices[0].message.content


def main(start_date: str, end_date: str):
    # 连接数据库
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # 执行查询
    query = """
            SELECT title, content 
            FROM new_processed_daily_news 
            WHERE (stock_name IS NOT NULL 
                   OR industry_name IS NOT NULL 
                   OR concept_name IS NOT NULL)
              AND trade_date BETWEEN %s AND %s
        """
    cursor.execute(query, (start_date, end_date))
    results = cursor.fetchall()

    # 拼接文档内容
    docs_processed = [
        f"标题：{title}\n内容：{content}"
        for title, content in results
    ]

    # 关闭数据库连接
    cursor.close()
    conn.close()

    # 处理问答对生成
    outputs = []
    for doc in tqdm(docs_processed, desc="生成问答对"):
        try:
            output_QA = qa_generator_llm(doc, client)

            # 解析结果
            question = output_QA.split("事实型问题：")[-1].split("答案：")[0].strip()
            answer = output_QA.split("答案：")[-1].strip()

            assert len(answer) < 500, "答案过长"

            outputs.append({
                "context": doc,
                "question": question,
                "answer": answer,
            })
        except Exception as e:
            print(f"处理文档时出错：{str(e)}")
            continue

    return outputs


import csv


def save_to_csv(data, filename="qa_pairs_update.csv"):
    """将问答对保存到CSV文件"""
    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ['context', 'question', 'answer']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"已保存 {len(data)} 条问答对到 {filename}")


if __name__ == "__main__":
    start_time = "2025-04-03 00:00:00"
    end_time = "2025-04-09 23:59:59"

    qa_pairs = main(start_time, end_time)

    # 新增保存CSV功能
    if qa_pairs:
        save_to_csv(qa_pairs)
    else:
        print("没有生成任何问答对，跳过保存")

    # 打印前3个结果
    for i, pair in enumerate(qa_pairs[:3]):
        print(f"\n第 {i + 1} 个问答对：")
        print(f"问题：{pair['question']}")
        print(f"答案：{pair['answer']}")
        print("-" * 50)