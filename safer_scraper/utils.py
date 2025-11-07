from django.db import models, transaction
from django.utils import timezone
from .models import SaferState
from asgiref.sync import sync_to_async


def get_last_fetched_id():
    """Get the latest fetched ID."""
    try:
        return (
                SaferState.objects.filter(status="fetched").aggregate(last_id=models.Max("id"))["last_id"] or 0

                or 0
        )
    except Exception:
        return 0


def get_last_fetched_id_last_time():
    today = timezone.now().date()
    return (
            SaferState.objects.filter(status="fetched", last_checked__lt=today).aggregate(last_id=models.Max("id"))[
                "last_id"]
            or 0
    )


def get_recent_ids(recent_range):
    """Get IDs from the given range that haven't been fetched yet."""
    try:
        if not recent_range:
            return []
        return list(
            SaferState.objects
            .filter(id__in=recent_range)
            .exclude(status="fetched")
            .values_list("id", flat=True)
        )
    except Exception:
        return recent_range


def get_backfill_ids_since_last_fetched(last_fetched_id):
    """Get IDs with no_data status after last fetched ID."""
    try:
        return list(
            SaferState.objects
            .filter(status="no_data", id__gt=last_fetched_id)
            .order_by("id")
            .values_list("id", flat=True)
        )
    except Exception:
        return []


@sync_to_async
@transaction.atomic
def mark_no_data(id_, timestamp):
    try:
        updated = (
            SaferState.objects
            .filter(id=id_)
            .update(status="no_data", last_checked=timestamp)
        )
        if not updated:
            SaferState.objects.bulk_create(
                [
                    SaferState(
                        id=id_,
                        status="no_data",
                        last_checked=timestamp,
                        retry_count=0,
                    )
                ],
                ignore_conflicts=True,
            )
    except Exception as e:
        print(f"[mark_no_data] error: {e}")


@sync_to_async
@transaction.atomic
def mark_fetched(id_, timestamp):
    try:
        updated = (
            SaferState.objects
            .filter(id=id_)
            .update(status="fetched", last_checked=timestamp, retry_count=0)
        )
        if not updated:
            SaferState.objects.bulk_create(
                [
                    SaferState(
                        id=id_,
                        status="fetched",
                        last_checked=timestamp,
                        retry_count=0,
                    )
                ],
                ignore_conflicts=True,
            )
    except Exception as e:
        print(f"[mark_fetched] error: {e}")