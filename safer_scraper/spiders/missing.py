from datetime import datetime, timedelta

from django.utils import timezone

from .base import SaferSpider
from ..utils import get_missing_dot_numbers_for_date


class MissingDocsSpider(SaferSpider):
    """
    Spider dedicated to re-fetching missing DOT numbers for a specific date.
    Extends the core SaferSpider so it reuses parsing, pipelines, and request
    handling logic while supplying its own ID source.
    """

    name = "safer_missing_yesterday"

    def __init__(self, *args, **kwargs):
        target_date = kwargs.pop("target_date", None)
        self.target_date = self._resolve_target_date(target_date)
        self.missing_ids = self._load_missing_ids()
        super().__init__(*args, **kwargs)

    def _resolve_target_date(self, target_date):
        """Return a date object for whichever input is provided."""
        if target_date is None:
            return timezone.now().date() - timedelta(days=1)
        if isinstance(target_date, str):
            return datetime.strptime(target_date, "%Y-%m-%d").date()
        return target_date

    def _load_missing_ids(self):
        """Fetch and cache the list of DOT numbers to backfill."""
        return list(get_missing_dot_numbers_for_date(self.target_date))

    def start_requests(self):
        has_any = False
        for code in self.missing_ids:
            has_any = True
            if self.stop_if_deadline("start_requests"):
                return
            yield self._build_request(code)
        if not has_any:
            self.logger.info(
                "✅ No missing DOT numbers detected for %s.",
                self.target_date.isoformat(),
            )
