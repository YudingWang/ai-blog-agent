from __future__ import annotations
import os, io, base64, mimetypes, random, glob, re
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import requests
from .config import settings

def _auth_header() -> dict:
    creds = f"{settings.wp_user}:{settings.wp_app_password}".encode("utf-8")
    return {"Authorization": f"Basic {base64.b64encode(creds).decode('utf-8')}"}

def _slugify(s: str) -> str:
    s = re.sub(r"<.*?>", "", s or "")
    s = s.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s[:180] or "post"

def _pick_random_image() -> Optional[str]:
    base = os.getenv("IMAGE_DIR") or getattr(settings, "image_dir", None)
    if not base:
        base = Path(__file__).resolve().parents[1] / "images"
    base = Path(base)
    if not base.exists():
        return None
    candidates = []
    for ext in ("*.jpg","*.jpeg","*.png","*.webp"):
        candidates += glob.glob(str(base / ext))
    return random.choice(candidates) if candidates else None

def optimize_image(image_path: str, target_size_kb: int = 200, max_width: int = 1600, quality: int = 85) -> str:
    if not os.path.exists(image_path):
        raise FileNotFoundError(image_path)
    original_size_kb = os.path.getsize(image_path) / 1024
    out_path = image_path
    if original_size_kb <= target_size_kb:
        return out_path
    image = Image.open(image_path)
    if image.width > max_width:
        new_height = int((max_width / image.width) * image.height)
        image = image.resize((max_width, new_height))
    img_format = "JPEG" if image.format != "JPEG" else image.format
    if image.format == "PNG":
        image = image.convert("RGB")
    root, ext = os.path.splitext(image_path)
    out_path = f"{root}_optimized{ext}"
    img_bytes = io.BytesIO()
    image.save(img_bytes, format=img_format, quality=quality)
    while len(img_bytes.getvalue()) > target_size_kb * 1024 and quality > 10:
        quality -= 5
        img_bytes = io.BytesIO()
        image.save(img_bytes, format=img_format, quality=quality)
    with open(out_path, "wb") as f:
        f.write(img_bytes.getvalue())
    return out_path

def upload_image(image_path: str) -> Optional[Tuple[int, str]]:
    endpoint = f"{settings.wp_base_url}/wp-json/wp/v2/media"
    opt_path = optimize_image(image_path)
    mime_type, _ = mimetypes.guess_type(opt_path)
    if mime_type is None:
        mime_type = "image/jpeg"
    headers = {"User-Agent": "ai-blog-agent/1.0"}
    headers.update(_auth_header())
    with open(opt_path, "rb") as fh:
        files = {"file": (os.path.basename(opt_path), fh, mime_type)}
        r = requests.post(endpoint, headers=headers, files=files, timeout=60)
    if r.status_code == 201:
        j = r.json()
        return j.get("id"), j.get("source_url")
    raise RuntimeError(f"Upload failed {r.status_code}: {r.text}")

def _update_rankmath_meta(base: str, headers: dict, post_id: int,
                          meta_title: str, meta_description: str, focus_keyword: str) -> bool:
    """优先用 Rank Math 自己的 REST 端点；不同版本参数名不一致，做多形态尝试。"""
    url = f"{base}/wp-json/rankmath/v1/updateMeta"
    variants = [
        # 1) 部分版本：带前缀键名
        {"objectID": post_id, "objectType": "post",
         "meta": {"rank_math_title": meta_title,
                  "rank_math_description": meta_description,
                  "rank_math_focus_keyword": focus_keyword}},
        # 2) 另一种：不带前缀键名
        {"objectID": post_id, "objectType": "post",
         "meta": {"title": meta_title,
                  "description": meta_description,
                  "focus_keyword": focus_keyword}},
        # 3) 旧形态：post_id
        {"post_id": post_id,
         "meta": {"rank_math_title": meta_title,
                  "rank_math_description": meta_description,
                  "rank_math_focus_keyword": focus_keyword}},
        {"post_id": post_id,
         "meta": {"title": meta_title,
                  "description": meta_description,
                  "focus_keyword": focus_keyword}},
    ]
    for payload in variants:
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=30)
            if r.status_code in (200, 201):
                return True
        except Exception:
            pass
    return False

def publish_post(
    title: str,
    content_html: str,
    meta_title: str,
    meta_description: str,
    focus_keyword: str,
    image_path: Optional[str] = None,
    alt_text: Optional[str] = None,
    status: str = "publish",
) -> int:
    base = settings.wp_base_url.rstrip("/")
    headers = {"Content-Type": "application/json", "User-Agent": "ai-blog-agent/1.0"}
    headers.update(_auth_header())

    primary_kw = (focus_keyword or "").strip()

    # 去掉正文里的所有 <img>，避免与特色图重复
    content_html = re.sub(r"(?is)<img[^>]*>", "", content_html)

    # 随机图
    if not image_path:
        image_path = _pick_random_image()

    featured_media_id = None
    if image_path:
        media = upload_image(image_path)
        if media:
            media_id, _media_url = media
            featured_media_id = media_id
            try:
                alt_val = f"{primary_kw or title} - {alt_text or meta_description or ''}".strip()
                requests.post(
                    f"{base}/wp-json/wp/v2/media/{media_id}",
                    headers=headers,
                    json={"alt_text": alt_val, "caption": alt_val, "description": alt_val},
                    timeout=30,
                )
            except Exception:
                pass

    # 1) 先创建草稿（带 slug/特色图）
    create_payload = {
        "title": title,                       # 已用 SEO 标题
        "slug": _slugify(primary_kw or title),
        "content": content_html,
        "status": "draft",
    }
    if featured_media_id:
        create_payload["featured_media"] = featured_media_id

    r = requests.post(f"{base}/wp-json/wp/v2/posts", headers=headers, json=create_payload, timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Post create failed {r.status_code}: {r.text}")
    post_id = int(r.json().get("id"))

    # 2) 尝试通过 Rank Math 端点写入 Meta（优先）
    _ = _update_rankmath_meta(base, headers, post_id, meta_title, meta_description, primary_kw)

    # 3) 同时再用 WP 官方 posts/{id} 写一次（有的站点注册了 meta，会成功）
    if primary_kw and primary_kw.lower() not in (meta_title or "").lower():
        meta_title = f"{primary_kw} | NNRoad Guide"
    if primary_kw and primary_kw.lower() not in (meta_description or "").lower():
        meta_description = f"{primary_kw} — {meta_description or ''}"
    meta_description = (meta_description or "")[:160]

    meta_payload = {
        "meta": {
            "rank_math_title": meta_title or title,
            "rank_math_description": meta_description,
            "rank_math_focus_keyword": primary_kw,
        },
        "status": status,   # 同时发布
    }
    r2 = requests.post(f"{base}/wp-json/wp/v2/posts/{post_id}", headers=headers, json=meta_payload, timeout=30)
    if r2.status_code not in (200, 201):
        # 即使这里失败，文章已创建；抛错太激进。改为再发布一次以确保可见。
        requests.post(f"{base}/wp-json/wp/v2/posts/{post_id}", headers=headers, json={"status": status}, timeout=30)

    return post_id
