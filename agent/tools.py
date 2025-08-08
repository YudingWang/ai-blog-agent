from __future__ import annotations
import os, glob, random
import pandas as pd
from typing import List, Optional
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
    """Pick one keyword from the configured KEYWORDS_FILE and return it."""
    kws = _load_keywords(settings.keywords_file)
    if not kws:
        raise ValueError("No keywords found. Please check KEYWORDS_FILE.")
    return random.choice(kws)

@tool("generate-blog", return_direct=False)
def generate_blog_tool(primary_kw: str, secondary_kw: str = "") -> dict:
    """Generate blog HTML, meta, and keywords from Primary and optional Secondary keyword."""
    html, title, keywords, meta_desc = finalize_blog(primary_kw, secondary_kw)
    return {"html": html, "title": title, "keywords": keywords, "meta_description": meta_desc}

@tool("post-to-wordpress", return_direct=False)
def post_to_wordpress_tool(title: str, html: str, keywords: str, meta_desc: str, image_path: Optional[str] = None) -> int:
    """Publish the article to WordPress with RankMath meta. Returns the post id."""
    return publish_post(
        title=title,
        content_html=html,
        meta_title=title,
        meta_description=meta_desc,
        focus_keyword=keywords.split(",")[0].strip() if keywords else "",
        image_path=image_path,
        alt_text=meta_desc,
    )
