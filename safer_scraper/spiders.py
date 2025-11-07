import re
import random
import scrapy
from datetime import datetime, timedelta
from .constants import API_URL, PAYLOAD, HEADERS
from .utils import (
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

    API_URL = API_URL
    PAYLOAD = PAYLOAD
    HEADERS = HEADERS

    def __init__(self, start_id=None, hours_to_run=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_id = int(start_id) if start_id else 1
        self.hours_to_run = float(hours_to_run) if hours_to_run else 1.0
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
            item['operating_status'] = response.css('th:contains("Operating Authority Status:") + td::text').get("").strip()
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
