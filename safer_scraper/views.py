from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.management import call_command
from threading import Thread
from .models.scraper_job import ScraperJob
from safer_scraper.forms import ScraperStartForm
from django.utils.timezone import localtime


def run_scraper_background(job_id, start_id, hours):
    """Run scraper in background thread for non-blocking execution."""
    job = ScraperJob.objects.get(id=job_id)

    try:
        job.mark_as_running()

        # Run actual scraper
        call_command("run_scraper", start_id=start_id, hours=hours, job_id=job_id)

        job.mark_as_completed()
    except Exception as e:
        job.mark_as_failed(str(e))


def start_scraper_view(request):
    """Start scraper page: submit form and redirect immediately to status page."""

    # Check if any scraper is already running or pending
    running_job_exists = ScraperJob.objects.filter(status__in=['pending', 'running']).exists()

    if running_job_exists:
        messages.warning(request, "You are not allowed to run more than 1 scraper at a time.")
        form = ScraperStartForm()  # show empty form
        return render(request, 'scraper/start_scraper.html', {'form': form})

    if request.method == 'POST':
        form = ScraperStartForm(request.POST)
        if form.is_valid():
            start_id = form.cleaned_data['start_id']
            hours = form.cleaned_data['hours']

            # Create job in DB
            job = ScraperJob.objects.create(
                start_id=start_id,
                hours_to_run=hours,
                status='pending'
            )

            # Run scraper in background thread
            Thread(target=run_scraper_background, args=(job.id, start_id, hours)).start()

            messages.success(request, 'Scraper started successfully.')
            return redirect('scraper_status')
        else:
            messages.error(request, 'Please provide valid inputs.')
    else:
        form = ScraperStartForm()

    return render(request, 'scraper/start_scraper.html', {'form': form})


def scraper_status_view(request):
    """Display all scraper jobs and their statuses."""
    jobs = ScraperJob.objects.all().order_by("-id")
    for job in jobs:
        if job.started_at:
            job.started_at_local = localtime(job.started_at)
        if job.completed_at:
            job.completed_at_local = localtime(job.completed_at)

    return render(request, "scraper/scraper_status.html", {"jobs": jobs})
