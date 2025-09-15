import time
import dashscope
from typing import List, Dict
from pymilvus import connections, Collection
import numpy as np
from openai import OpenAI  # 使用兼容OpenAI的SDK
import yaml


# ================= 配置加载 =================
def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


config = load_config('../config/config.yaml')

# ================= 服务初始化 =================
# 配置Dashscope
dashscope.api_key = config['qwen']['api_key']

# 初始化Qwen客户端
qwen_client = OpenAI(
    api_key=config['qwen']['api_key'],
    base_url=config['qwen']['base_url']
)


# ================= 核心功能 =================
def get_embedding(text: str) -> List[float]:
    """获取文本向量（带异常重试）"""
    for _ in range(3):
        try:
            resp = dashscope.TextEmbedding.call(
                model=config['qwen']['embedding_model'],
                input=text,
                text_type="document"
            )
            if resp.status_code == 200:
                return resp.output['embeddings'][0]['embedding']
        except Exception as e:
            print(f"向量生成异常: {str(e)}")
        time.sleep(1)
    return None


def generate_summary(query: str, contexts: str) -> str:
    """使用Qwen生成智能摘要"""
    # context_str = "\n".join(
    #     f"[片段{i + 1}]: {ctx}"
    #     for i, ctx in enumerate(contexts[:10]))

    try:
        response = qwen_client.chat.completions.create(
            model=config['qwen']['chat_model'],
            messages=[
                {"role": "system",
                 "content": "你是一个专业的证券领域的信息整合助手，需要根据提供的文本片段生成详细的摘要，并将生成的摘要生成为一个简报"},
                {"role": "user", "content": f"""
                问题：{query}

                相关文本：
                {contexts}

                请生成满足以下要求的摘要：
                1. 直接回答问题核心，不要复述问题
                2. 保留关键数据（数值、时间等）
                3. 不要包含"根据资料"等前缀
                4. 不要看trade_date的信息
                """}
            ],
            temperature=0.3,
            top_p=0.9
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"摘要生成失败: {str(e)}")
        return "摘要生成失败"


# ================= 主流程 =================
def main():
    # 连接Milvus
    connections.connect(
        host=config['milvus']['host'],
        port=config['milvus']['port'],
        alias='default'
    )
    collection = Collection(config['milvus']['collection_name'])
    collection.load()

    # 读取测试问题
    with open('../data/test.txt', 'r', encoding='gbk') as f:
        queries = [line.strip() for line in f if line.strip()]

    # 处理每个查询
    for i, query in enumerate(queries, 1):
        print(f"\n[{i}/{len(queries)}] 问题: {query}")

        # 1. 向量检索
        embedding = get_embedding(query)
        if not embedding:
            continue

        start_time = time.time()

        # Milvus搜索
        results = collection.search(
            data=[np.array(embedding).tolist()],
            anns_field="embedding",
            param={
                "metric_type": config['milvus']['search_params']['metric_type'],
                "params": {"nprobe": config['milvus']['search_params']['nprobe']}
            },
            limit=config['milvus']['search_params']['limit'],
            output_fields=["content", "title"]
        )

        # 2. 提取检索结果
        hits = results[0]
        if not hits:
            print("未找到相关结果")
            continue

        contexts = [{
            "title": hit.entity.get("title"),
            "content": hit.entity.get("content")
        } for hit in hits]

        # 3. 生成智能摘要
        summary = generate_summary(query, [ctx["content"] for ctx in contexts])
        print(f"\n摘要: {summary}")

        # 4. 显示检索结果
        print("\n相关结果:")
        for j, ctx in enumerate(contexts, 1):
            print(f"{j}. [{ctx['title']}] {ctx['content'][:100]}...")

        print(f"总耗时: {time.time() - start_time:.2f}s")

    # 清理连接
    connections.disconnect('default')


if __name__ == "__main__":
    main()
