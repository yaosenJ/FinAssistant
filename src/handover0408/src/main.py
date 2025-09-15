# !/usr/bin/python3
# -*- coding: utf-8 -*-

import json

from rag_consine_date import NewsSearchSystem
from llm import process_request
from summary_generation import generate_summary

def get_content(query):
    days = int(10)
    system = NewsSearchSystem()
    result1 = system.search_news(query, days)
    result2 = process_request(query)

    json_data = result2.to_json(orient='records',
                                date_format='iso',
                                force_ascii=False)

    # 美化输出格式
    formatted_json = json.dumps(json.loads(json_data),
                                indent=2,
                                ensure_ascii=False)
    print(type(formatted_json))
    result = str(result1) + formatted_json
    return result


def main(query):
    content = get_content(query)
    summary_content = generate_summary(query, content)
    return summary_content


if __name__ == "__main__":
    # query = '半导体行业的估值是否处于历史低位？'
    query = '新能源汽车的发展前景如何？'
    # query = 'Deepseek最近有什么新闻'

    content = get_content(query)
    print(content)

    print(main(query))

# print(get_content('半导体行业的估值是否处于历史低位？'))


# if __name__ == "__main__":
#     system = NewsSearchSystem()
#     try:
#         # print("正在初始化数据...")
#         # system.load_data()
#
#         while True:
#             query = input("\n请输入问题(输入 q 退出): ").strip()
#             if query.lower() == 'q':
#                 break
#
#             days = int(20)
#             result1 = system.search_news(query, days)
#             print("向量检索结果：")
#             system.print_results(result1)
#             print("向量检索结果：")
#             result2 = process_request(query)
#             print(result2)
#     finally:
#         system.close()
