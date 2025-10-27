from django.shortcuts import render
from .models import SaferData

def safer_data_view(request):
    rows = SaferData.objects.all()
    return render(request, "listings/safer_data.html", {"rows": rows})