from celery import shared_task
from safer_scraper.views import run_scraper_background
from safer_scraper.models.scraper_job import ScraperJob
import threading

@shared_task
def run_daily_scraper():
    """
    Celery task that triggers the scraper safely — creates a job placeholder so run_scraper_background works.
    """

    print("🚀 Celery: triggering scraper run...")

    # Create a lightweight job record (just to get a valid job_id)
    job = ScraperJob.objects.create(
        start_id=0,
        hours_to_run=0,
        status="pending"
    )

    # Run the scraper thread with this job id
    thread = threading.Thread(target=run_scraper_background, args=(job.id, None, None))
    thread.start()

    print(f"✅ Celery triggered scraper for job {job.id}")
    return f"Scraper started for job {job.id}"
