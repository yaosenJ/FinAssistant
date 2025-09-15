# !/usr/bin/python3
# -*- coding: utf-8 -*-
# from rag_consine_date import NewsSearchSystem
from rag_consine_date_re_bge_reranker_large  import NewsSearchSystem
from get_data import get_company_report_info_from_stock, get_company_report_info_from_industry, \
    get_company_report_info_from_concept
from summary_generation import generate_summary


def get_content(query, content, type):
    days = int(10)
    system = NewsSearchSystem()
    result1 = system.search_news(query, days)
    reranked_texts = system.rerank_contexts(query=query, contexts=result1)

    if type == "stock":
        result2 = get_company_report_info_from_stock(content)
    elif type == "industry":
        result2 = get_company_report_info_from_industry(content)
    elif type == "concept":
        result2 = get_company_report_info_from_concept(content)
    # print(result1)
    # print(result2)
    # result = str(result1) + str(result2)
    # result1:list,result2:DataFrame
    result = str(result2) + str(reranked_texts)
    return result


def main(query, content, type):
    text = get_content(query, content, type)
    summary_content = generate_summary(query, text)
    return summary_content


if __name__ == "__main__":
    query = '新能源汽车的发展前景如何？'
    content = "新能源车"
    type = "concept"
    # content = get_content(query, content, type)
    # print(content)
    print(main(query, content, type))
