from celery import shared_task
from safer_scraper.models.scraper_job import ScraperJob
from safer_scraper.views import run_scraper_background
from .utils import (
    get_last_fetched_id
)
import threading

@shared_task
def run_daily_scraper(start_id=None, hours=None):
    """Run scraper daily at 8 AM Mountain Time, fetching IDs dynamically."""

    # Check if another scraper is already running or pending
    running_jobs = ScraperJob.objects.filter(status__in=["pending", "running"])
    if running_jobs.exists():
        print("⚠️ Scraper not started: another job is already running or pending.")
        return "Skipped: Another scraper is running"

    # Determine start_id dynamically
    last_fetched_id = get_last_fetched_id()
    start_id = int(start_id) if start_id else last_fetched_id + 1
    hours = float(hours) if hours else 4.0  # default 1 hour if not provided

    # Create a new ScraperJob
    job = ScraperJob.objects.create(
        start_id=start_id,
        hours_to_run=hours,
        status="pending"
    )

    # Run scraper in a background thread
    thread = threading.Thread(target=run_scraper_background, args=(job.id, start_id, hours))
    thread.start()

    print(f"✅ Scraper started for job {job.id} (start_id={start_id}, hours={hours})")
    return f"Scraper started for job {job.id} (start_id={start_id}, hours={hours})"
