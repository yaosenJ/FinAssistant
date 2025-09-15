# !/usr/bin/python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
from main import get_content

from summary_generation import generate_summary

router = APIRouter()


# Request Model for your summary service
class SummaryRequest(BaseModel):
    query: str
    content: str
    type: str


# Response Model for your summary service
class SummaryResponse(BaseModel):
    summary_content: str


@router.post("/generate_summary", response_model=SummaryResponse)
async def generate_summary_endpoint(request: SummaryRequest):
    """
    Endpoint to generate a summary based on the provided query.
    """

    query = request.query
    content = request.content
    type = request.type
    content = get_content(query, content, type)
    summary_content = generate_summary(query, content)
    return SummaryResponse(summary_content=summary_content)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(router, host="192.168.1.227", port=8000)
