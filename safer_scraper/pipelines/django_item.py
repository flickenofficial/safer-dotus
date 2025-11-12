from itemadapter import ItemAdapter
from django.utils import timezone
from django.db import transaction
from asgiref.sync import sync_to_async
from twisted.internet.defer import ensureDeferred

from ..models import SaferData
from .base import BasePipeline


class DjangoItemPipeline(BasePipeline):
    """Async-safe pipeline to bulk save items to Django database."""

    def __init__(self, buffer_limit=100):
        self.buffer = []
        self.buffer_limit = buffer_limit

    async def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        data = {
            'dot_number': adapter.get('dot_number'),
            'legal_name': adapter.get('legal_name', ''),
            'physical_address': adapter.get('physical_address', ''),
            'zipcode': adapter.get('zipcode', ''),
            'mailing_code': adapter.get('mailing_code', ''),
            'phone': adapter.get('phone', ''),
            'operating_status': adapter.get('operating_status', ''),
            'power_units': adapter.get('power_units', ''),
            'drivers': adapter.get('drivers', ''),
            'date_filed': adapter.get('date_filed', ''),
            'email': adapter.get('email', ''),
            'fetched_at': adapter.get('fetched_at', timezone.now()),
        }
        self.buffer.append(data)

        if len(self.buffer) >= self.buffer_limit:
            await self.flush_buffer(spider)

        return item

    @sync_to_async
    def _sync_flush(self, spider):
        """This part runs synchronously in a separate thread."""
        if not self.buffer:
            return

        try:
            with transaction.atomic():
                objs = [SaferData(**data) for data in self.buffer]
                SaferData.objects.bulk_create(
                    objs,
                    batch_size=self.buffer_limit,
                    ignore_conflicts=True
                )

                existing_dots = SaferData.objects.filter(
                    dot_number__in=[d['dot_number'] for d in self.buffer]
                )
                existing_map = {obj.dot_number: obj for obj in existing_dots}
                to_update = []
                for data in self.buffer:
                    if data['dot_number'] in existing_map:
                        obj = existing_map[data['dot_number']]
                        for field, value in data.items():
                            setattr(obj, field, value)
                        to_update.append(obj)

                if to_update:
                    SaferData.objects.bulk_update(
                        to_update,
                        fields=[
                            'legal_name', 'physical_address', 'zipcode', 'mailing_code',
                            'phone', 'operating_status', 'power_units', 'drivers',
                            'date_filed', 'email', 'fetched_at'
                        ],
                        batch_size=self.buffer_limit,
                    )

            spider.logger.info(f"Bulk saved {len(self.buffer)} items to database")
        except Exception as e:
            spider.logger.error(f"Bulk save error: {e}")
        finally:
            self.buffer.clear()

    async def flush_buffer(self, spider):
        """Flush asynchronously (but ORM inside runs in sync thread)."""
        if self.buffer:
            await self._sync_flush(spider)

    async def close_spider(self, spider):
        """Flush remaining items when spider closes."""
        await self.flush_buffer(spider)
