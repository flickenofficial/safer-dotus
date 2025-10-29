import csv
from django.db.models import Q
from django.shortcuts import render
from django.http import HttpResponse
from django.core.paginator import Paginator
from .models import SaferData


def build_filtered_queryset(request, base_queryset=None):
    """Reusable filtering logic for search and CSV export."""
    if base_queryset is None:
        base_queryset = SaferData.objects.all()

    query = request.GET.get('q', '').strip()
    dot_from = request.GET.get('dot_from')
    dot_to = request.GET.get('dot_to')

    # Text or numeric search
    if query:
        filters = Q()
        if query.isdigit():
            filters |= (
                Q(id=int(query))
                | Q(dot_number=int(query))
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
                | Q(fetched_at__icontains=query)
            )
        base_queryset = base_queryset.filter(filters)

    # DOT range filter
    if dot_from and dot_to:
        base_queryset = base_queryset.filter(dot_number__range=[dot_from, dot_to])
    elif dot_from:
        base_queryset = base_queryset.filter(dot_number__gte=dot_from)
    elif dot_to:
        base_queryset = base_queryset.filter(dot_number__lte=dot_to)

    return base_queryset


def safer_data_view(request):
    """Main view: shows filtered data with pagination."""
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
    """Allows downloading the filtered data as a CSV file."""
    safer_data = build_filtered_queryset(request)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="safer_data.csv"'
    writer = csv.writer(response)

    writer.writerow([
        'id', 'dot_number', 'legal_name', 'physical_address', 'zipcode',
        'mailing_code', 'phone', 'operating_status', 'power_units',
        'drivers', 'date_filed', 'fetched_at'
    ])

    for data in safer_data:
        writer.writerow([
            data.id, data.dot_number, data.legal_name, data.physical_address,
            data.zipcode, data.mailing_code, data.phone, data.operating_status,
            data.power_units, data.drivers, data.date_filed, data.fetched_at
        ])

    return response
