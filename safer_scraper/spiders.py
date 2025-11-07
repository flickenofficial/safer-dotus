import re
import random
import scrapy
from datetime import datetime
from .constants import API_URL, PAYLOAD, HEADERS, BATCH_SIZE
from .utils import (
    get_last_fetched_id,
    get_last_fetched_id_last_time,
    get_recent_ids,
    get_backfill_ids_since_last_fetched,
    mark_no_data,
    mark_fetched
)
from .items import SaferItem

proxy_list = [
        "http://utzzwcbp:n3khqw2dm4l2@142.111.48.253:7030",
        "http://utzzwcbp:n3khqw2dm4l2@23.95.150.145:6114",
        "http://utzzwcbp:n3khqw2dm4l2@198.23.239.134:6540",
        "http://utzzwcbp:n3khqw2dm4l2@107.172.163.27:6543",
        "http://utzzwcbp:n3khqw2dm4l2@216.10.27.159:6837",
        "http://utzzwcbp:n3khqw2dm4l2@142.147.128.93:6593"
    ]
class SaferSpider(scrapy.Spider):
    name = "safer_smart"

    # Make constants class attributes for easier access in subclasses
    API_URL = API_URL
    PAYLOAD = PAYLOAD
    HEADERS = HEADERS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get the last fetched ID to define today's range
        last_fetched_id = get_last_fetched_id()

        self.last_day_fetched_id = (get_last_fetched_id_last_time() or 0) + 1
        # Create range from the last fetched ID
        self.start_id = last_fetched_id + 1
        self.end_id = self.start_id + BATCH_SIZE

        self.logger.info(f"🚀 Starting from ID {self.start_id} → {self.end_id}")

    def start_requests(self):
        for code in self.ids_to_scan():
            payload = self.PAYLOAD.format(code)
            yield scrapy.Request(
                self.API_URL,
                method="POST",
                body=payload,
                headers=self.HEADERS,
                meta={"code": code, 'proxy':random.choice(proxy_list)},
                dont_filter=True,
                callback=self.parse,
                errback=self.handle_error,
            )

    def ids_to_scan(self):
        # Initial range for today's run (from self.start_id to self.end_id)
        ids = list(range(self.start_id, self.end_id))

        # Add backfill range if last day's fetched ID is different from today's start ID
        if self.last_day_fetched_id != self.start_id:
            ids += list(range(self.last_day_fetched_id, self.start_id))

        # Remove already fetched IDs from the list (from 'safer_state' table)
        ids = get_recent_ids(ids)  # Retrieve already fetched IDs

        # Add backfill IDs from the last fetched ID to the current date
        ids += get_backfill_ids_since_last_fetched(self.start_id - 1)

        # Remove duplicates and return unique IDs
        return list(sorted(set(ids)))  # Sorting to keep the order intact

    async def parse(self, response):
        code = response.meta["code"]
        now = datetime.utcnow().isoformat()
        try:
            legal_name = response.css('th:contains("Legal Name:") + td::text').get("")
            if not legal_name:
                await mark_no_data(code, now)
                return

            mailing_address = " ".join(
                response.css('th:contains("Mailing Address:") + td::text').getall()
            ).strip()
            mailing_address = re.sub(r"\s+", " ", mailing_address)
            zipcode = mailing_address.split()[-1].strip() if mailing_address else ''

            item = SaferItem()
            item['dot_number'] = code
            item['legal_name'] = legal_name.strip()
            item['physical_address'] = response.css('th:contains("Physical Address:") + td::text').get("").strip()
            item['zipcode'] = zipcode
            item['mailing_code'] = mailing_address
            item['phone'] = response.css('th:contains("Phone:") + td::text').get("").strip()
            item['operating_status'] = response.css('th:contains("Operating Authority Status:") + td::text').get(
                "").strip() or response.css('th:contains("Operating Authority Status:") + td > font > b::text').get(
                "").strip()
            item['power_units'] = response.css('th:contains("Power Units:") + td::text').get("").strip()
            item['drivers'] = response.css('th:contains("Drivers:") + td::text').get("").strip() or response.css(
                'th:contains("Drivers:") + td > font > b::text').get("").strip()
            item['date_filed'] = response.css('th:contains("Form Date") + td::text').get("").strip()

            url = f"https://ai.fmcsa.dot.gov/SMS/Carrier/{code}/CarrierRegistration.aspx"

            yield scrapy.Request(url, meta={'item': item, 'proxy':random.choice(proxy_list)}, callback=self.parse_email, errback=self.handle_error, )


        except Exception as e:
            self.logger.warning(f"Parse failed for {code}: {e}")
            await mark_no_data(code, now)

    async def parse_email(self, response, **kwargs):
        item = response.meta.get('item')
        now = datetime.utcnow().isoformat()
        item['fetched_at'] = now

        item['email'] = response.css('label:contains("Email:") + span::text').get('').strip()
        yield item
        await mark_fetched(item['dot_number'], now)

    async def handle_error(self, failure):
        """Called when a request fails (404, 500, timeout, etc)."""
        item = failure.request.meta.get('item')
        code = failure.request.meta.get("code") or item['dot_number']
        now = datetime.utcnow().isoformat()
        if item:
            item['fetched_at'] = now
            yield item
            await mark_no_data(code, now)

        else:
            self.logger.warning(f"⚠️ ID {code} failed: {failure.value}")
            await mark_no_data(code, now)