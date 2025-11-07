from django import forms

class ScraperStartForm(forms.Form):
    start_id = forms.IntegerField(label="DOT Number", required=True)
    hours = forms.FloatField(
        label="Hours (can be fractional, e.g., 0.25 for 15 minutes)",
        min_value=0.01,  # cannot be zero or negative
        required=True,
    )
