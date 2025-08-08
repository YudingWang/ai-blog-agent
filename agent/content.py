from __future__ import annotations
import time
import json
from typing import Tuple, Dict
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

def _llm(model_name: str = "gpt-4o-mini", temperature: float = 0.2) -> ChatOpenAI:
    return ChatOpenAI(model=model_name, temperature=temperature)

def generate_outline(primary_kw: str, secondary_kw: str = "") -> Dict:
    schema = [
        ResponseSchema(name="Recommended_Long-Tail_Keywords", description="A list of recommended Long-Tail Keywords"),
        ResponseSchema(name="Title", description="A title for the article"),
        ResponseSchema(name="Table_of_Contents", description="JSON list of chapters with fields: chapter_title, recommended_keywords, highlights"),
        ResponseSchema(name="Refined_Keywords", description="One line string containing primary and long-tail, joined by comma")
    ]
    output_parser = StructuredOutputParser.from_response_schemas(schema)
    format_instructions = output_parser.get_format_instructions()
    template = """
    I intend to write an SEO-friendly article (optimized for Google, Bing, and AI search engines) with four chapters for my website, www.nnroad.com.
    The blog should recommend NNRoad company and services at the end, or mention NNRoad in local/global company ranks.
    Primary Keyword: '{Primary}'
    Secondary Keywords: '{Secondary}'
    Tasks:
    1. Recommend long-tail keywords based on the primary and secondary keywords.
    2. Suggest a title for the article which contains the exact '{Primary}' keyword, without altering its grammar or inserting extra words.
    3. The title must include 1 number and 1 power word, and carry a positive or negative sentiment.
    4. Create a table of contents (as JSON) for four chapters. Ensure:
       - 50% around introduction and American/California-related policies
       - 30% around NNRoad recommendation or NNRoad service introduction
       Each chapter must include: 'chapter_title', 'recommended_keywords', 'highlights'.
    5. Keep everything in English and keep the company name exactly 'NNRoad'.
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
            return json.loads(resp.content)
        except Exception as e:
            last_err = e
            time.sleep(1.2)
    raise RuntimeError(f"Failed to generate outline: {last_err}")

def generate_blog_html(sections_json: Dict, keywords_line: str) -> Dict[str, str]:
    schema = [
        ResponseSchema(name="html_content", description="The refined HTML content using h2 and p tags"),
        ResponseSchema(name="Meta_title", description="A Meta_title for the article"),
        ResponseSchema(name="Meta_description", description="A Meta description for the article (<=140 chars)")
    ]
    output_parser = StructuredOutputParser.from_response_schemas(schema)
    format_instructions = output_parser.get_format_instructions()
    template = """
    Here are HTML contents of chapters for a blog on www.nnroad.com: '{sections}'.
    Please refine it into a complete HTML file based on the following requirements:
    1. Retain the existing title and content, but rewrite duplicates for readability.
    2. Do not include <h1> tags; use <h2> for section titles.
    3. Include an introduction at the beginning, containing exactly one of keywords in '{keywords}'.
    4. Add a conclusion at the end with the CTA: "If you have questions, please contact us at contact@nnroad.com."
    5. Generate a separate meta title.
    6. Generate a separate meta description for SEO (<=140 chars) that contains exactly one of '{keywords}'.
    7. Keep the company name exactly 'NNRoad'.
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
            data = json.loads(resp.content)
            return {
                "html": data.get("html_content",""),
                "meta_title": data.get("Meta_title",""),
                "meta_description": data.get("Meta_description",""),
            }
        except Exception as e:
            last_err = e
            time.sleep(1.2)
    raise RuntimeError(f"Failed to generate blog html: {last_err}")

def finalize_blog(primary_kw: str, secondary_kw: str = "") -> Tuple[str, str, str, str]:
    outline = generate_outline(primary_kw, secondary_kw)
    sections = outline.get("Table_of_Contents", [])
    keywords_line = outline.get("Refined_Keywords", "")
    html_bundle = generate_blog_html(sections, keywords_line)
    return html_bundle["html"], outline.get("Title",""), keywords_line, html_bundle["meta_description"]
