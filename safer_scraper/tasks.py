import sys
import subprocess
from datetime import timedelta

import redis
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils import timezone

from safer_scraper.models.scraper_job import ScraperJob

redis_client = redis.Redis(host="localhost", port=6379, db=0)
logger = get_task_logger(__name__)


def acquire_lock(key, timeout=900):
    """Prevent overlapping scraper runs."""
    lock = redis_client.lock(key, timeout=timeout)
    if lock.acquire(blocking=False):
        return lock
    return None


@shared_task
def run_scraper_job(job_id, start_id=None, hours=None):
    """
    Run the Scrapy-based Django management command in a subprocess to avoid
    Twisted reactor restart issues.
    """
    lock = acquire_lock("scraper-lock", timeout=900)
    if not lock:
        return "Skipped: scraper already running."

    try:
        cmd = [sys.executable, "manage.py", "run_scraper", f"--job-id={job_id}"]
        if start_id is not None:
            cmd.append(f"--start_id={start_id}")
        if hours is not None:
            cmd.append(f"--hours={hours}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=settings.BASE_DIR,
        )
        if result.stdout:
            logger.info("run_scraper stdout:\n%s", result.stdout.strip())
        if result.stderr:
            logger.error("run_scraper stderr:\n%s", result.stderr.strip())

        job = ScraperJob.objects.get(id=job_id)
        job.output_log = result.stdout[:50000]
        job.error_log = result.stderr[:50000]
        job.status = "completed" if result.returncode == 0 else "failed"
        job.save()

        return result.returncode
    finally:
        lock.release()


@shared_task
def run_daily_scraper():
    """
    Scheduled entrypoint: create a placeholder job and delegate to the main task.
    """
    job = ScraperJob.objects.create(
        start_id=0,
        hours_to_run=0.21,
        status="pending",
    )
    run_scraper_job.delay(job.id)


def _run_missing_docs_for_date(target_date, lock_name):
    lock = acquire_lock(lock_name, timeout=900)
    if not lock:
        return "Skipped: scraper already running."
    try:
        cmd = [sys.executable, "manage.py", "run_missing_docs"]
        if target_date:
            cmd.append(f"--target-date={target_date.isoformat()}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=settings.BASE_DIR,
        )
        if result.stdout:
            logger.info("Missing docs stdout (%s):\n%s", target_date or "default", result.stdout.strip())
        else:
            logger.info("Missing docs stdout (%s): [empty]", target_date or "default")
        if result.stderr:
            logger.error("Missing docs stderr (%s):\n%s", target_date or "default", result.stderr.strip())
        return result.returncode
    finally:
        lock.release()


@shared_task
def run_missing_docs_job():
    """Morning task: fetch yesterday's missing DOT numbers."""
    target_date = timezone.now().date() - timedelta(days=1)
    return _run_missing_docs_for_date(target_date, "missing-docs-yesterday-lock")


@shared_task
def run_missing_docs_today_job():
    """Evening task: fetch today's missing DOT numbers."""
    target_date = timezone.now().date()
    return _run_missing_docs_for_date(target_date, "missing-docs-today-lock")
