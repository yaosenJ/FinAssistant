# main.py
主函数入口  传入一个query、content、type，返回对应文本摘要
```python
async def main(query: str, content: str, type: str) -> str:
    """异步主函数"""
    text = await get_content(query, content, type)
    print(text)
    # summary_content = await asyncio.to_thread(AsyncQwenClient().generate_summary, query, text)
    summary_content = await AsyncQwenClient(config).generate_summary(query,text)
    return summary_content
```

