# !/usr/bin/python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
from typing import Optional
import json

# Assuming these are your existing modules
from rag_consine_date import NewsSearchSystem
from llm import process_request
from summary_generation2 import generate_summary
router = APIRouter()

# Request Model for your summary service
class SummaryRequest(BaseModel):
    query: str

# Response Model for your summary service
class SummaryResponse(BaseModel):
    summary_content: str

def get_content(query: str) -> str:
    days = int(10)
    system = NewsSearchSystem()
    result1 = system.search_news(query, days)
    result2 = process_request(query)

    json_data = result2.to_json(orient='records',
                           date_format='iso',
                           force_ascii=False)

    # Format the JSON output
    formatted_json = json.dumps(json.loads(json_data),
                                indent=2,
                                ensure_ascii=False)
    print(type(formatted_json))
    result = str(result1) + formatted_json
    return result

@router.post("/generate_summary", response_model=SummaryResponse)
async def generate_summary_endpoint(request: SummaryRequest):
    """
    Endpoint to generate a summary based on the provided query.
    """

    query = request.query
    content = get_content(query)
    summary_content = generate_summary(query, content)
    return SummaryResponse(summary_content=summary_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(router, host="192.168.1.227", port=8000)
