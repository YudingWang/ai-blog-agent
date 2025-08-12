# tools.py
from __future__ import annotations
import os, glob, random
import pandas as pd
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain.tools import tool
from .content import finalize_blog
from .wordpress import publish_post
from .config import settings

def _load_keywords(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    if path.lower().endswith(".xlsx") or path.lower().endswith(".xls"):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    for cand in ("kwName", "Keyword", "keyword"):
        if cand in df.columns:
            return [x for x in df[cand].dropna().astype(str).tolist() if x.strip()]
    return [x for x in df.iloc[:,0].dropna().astype(str).tolist() if x.strip()]

@tool("choose-keyword", return_direct=False)
def choose_keyword_tool() -> str:
    """Pick one keyword from KEYWORDS_FILE and return it as a plain string."""
    kws = _load_keywords(settings.keywords_file)
    if not kws:
        raise ValueError("No keywords found. Please check KEYWORDS_FILE.")
    return random.choice(kws)

# 为 generate-blog 定义结构化入参
class GenerateBlogInput(BaseModel):
    primary_kw: str = Field(..., description="Primary keyword for the article")
    secondary_kw: str = Field("", description="Optional secondary keyword")

@tool("generate-blog", args_schema=GenerateBlogInput, return_direct=False)
def generate_blog_tool(primary_kw: str, secondary_kw: str = "") -> dict:
    """Generate blog HTML, SEO title, keywords (comma separated), and meta description."""
    html, title, keywords, meta_desc = finalize_blog(primary_kw, secondary_kw)
    return {"html": html, "title": title, "keywords": keywords, "meta_description": meta_desc}

# 为 post-to-wordpress 定义结构化入参
class PostToWordpressInput(BaseModel):
    title: str = Field(..., description="Post title to publish")
    html: str = Field(..., description="HTML content of the article")
    keywords: str = Field(..., description="Comma separated keywords; first is focus keyword")
    meta_desc: str = Field(..., description="SEO meta description")
    image_path: Optional[str] = Field(None, description="Optional local path to featured image")

@tool("post-to-wordpress", args_schema=PostToWordpressInput, return_direct=False)
def post_to_wordpress_tool(title: str, html: str, keywords: str, meta_desc: str, image_path: Optional[str] = None) -> int:
    """Publish the article to WordPress with RankMath meta. Returns the post id (int)."""
    return publish_post(
        title=title,
        content_html=html,
        meta_title=title,
        meta_description=meta_desc,
        focus_keyword=keywords.split(",")[0].strip() if keywords else "",
        image_path=image_path,
        alt_text=meta_desc,
    )
