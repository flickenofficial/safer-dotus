import re
import random
import scrapy
from datetime import datetime, timedelta
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
    "http://fhxsdvde:v1wz5l4xjq1j@154.6.11.167:5636",
    "http://fhxsdvde:v1wz5l4xjq1j@154.6.11.83:5552",
    "http://fhxsdvde:v1wz5l4xjq1j@107.175.135.25:6466",
    "http://fhxsdvde:v1wz5l4xjq1j@206.83.131.179:5555",
    "http://fhxsdvde:v1wz5l4xjq1j@46.202.67.177:6173",
    "http://fhxsdvde:v1wz5l4xjq1j@82.23.222.251:6557",
    "http://fhxsdvde:v1wz5l4xjq1j@107.173.150.225:6679",
    "http://fhxsdvde:v1wz5l4xjq1j@142.147.128.51:6551",
    "http://fhxsdvde:v1wz5l4xjq1j@82.23.222.252:6558",
    "http://fhxsdvde:v1wz5l4xjq1j@191.96.130.133:5896",
    "http://fhxsdvde:v1wz5l4xjq1j@173.0.9.197:5780",
    "http://fhxsdvde:v1wz5l4xjq1j@191.101.174.93:6141",
    "http://fhxsdvde:v1wz5l4xjq1j@82.26.238.218:6525",
    "http://fhxsdvde:v1wz5l4xjq1j@136.0.117.162:6900",
    "http://fhxsdvde:v1wz5l4xjq1j@107.174.194.42:5484",
    "http://fhxsdvde:v1wz5l4xjq1j@191.96.104.24:5761",
    "http://fhxsdvde:v1wz5l4xjq1j@46.202.224.245:5797",
    "http://fhxsdvde:v1wz5l4xjq1j@166.88.224.48:5946",
    "http://fhxsdvde:v1wz5l4xjq1j@198.12.112.5:5016",
    "http://fhxsdvde:v1wz5l4xjq1j@67.227.113.96:5636",
]


class SaferSpider(scrapy.Spider):
    name = "safer_smart"

    API_URL = API_URL
    PAYLOAD = PAYLOAD
    HEADERS = HEADERS

    def __init__(self, start_id=None, hours_to_run=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        last_fetched_id = get_last_fetched_id()

        self.last_day_fetched_id = (get_last_fetched_id_last_time() or 0) + 1
        # Create range from the last fetched ID
        self.start_id = last_fetched_id + 1
        self.end_id = self.start_id + BATCH_SIZE

        self.logger.info(f"🚀 Starting from ID {self.start_id} → {self.end_id}")

        self.start_id = int(start_id) if start_id else 1
        self.hours_to_run = float(hours_to_run) if hours_to_run else 4.0
        self.end_id = self.start_id + 1000
        self.deadline = datetime.utcnow() + timedelta(hours=self.hours_to_run)
        self.logger.error(
            f"DEBUG: start_id={self.start_id}, hours_to_run={self.hours_to_run}, deadline={self.deadline}")

        self.logger.info(
            f"🚀 Starting scraper from DOT {self.start_id} "
            f"for {self.hours_to_run} hour(s) (deadline: {self.deadline})"
        )

    def start_requests(self):
        for code in self.ids_to_scan():

            # ✅ Stop scraper immediately when time expired
            if datetime.utcnow() > self.deadline:
                self.logger.info("⏹ Stopping scraper — time limit reached (start_requests)")
                raise scrapy.exceptions.CloseSpider("time_limit_reached")

            payload = self.PAYLOAD.format(code)
            yield scrapy.Request(
                self.API_URL,
                method="POST",
                body=payload,
                headers=self.HEADERS,
                meta={"code": code, 'proxy': random.choice(proxy_list)},
                dont_filter=True,
                callback=self.parse,
                errback=self.handle_error,
            )

    def ids_to_scan(self):
        ids = list(range(self.start_id, self.end_id))
        ids = get_recent_ids(ids)
        ids += get_backfill_ids_since_last_fetched(self.start_id - 1)
        return list(sorted(set(ids)))

    async def parse(self, response):
        code = response.meta["code"]
        now = datetime.utcnow().isoformat()

        # ✅ Stop scraper inside parse()
        if datetime.utcnow() > self.deadline:
            self.logger.info(f"⏹ Deadline reached in parse() at DOT {code}")
            raise scrapy.exceptions.CloseSpider("time_limit_reached")

        try:
            legal_name = response.css('th:contains("Legal Name:") + td::text').get("").strip()
            if not legal_name:
                await mark_no_data(code, now)
                return

            mailing_address = " ".join(response.css('th:contains("Mailing Address:") + td::text').getall()).strip()
            mailing_address = re.sub(r"\s+", " ", mailing_address)
            zipcode = mailing_address.split()[-1].strip() if mailing_address else ''

            item = SaferItem()
            item['dot_number'] = code
            item['legal_name'] = legal_name
            item['physical_address'] = response.css('th:contains("Physical Address:") + td::text').get("").strip()
            item['zipcode'] = zipcode
            item['mailing_code'] = mailing_address
            item['phone'] = response.css('th:contains("Phone:") + td::text').get("").strip()
            item['operating_status'] = response.css('th:contains("Operating Authority Status:") + td::text').get(
                "").strip()
            item['power_units'] = response.css('th:contains("Power Units:") + td::text').get("").strip()
            item['drivers'] = response.css('th:contains("Drivers:") + td::text').get("").strip()
            item['date_filed'] = response.css('th:contains("Form Date") + td::text').get("").strip()

            url = f"https://ai.fmcsa.dot.gov/SMS/Carrier/{code}/CarrierRegistration.aspx"
            yield scrapy.Request(
                url,
                meta={'item': item, 'proxy': random.choice(proxy_list)},
                callback=self.parse_email,
                errback=self.handle_error,
            )

        except Exception as e:
            self.logger.warning(f"Parse failed for DOT {code}: {e}")
            await mark_no_data(code, now)

    async def parse_email(self, response, **kwargs):

        # ✅ Stop scraper inside parse_email()
        if datetime.utcnow() > self.deadline:
            self.logger.info("⏹ Deadline reached in parse_email()")
            raise scrapy.exceptions.CloseSpider("time_limit_reached")

        item = response.meta.get('item')
        now = datetime.utcnow().isoformat()
        item['fetched_at'] = now
        item['email'] = response.css('label:contains("Email:") + span::text').get('').strip()

        yield item
        await mark_fetched(item['dot_number'], now)

    async def handle_error(self, failure):

        # ✅ Stop scraper inside handle_error()
        if datetime.utcnow() > self.deadline:
            self.logger.info("⏹ Deadline reached in handle_error()")
            raise scrapy.exceptions.CloseSpider("time_limit_reached")

        item = failure.request.meta.get('item')
        code = failure.request.meta.get("code") or (item['dot_number'] if item else None)
        now = datetime.utcnow().isoformat()

        if item:
            item['fetched_at'] = now
            yield item
            await mark_no_data(code, now)
        else:
            self.logger.warning(f"⚠️ ID {code} failed: {failure.value}")
            await mark_no_data(code, now)
