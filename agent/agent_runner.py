# agent/agent_runner.py
from __future__ import annotations
import os, re, json
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent, AgentType

from .tools import (
    choose_keyword_tool,
    generate_blog_tool,
    post_to_wordpress_tool,
)

def _llm():
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,
        api_key=os.getenv("OPENAI_API_KEY"),
        max_tokens=2000,
        timeout=120,
        max_retries=2,
    )

def _agent_for_generation():
    # 仅保留“轻载”工具给 Agent：选词、（可选）生成
    return initialize_agent(
        tools=[choose_keyword_tool],  # ⚠️ 不再把 generate/post 交给 Agent
        llm=_llm(),
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=True,
        handle_parsing_errors=True,
    )

def run_once(primary_kw: Optional[str] = None,
             secondary_kw: str = "",
             image_path: Optional[str] = None) -> int:
    agent = _agent_for_generation()

    # 1) 选主关键词（如果没传）
    if not primary_kw:
        resp = agent.invoke({"input": "Use choose-keyword to pick ONE keyword. Return ONLY the keyword."})
        primary_kw = (resp.get("output", resp) if isinstance(resp, dict) else str(resp)).strip()

    # 2) 本地直接生成内容（不走 Agent，避免 JSON/长度问题）
    blog = generate_blog_tool.func(primary_kw=primary_kw, secondary_kw=secondary_kw)
    if not isinstance(blog, dict) or not blog.get("html"):
        raise RuntimeError(f"generate-blog returned invalid payload: {blog}")

    # 3) 本地直接发布到 WordPress（同理不走 Agent）
    post_id = post_to_wordpress_tool.func(
        title=blog.get("title") or primary_kw,
        html=blog.get("html", ""),
        keywords=blog.get("keywords", primary_kw),
        meta_desc=blog.get("meta_description", ""),
        image_path=image_path or None,
    )
    return int(post_id)
