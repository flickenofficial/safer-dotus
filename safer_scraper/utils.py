import asyncio
from datetime import timedelta
from typing import Iterable

from django.db import models, transaction
from django.utils import timezone
from asgiref.sync import async_to_sync, sync_to_async
from .models import SaferState, SaferData


def get_last_fetched_id():
    """Get the latest fetched ID."""
    try:
        return (
                SaferState.objects.filter(status="fetched").aggregate(last_id=models.Max("id"))["last_id"] or 0

                or 0
        )
    except Exception:
        return 0


def get_proxies():
    with open("safer_scraper/proxies.txt", mode='r') as f:
        raw_proxies = f.readlines()

    proxies = list()
    for proxy in raw_proxies:
        proxy = proxy.strip().split(':')
        proxies.append(
            f'http://{proxy[2]}:{proxy[3]}@{proxy[0]}:{proxy[1]}'
        )

    return proxies


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


def _iter_missing_numbers(min_dot: int, max_dot: int, existing_iter: Iterable[int]) -> Iterable[int]:
    """
    Stream numbers between min/max that are absent from the existing iterator.
    """
    if min_dot is None or max_dot is None:
        return iter(())

    def generator():
        next_expected = min_dot
        for dot in existing_iter:
            dot = int(dot)
            while next_expected < dot and next_expected <= max_dot:
                yield next_expected
                next_expected += 1
            if dot == next_expected:
                next_expected += 1
        while next_expected <= max_dot:
            yield next_expected
            next_expected += 1

    return generator()


def get_missing_dot_numbers_for_date(target_date, chunk_size: int = 10000) -> Iterable[int]:
    """
    Yield DOT numbers for the provided date that are missing from SaferData between the
    observed min/max range. Uses streaming iteration so 1M+ ranges are OK.
    """
    try:
        queryset = SaferData.objects.filter(fetched_at__date=target_date)
        bounds = queryset.aggregate(
            min_dot=models.Min("dot_number"),
            max_dot=models.Max("dot_number"),
        )
        min_dot = bounds.get("min_dot")
        max_dot = bounds.get("max_dot")
        if min_dot is None or max_dot is None:
            return iter(())
        existing_iter = (
            queryset.order_by("dot_number")
            .values_list("dot_number", flat=True)
            .iterator(chunk_size=chunk_size)
        )
        return _iter_missing_numbers(min_dot, max_dot, existing_iter)
    except Exception:
        return iter(())


@transaction.atomic
def _mark_no_data_sync(id_, timestamp):
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


_mark_no_data_async = sync_to_async(_mark_no_data_sync, thread_sensitive=True)


async def mark_no_data_async(id_, timestamp):
    await _mark_no_data_async(id_, timestamp)


@transaction.atomic
def _mark_fetched_sync(id_, timestamp):
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


_mark_fetched_async = sync_to_async(_mark_fetched_sync, thread_sensitive=True)


async def mark_fetched_async(id_, timestamp):
    await _mark_fetched_async(id_, timestamp)


def _run_async_task(async_func, *args, **kwargs):
    """Execute async DB helpers even when called from sync Twisted callbacks."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        async_to_sync(async_func)(*args, **kwargs)
        return

    task = loop.create_task(async_func(*args, **kwargs))

    def _log_task_error(fut):
        if fut.exception():
            print(f"[async_task] error: {fut.exception()}")

    task.add_done_callback(_log_task_error)


def mark_no_data(id_, timestamp):
    _run_async_task(mark_no_data_async, id_, timestamp)


def mark_fetched(id_, timestamp):
    _run_async_task(mark_fetched_async, id_, timestamp)
