from celery import shared_task
from django.core.management import call_command
from safer_scraper.models.scraper_job import ScraperJob


@shared_task
def run_scraper_job(job_id, start_id=None, hours=None):
    """
    Execute the Django management command in a Celery worker so web requests stay fast.
    """
    options = {"job_id": job_id}
    if start_id is not None:
        options["start_id"] = start_id
    if hours is not None:
        options["hours"] = hours
    call_command("run_scraper", **options)


@shared_task
def run_daily_scraper():
    """
    Scheduled entrypoint: create a placeholder job and delegate to the main task.
    """
    job = ScraperJob.objects.create(
        start_id=0,
        hours_to_run=0,
        status="pending",
    )
    run_scraper_job.delay(job.id)
    return f"Scraper queued for job {job.id}"
