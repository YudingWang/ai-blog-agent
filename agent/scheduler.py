from __future__ import annotations
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from .agent_runner import run_once
from .config import settings

def start_scheduler():
    cron = settings.schedule_cron.split()
    if len(cron) != 5:
        raise ValueError("SCHEDULE_CRON must have 5 fields like: '0 10 * * *'")
    minute, hour, dom, month, dow = cron[0], cron[1], cron[2], cron[3], cron[4]
    scheduler = BlockingScheduler()
    scheduler.add_job(run_once, trigger=CronTrigger(minute=minute, hour=hour, day=dom, month=month, day_of_week=dow), name="blog-agent")
    print(f"Scheduler started with cron: {settings.schedule_cron}")
    scheduler.start()
