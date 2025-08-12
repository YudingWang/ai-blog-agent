from __future__ import annotations
import os
import time
import json
import re
import hashlib
from html import escape
from typing import Tuple, Dict, List
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

# ---------------- LLM config ----------------
def _llm(model_name: str = "gpt-4o-mini", temperature: float = 0.4) -> ChatOpenAI:
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        max_tokens=4000,
        api_key=os.getenv("OPENAI_API_KEY"),
        timeout=120,
        max_retries=2,
    )

# ---------------- utilities ----------------
def _strip_code_fences(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"(?is)^\s*```(?:html)?\s*|\s*```\s*$", "", text).strip()
    text = re.sub(r'^\s*["`“”]+', "", text)
    return text.strip()

def _word_count(html: str) -> int:
    txt = re.sub(r"<[^>]+>", " ", html or "")
    return len(re.findall(r"\w+", txt))

def _expand_html(html: str, sections_json: Dict, keywords_line: str,
                 target_min: int = 1200, target_max: int = 1600) -> str:
    llm = _llm(temperature=0.2)
    prompt = f"""
You are an editor. Expand the following HTML article to {target_min}-{target_max} words.
Keep all existing H2/H3 headings, structure, and style. Do not add <h1>.
Preserve the first <h2> as the on-page title. Keep compliance callouts and short paragraphs.
Use the Primary keyword from '{keywords_line}' naturally across headings and body.
Return HTML only (no code fences).

[Current HTML]
{html}
"""
    resp = llm.invoke(prompt)
    return _strip_code_fences(resp.content)

def _first_paragraph_text(html: str) -> str:
    m = re.search(r"<p[^>]*>(.*?)</p>", html or "", flags=re.I | re.S)
    if not m:
        return ""
    raw = re.sub(r"<.*?>", " ", m.group(1))
    return re.sub(r"\s+", " ", raw).strip()

def _diversify_title(meta_title: str, primary: str) -> str:
    """若标题与主关键词一样或过短，则在不改变关键词的前提下添加稳定后缀。"""
    base = (meta_title or "").strip()
    if not primary:
        return base
    norm_base = re.sub(r"\s+", " ", base).strip().lower()
    norm_primary = primary.strip().lower()
    if not base or norm_base == norm_primary or len(base) < 25:
        suffixes = [
            "— Key Insights for Leaders",
            "— Compliance & Hiring Guide",
            "— What You Need to Know",
            "— 2025 Playbook",
            "— Quick Guide", "— Essentials", "— Executive Brief", "— 2025 Update",
            "— Best Practices", "— Compliance Basics", "— Hiring Guide", "— For CEOs & CFOs",
            "— Action Checklist", "— Step-by-Step", "— Key Considerations", "— What to Watch",
            "— Practical Guide", "— Market Snapshot", "— Startup Guide", "— Playbook",
            "— Tips & Traps", "— Do’s & Don’ts", "— At a Glance", "— Deep Dive",
        ]
        idx = int(hashlib.md5(primary.encode("utf-8")).hexdigest(), 16) % len(suffixes)
        base = f"{primary} {suffixes[idx]}"
    return base


# ---------------- outline & html generation ----------------
def generate_outline(primary_kw: str, secondary_kw: str = "") -> Dict:
    schema = [
        ResponseSchema(name="Recommended_Long-Tail_Keywords", description="A list of recommended Long-Tail Keywords"),
        ResponseSchema(name="Title", description="A title for the article"),
        ResponseSchema(name="Table_of_Contents", description="JSON list of chapters with fields: chapter_title, recommended_keywords, highlights"),
        ResponseSchema(name="Refined_Keywords", description="One line string containing primary and long-tail, joined by comma"),
    ]
    output_parser = StructuredOutputParser.from_response_schemas(schema)
    format_instructions = output_parser.get_format_instructions()
    template = """
    You are preparing an SEO-friendly blog outline for www.nnroad.com.

    Primary Keyword (exact, contiguous): '{Primary}'
    Additional context / secondary hints: '{Secondary}'

    Goals:
    - Produce an outline that targets to C-level leaders, such as CEOs, CFOs, HR heads, and legal leads at international companies.
    - Tone: professional, authoritative, approachable; plain English, short paragraphs/bullets; avoid dense legal text.
    - Mention any relevant local/US/California policies or laws in plain English if applicable.

    OUTPUT FORMAT (STRICT) — return JSON ONLY matching the existing schema fields below:
    1) "Recommended_Long-Tail_Keywords": A list of 3–6 long-tail keywords derived from the Primary Keyword.
    2) "Title": An SEO title that MUST include the exact Primary Keyword as a contiguous phrase. You MAY include one number and one power word and an optional positive/negative sentiment.
    3) "Table_of_Contents": A JSON list of 4–8 chapters. Each item has:
       - "chapter_title" (should be concise and, where natural, include the Primary Keyword at least once across the whole ToC)
       - "recommended_keywords" (2–5 relevant terms)
       - "highlights" (2–4 bullet points of key content ideas)
       Focus balance guideline: ~50% intro + US/California-related policies (if relevant), ~30% NNRoad recommendation/service intro, remainder best practices/FAQs.
    4) "Refined_Keywords": ONE line string: "Primary, <one long-tail keyword>" (exactly these two, comma-separated; Primary first, unchanged).

    Rules:
    - Keep the company name exactly "NNRoad" when it appears.
    - English only.
    - Return valid JSON only, no extra text.

    {format_instructions}
    """
    prompt = PromptTemplate(
        input_variables=["format_instructions", "Primary", "Secondary"],
        template=template,
    ).format(format_instructions=format_instructions, Primary=primary_kw, Secondary=secondary_kw)

    llm = _llm()
    last_err = None
    for _ in range(3):
        try:
            resp = llm.invoke(prompt)
            return output_parser.parse(resp.content)
        except Exception as e:
            last_err = e
            time.sleep(1.2)
    raise RuntimeError(f"Failed to generate outline: {last_err}")

