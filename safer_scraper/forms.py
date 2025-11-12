from django import forms
from safer_scraper.models.scraper_job import ScraperJob

class ScraperStartForm(forms.Form):
    start_id = forms.IntegerField(
        required=True,
        label="DOT Number",
        min_value=1,
        error_messages={
            "required": "DOT Number is required.",
            "invalid": "DOT Number must be a valid number.",
            "min_value": "DOT Number must be greater than 0.",
        }
    )

    hours = forms.FloatField(
        required=True,
        label="Hours to run",
        min_value=0.01,
        error_messages={
            "required": "Hours value is required.",
            "invalid": "Hours must be a valid number.",
            "min_value": "Hours must be greater than 0.",
        }
    )

    def clean_start_id(self):
        start_id = self.cleaned_data.get("start_id")

        # if ScraperJob.objects.filter(start_id=start_id).exists():
        #     raise forms.ValidationError(
        #         f"DOT Number {start_id} exist in the database."
        #     )

        return start_id
