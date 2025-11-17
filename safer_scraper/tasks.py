import sys
import subprocess
from celery import shared_task
from django.conf import settings
from safer_scraper.models.scraper_job import ScraperJob
import redis

# Optional Redis lock to prevent overlapping runs
redis_client = redis.Redis(host='localhost', port=6379, db=0)


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
        # Build the command
        cmd = [sys.executable, "manage.py", "run_scraper", f"--job-id={job_id}"]
        if start_id is not None:
            cmd.append(f"--start_id={start_id}")
        if hours is not None:
            cmd.append(f"--hours={hours}")

        # Run the command in a subprocess
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=settings.BASE_DIR
        )

        # Update ScraperJob record
        job = ScraperJob.objects.get(id=job_id)
        job.output_log = result.stdout[:50000]  # limit size
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
        hours_to_run=0.21,  # ~12 minutes
        status="pending",
    )
    run_scraper_job.delay(job.id)