def generate_blog_html(sections_json: Dict, keywords_line: str) -> Dict[str, str]:
    schema = [
        ResponseSchema(name="html_content", description="The refined HTML content using h2 and p tags"),
        ResponseSchema(name="Meta_title", description="A Meta_title for the article"),
        ResponseSchema(name="Meta_description", description="A Meta description for the article (<=140 chars)"),
    ]
    output_parser = StructuredOutputParser.from_response_schemas(schema)
    format_instructions = output_parser.get_format_instructions()
    template = """
    You are generating the full blog HTML and SEO meta information for www.nnroad.com.

    Sections (Table_of_Contents) JSON: '{sections}'
    Refinement keywords line: '{keywords}'

    STRICT REQUIREMENTS:
    - Length: ~1,200–1,500 words total.
    - HTML only in "html_content"; use <h2>/<h3>/<p>/<ul>/<li> (NO <h1>).
    - The FIRST <h2> is the on-page title and MUST contain the exact Primary Keyword (from '{keywords}' — the first term before the comma).
    - Use the Primary Keyword multiple times naturally; include it at least once in each chapter heading where natural.
    - Introduction: MUST contain the Primary Keyword exactly once (no more than once).
    - Style: short paragraphs, plain English; bullets/tables/callouts allowed; avoid dense legal text.
    - Mention key local/US/California laws/policies by name if relevant, with very short plain-English explanations.
    - Include at least one <div class='callout'>…</div> for key compliance notes.
    - End the article with: "If you have questions, please contact us at contact@nnroad.com."
    - Keep the company name exactly "NNRoad" when used.

    Meta fields:
    - "Meta_title": MUST include the exact Primary Keyword.
    - "Meta_description": <=140 chars and MUST include exactly one of the terms from '{keywords}'.

    OUTPUT FORMAT (STRICT):
    - Return JSON ONLY matching the existing schema fields:
      * "html_content"
      * "Meta_title"
      * "Meta_description"
    - All JSON keys/strings use double quotes.
    - Inside html_content, prefer single quotes for HTML attributes to minimize escaping.

    {format_instructions}
    """
    prompt = PromptTemplate(
        input_variables=["format_instructions", "sections", "keywords"],
        template=template,
    ).format(format_instructions=format_instructions, sections=json.dumps(sections_json), keywords=keywords_line)

    llm = _llm()
    last_err = None
    for _ in range(3):
        try:
            resp = llm.invoke(prompt)
            data = output_parser.parse(resp.content)

            html = _strip_code_fences(data.get("html_content", ""))
            if _word_count(html) < 1150:
                html = _expand_html(html, sections_json, keywords_line)

            primary = (keywords_line or "").split(",")[0].strip()
            meta_title = _strip_code_fences(data.get("Meta_title", "")) or primary
            if primary and primary.lower() not in meta_title.lower():
                meta_title = f"{primary} | NNRoad"
            meta_title = _diversify_title(meta_title, primary)

            meta_desc = _strip_code_fences(data.get("Meta_description", "")) or _first_paragraph_text(html)
            if primary and primary.lower() not in (meta_desc or "").lower():
                meta_desc = f"{primary} — {meta_desc}"
            meta_desc = meta_desc[:160]

            return {"html": html, "meta_title": meta_title, "meta_description": meta_desc}
        except Exception as e:
            last_err = e
            time.sleep(1.2)
    raise RuntimeError(f"Failed to generate blog html: {last_err}")

# ---------------- helpers for headings & internal links ----------------
def _slug(s: str) -> str:
    s = re.sub(r"<.*?>", "", s)
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    return re.sub(r"\s+", "-", s.strip().lower())

