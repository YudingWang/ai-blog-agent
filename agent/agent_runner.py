from __future__ import annotations
import json, re
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent, AgentType
from .tools import choose_keyword_tool, generate_blog_tool, post_to_wordpress_tool

def _llm():
    return ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

def _jsonify(maybe_str):
    if isinstance(maybe_str, dict):
        return maybe_str
    try:
        cleaned = re.sub(r'```json|```', '', str(maybe_str)).strip()
        return json.loads(cleaned)
    except Exception:
        return {}

def run_once(primary_kw: Optional[str] = None, secondary_kw: str = "", image_path: Optional[str] = None) -> int:
    tools = [choose_keyword_tool, generate_blog_tool, post_to_wordpress_tool]
    agent = initialize_agent(
        tools,
        _llm(),
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False,
        handle_parsing_errors=True,
    )

    if not primary_kw:
        primary_kw = agent.run("Use the choose-keyword tool to pick a keyword for today's post.")
        primary_kw = str(primary_kw).strip()

    blog = agent.run(f"Call generate-blog with primary_kw='{primary_kw}' and secondary_kw='{secondary_kw}'. Return the JSON.")
    blog = _jsonify(blog)

    post_id = agent.run(
        f"Use post-to-wordpress to publish the article. "
        f"Args: title='{blog.get('title','')}', html='<omitted_html>', keywords='{blog.get('keywords','')}', meta_desc='{blog.get('meta_description','')}'. "
        f"image_path='{image_path or ''}'. Return the post id."
    )
    try:
        return int(str(post_id).strip())
    except Exception:
        return -1
