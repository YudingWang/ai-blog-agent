from __future__ import annotations
import os, io, base64, mimetypes
from typing import Optional
from PIL import Image
import requests
from .config import settings

def _auth_header() -> dict:
    creds = f"{settings.wp_user}:{settings.wp_app_password}".encode("utf-8")
    return {"Authorization": f"Basic {base64.b64encode(creds).decode('utf-8')}"}

def optimize_image(image_path: str, target_size_kb: int = 100, max_width: int = 1200, quality: int = 85) -> str:
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
    out_path = image_path.replace(".", "_optimized.")
    import io
    img_bytes = io.BytesIO()
    image.save(img_bytes, format=img_format, quality=quality)
    while len(img_bytes.getvalue()) > target_size_kb * 1024 and quality > 10:
        quality -= 5
        img_bytes = io.BytesIO()
        image.save(img_bytes, format=img_format, quality=quality)
    with open(out_path, "wb") as f:
        f.write(img_bytes.getvalue())
    return out_path

def upload_image(image_path: str) -> Optional[int]:
    endpoint = f"{settings.wp_base_url}/wp-json/wp/v2/media"
    files = {}
    opt_path = optimize_image(image_path)
    mime_type, _ = mimetypes.guess_type(opt_path)
    if mime_type is None:
        mime_type = "image/png"
    files["file"] = (os.path.basename(opt_path), open(opt_path, "rb"), mime_type)
    headers = {"User-Agent": "ai-blog-agent/1.0"}
    headers.update(_auth_header())
    r = requests.post(endpoint, headers=headers, files=files, timeout=60)
    if r.status_code == 201:
        return r.json().get("id")
    raise RuntimeError(f"Upload failed {r.status_code}: {r.text}")

def publish_post(title: str, content_html: str, meta_title: str, meta_description: str, focus_keyword: str, image_path: Optional[str] = None, alt_text: Optional[str] = None) -> int:
    endpoint = f"{settings.wp_base_url}/wp-json/wp/v2/posts"
    headers = {"Content-Type": "application/json", "User-Agent": "ai-blog-agent/1.0"}
    headers.update(_auth_header())
    featured_media_id = None
    if image_path:
        media_id = upload_image(image_path)
        if media_id:
            featured_media_id = media_id
            try:
                requests.post(
                    f"{settings.wp_base_url}/wp-json/wp/v2/media/{media_id}",
                    headers=headers,
                    json={"alt_text": alt_text or meta_description or title},
                    timeout=30,
                )
            except Exception:
                pass
    payload = {
        "title": title,
        "content": content_html,
        "status": "publish",
        "meta": {
            "rank_math_focus_keyword": focus_keyword,
            "rank_math_description": meta_description,
            "rank_math_title": meta_title
        },
    }
    if featured_media_id:
        payload["featured_media"] = featured_media_id
    r = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    if r.status_code in (200,201):
        return r.json().get("id")
    raise RuntimeError(f"Post publish failed {r.status_code}: {r.text}")