def promote_h3_to_h2(html: str) -> str:
    html = re.sub(r"(?is)<h3(\b[^>]*)>", r"<h2\1>", html)
    html = re.sub(r"(?is)</h3>", "</h2>", html)
    return html

def ensure_headings_and_ids(html: str, sections_json: List[Dict]) -> str:
    html = promote_h3_to_h2(html)
    items = []
    pat = re.compile(r"<h2[^>]*>(.*?)</h2>", re.I | re.S)

    def _add_id(m: re.Match) -> str:
        inner = m.group(1)
        text = re.sub(r"<.*?>", "", inner).strip()
        sid = _slug(text) if text else f"sec-{len(items)+1}"
        items.append((2, text or f"Section {len(items)+1}", sid))
        return f'<h2 id="{sid}">{inner}</h2>'

    html = re.sub(pat, _add_id, html)

    need_min = max(3, min(6, len(sections_json) or 0))
    if len(items) < need_min and sections_json:
        for sec in sections_json:
            title = (sec or {}).get("chapter_title", "").strip()
            if not title:
                continue
            sid = _slug(title)
            html += f'\n<h2 id="{sid}">{escape(title)}</h2>\n'
            items.append((2, title, sid))
            if len(items) >= need_min:
                break
    return html

INTERNAL_LINKS = [
    (r"\bEmployer of Record\b|\bEOR services?\b|\bEOR\b", "https://nnroad.com/services/employer-of-record/"),
    (r"\bglobal payroll\b|\bpayroll\b", "https://nnroad.com/services/global-payroll/"),
    (r"\blabor cost calculator\b", "https://nnroad.com/usa/labor-cost-calculator/"),
    (r"\bwork permits?\b|\bvisa\b", "https://nnroad.com/services/"),
]
COUNTRY_IS_US = ("united states", "usa", "u.s.", "california", "florida")

def _apply_links_in_tag(html: str, tag: str, pairs: List[tuple], seen_urls: set, limit: int) -> str:
    """只在 <p>/<li> 内做替换；同一 URL 全文只插一次；整体不超过 limit。"""
    a_pat = re.compile(r"<a\b[^>]*>.*?</a>", re.I | re.S)

    def protect(text: str):
        anchors: List[str] = []
        def _rep(m: re.Match) -> str:
            anchors.append(m.group(0))
            return f"__A_{len(anchors)-1}__"
        return a_pat.sub(_rep, text), anchors

    def restore(text: str, anchors: List[str]) -> str:
        for i, a in enumerate(anchors):
            text = text.replace(f"__A_{i}__", a)
        return text

    def repl(m: re.Match) -> str:
        start, inner, end = m.group(1), m.group(2), m.group(3)
        prot, anchors = protect(inner)
        for pat, url in pairs:
            if len(seen_urls) >= limit or url in seen_urls:
                continue
            prot2, n = re.subn(pat, r'<a href="' + url + r'">\g<0></a>', prot, count=1, flags=re.I)
            if n:
                prot = prot2
                seen_urls.add(url)
                if len(seen_urls) >= limit:
                    break
        return start + restore(prot, anchors) + end

    return re.sub(rf"(<{tag}[^>]*>)(.*?)(</{tag}>)", repl, html, flags=re.I | re.S)

def add_internal_links(html: str, primary_kw: str, max_links: int = 4) -> str:
    low = (primary_kw or "").lower()
    is_usa = any(k in low for k in COUNTRY_IS_US)

    pairs = list(INTERNAL_LINKS)
    if is_usa:
        pairs[0] = (pairs[0][0], "https://nnroad.com/usa/employer-of-record-eor-peo-geo-company/")
        pairs[1] = (pairs[1][0], "https://nnroad.com/usa/payroll-service-company/")

    seen = set()
    html = _apply_links_in_tag(html, "p", pairs, seen, max_links)
    if len(seen) < max_links:
        html = _apply_links_in_tag(html, "li", pairs, seen, max_links)
    if len(seen) < max_links:
        extra = [(r"\bUnited States\b|\bUSA\b|\bU\.S\.A\.?\b", "https://nnroad.com/usa/")]
        html = _apply_links_in_tag(html, "p", extra, seen, max_links)
    return html

# ---------------- finalize ----------------
def finalize_blog(primary_kw: str, secondary_kw: str = "") -> Tuple[str, str, str, str]:
    outline = generate_outline(primary_kw, secondary_kw)
    sections = outline.get("Table_of_Contents", [])
    keywords_line = outline.get("Refined_Keywords", "")
    html_bundle = generate_blog_html(sections, keywords_line)

    html = ensure_headings_and_ids(html_bundle["html"], sections)
    html = add_internal_links(html, primary_kw)

    return html, html_bundle["meta_title"], keywords_line, html_bundle["meta_description"]
