import csv
from django.db.models import Q
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.paginator import Paginator
from safer_scraper.models import SaferData
from django.core.management import call_command
from safer_scraper.models.scraper_job import ScraperJob
from .forms import ScraperStartForm
from django.contrib import messages
from threading import Thread


def build_filtered_queryset(request, base_queryset=None):
    """Reusable filtering logic for search and CSV export."""
    if base_queryset is None:
        base_queryset = SaferData.objects.all()

    query = request.GET.get('q', '').strip()
    dot_from = request.GET.get('dot_from')
    dot_to = request.GET.get('dot_to')

    if query:
        filters = Q()
        if query.isdigit():
            filters |= (
                Q(dot_number=int(query))
                | Q(zipcode=int(query))
                | Q(phone=int(query))
            )
        else:
            filters |= (
                Q(legal_name__icontains=query)
                | Q(physical_address__icontains=query)
                | Q(mailing_code__icontains=query)
                | Q(operating_status__icontains=query)
                | Q(power_units__icontains=query)
                | Q(drivers__icontains=query)
                | Q(date_filed__icontains=query)
                | Q(email__icontains=query)
                | Q(fetched_at__icontains=query)
            )
        base_queryset = base_queryset.filter(filters)

    if dot_from and dot_to:
        base_queryset = base_queryset.filter(dot_number__range=[dot_from, dot_to])
    elif dot_from:
        base_queryset = base_queryset.filter(dot_number__gte=dot_from)
    elif dot_to:
        base_queryset = base_queryset.filter(dot_number__lte=dot_to)

    return base_queryset


def safer_data_view(request):
    data = build_filtered_queryset(request)
    paginator = Paginator(data, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'data': page_obj,
        'query': request.GET.get('q', '').strip(),
        'dot_from': request.GET.get('dot_from'),
        'dot_to': request.GET.get('dot_to'),
    }
    return render(request, 'safer_app_listing/safer_data.html', context)


def download_csv(request):
    safer_data = build_filtered_queryset(request)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="safer_data.csv"'
    writer = csv.writer(response)

    writer.writerow([
        'dot_number', 'legal_name', 'physical_address', 'zipcode',
        'mailing_code', 'phone', 'operating_status', 'power_units',
        'drivers', 'date_filed', 'email'
    ])

    for data in safer_data:
        writer.writerow([
            data.dot_number, data.legal_name, data.physical_address,
            data.zipcode, data.mailing_code, data.phone, data.operating_status,
            data.power_units, data.drivers, data.date_filed, data.email
        ])

    return response


def run_scraper_background(job_id, start_id, hours):
    """Run scraper in background thread for non-blocking execution."""
    job = ScraperJob.objects.get(id=job_id)

    try:
        job.mark_as_running()

        # Run actual scraper
        call_command("run_scraper", start_id=start_id, hours=hours)

        job.mark_as_completed()
    except Exception as e:
        job.mark_as_failed(str(e))


def start_scraper_view(request):
    """Start scraper page: submit form and redirect immediately to status page."""
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
    return render(request, "scraper/scraper_status.html", {"jobs": jobs})
