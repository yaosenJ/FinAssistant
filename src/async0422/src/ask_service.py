# !/usr/bin/python3
# -*- coding: utf-8 -*-
import requests

# 定义 API URL
api_url = " http://192.168.1.227:8000/generate_summary"

request_body = {
    "query": "新能源汽车行业未来5年的发展前景如何？",
    "content": "新能源",
    "type": "concept"
}

# 发送 POST 请求
try:
    response = requests.post(api_url, json=request_body)
    print("响应状态码:", response.status_code)

    if response.status_code == 200:
        print("返回数据:", response.json())
    else:
        print("请求失败，错误信息:", response.text)
except requests.exceptions.RequestException as e:
    print(f"请求出错: {e}")