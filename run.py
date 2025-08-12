from __future__ import annotations
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)
import argparse
from agent.agent_runner import run_once
from agent.scheduler import start_scheduler
from agent.config import settings
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description="AI Blog Agent (LangChain)")
    parser.add_argument("--keyword", help="Primary keyword to write about. If omitted, agent will choose one from KEYWORDS_FILE.")
    parser.add_argument("--secondary", default="", help="Secondary keyword (optional).")
    parser.add_argument("--image", default="", help="Path to image to upload as featured image (optional).")
    parser.add_argument("--schedule", action="store_true", help="Start scheduler (uses SCHEDULE_CRON).")
    args = parser.parse_args()

    if args.schedule or settings.scheduler_enabled:
        start_scheduler()
        return

    post_id = run_once(primary_kw=args.keyword, secondary_kw=args.secondary, image_path=args.image or None)
    print(f"Done. Post ID: {post_id}")

if __name__ == "__main__":
    main()









#
# # run.py
# import argparse
# import os
# import pandas as pd
# from agent.agent_runner import run_once

#
# def main():
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--keyword", help="single keyword string", default=None)
#     parser.add_argument("--secondary", help="secondary keyword", default=None)
#     parser.add_argument("--image", help="image path", default=None)
#     parser.add_argument("--excel", help="path to xlsx with ONE column of keywords", default=None)
#     args = parser.parse_args()
#
#     # 情况 A：传入 excel，按行跑
#     if args.excel:
#         if not os.path.exists(args.excel):
#             raise FileNotFoundError(f"Excel not found: {args.excel}")
#
#         # 读取只有一列的表：不管有没有列名，都取第一列
#         df = pd.read_excel(args.excel, header=0)  # 若无表头也可 header=None
#         first_col = df.columns[0]  # 只有一列就拿第一个
#         # 清洗：去空值、去重、去两端空格
#         keywords = (
#             df[first_col]
#             .dropna()
#             .astype(str)
#             .map(str.strip)
#             .replace("", pd.NA)
#             .dropna()
#             .drop_duplicates()
#             .tolist()
#         )
#
#         print(f"[INFO] Loaded {len(keywords)} keywords from {args.excel}")
#         results = []
#         for i, kw in enumerate(keywords, 1):
#             print(f"[{i}/{len(keywords)}] Running for keyword: {kw!r}")
#             try:
#                 post_id = run_once(primary_kw=kw, secondary_kw=None, image_path=args.image or None)
#                 results.append({"keyword": kw, "post_id": post_id, "status": "ok"})
#             except Exception as e:
#                 print(f"[ERROR] {kw!r} failed: {e}")
#                 results.append({"keyword": kw, "post_id": None, "status": f"error: {e}"})
#
#         # 可选：把结果写回同目录
#         out_csv = os.path.splitext(args.excel)[0] + "_results.csv"
#         pd.DataFrame(results).to_csv(out_csv, index=False)
#         print(f"[DONE] Results saved to {out_csv}")
#         return
#
#     # 情况 B：单个关键字跑一次（原有逻辑）
#     if not args.keyword:
#         raise SystemExit("Please provide --keyword or --excel")
#     post_id = run_once(primary_kw=args.keyword, secondary_kw=args.secondary, image_path=args.image or None)
#     print(f"[DONE] post_id: {post_id}")
#
# if __name__ == "__main__":
#     main()
