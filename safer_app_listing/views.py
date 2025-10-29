from django.shortcuts import render
from django.db.models import Q
from django.core.paginator import Paginator
from .models import SaferData


def safer_data_view(request):
    query = request.GET.get('q', '').strip()
    dot_from = request.GET.get('dot_from')
    dot_to = request.GET.get('dot_to')

    data = SaferData.objects.all()

    # --- Apply global search ---
    if query:
        data = data.filter(
            Q(id__icontains=query) |
            Q(dot_number__icontains=query) |
            Q(legal_name__icontains=query) |
            Q(physical_address__icontains=query) |
            Q(zipcode__icontains=query) |
            Q(mailing_code__icontains=query) |
            Q(phone__icontains=query) |
            Q(operating_status__icontains=query) |
            Q(power_units__icontains=query) |
            Q(drivers__icontains=query) |
            Q(date_filed__icontains=query) |
            Q(fetched_at__icontains=query)
        )

    # --- Apply DOT number range filter ---
    if dot_from and dot_to:
        data = data.filter(dot_number__gte=dot_from, dot_number__lte=dot_to)
    elif dot_from:
        data = data.filter(dot_number__gte=dot_from)
    elif dot_to:
        data = data.filter(dot_number__lte=dot_to)

    # --- Pagination (50 items per page) ---
    paginator = Paginator(data, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'data': page_obj,
        'query': query,
        'dot_from': dot_from,
        'dot_to': dot_to,
    }
    return render(request, 'safer_app_listing/safer_data.html', context)