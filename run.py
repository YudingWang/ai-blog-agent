from __future__ import annotations
import argparse
from agent.agent_runner import run_once
from agent.scheduler import start_scheduler
from agent.config import settings

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
