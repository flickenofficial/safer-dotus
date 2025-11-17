import re
import random
import scrapy
from datetime import datetime, timedelta
from ..constants import API_URL, PAYLOAD, HEADERS, BATCH_SIZE
from ..utils import (
    get_last_fetched_id,
    get_last_fetched_id_last_time,
    get_recent_ids,
    get_backfill_ids_since_last_fetched,
    mark_no_data,
    mark_fetched,
    get_proxies,
)
from ..items import SaferItem

class SaferSpider(scrapy.Spider):
    name = "safer_smart"

    API_URL = API_URL
    PAYLOAD = PAYLOAD
    HEADERS = HEADERS

    # -------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------
    def __init__(self, start_id=None, hours_to_run=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.proxy_list = get_proxies()
        if not start_id:
            self.infinite_loop = False
            last_fetched_id = get_last_fetched_id()
            # self.last_day_fetched_id = (get_last_fetched_id_last_time() or 0) + 1

            self.start_id = last_fetched_id + 1
            self.end_id = self.start_id + BATCH_SIZE
            self.deadline = datetime.utcnow() + timedelta(hours=0.21)

            self.logger.info(f"🚀 Infinite mode: IDs {self.start_id} → {self.end_id}")
        else:
            self.infinite_loop = True
            self.start_id = int(start_id)
            self.hours_to_run = float(hours_to_run or 4.0)
            self.end_id = 1000
            self.deadline = datetime.utcnow() + timedelta(hours=self.hours_to_run)
            self.logger.info(
                f"🚀 Timed mode: start DOT {self.start_id}, "
                f"run {self.hours_to_run}h (deadline {self.deadline})"
            )

    # -------------------------------------------------------------------
    # Utility helpers
    # -------------------------------------------------------------------
    def get_proxy(self):
        return random.choice(self.proxy_list)

    def stop_if_deadline(self, context: str = "") -> bool:
        """Gracefully stop spider when deadline reached."""
        if hasattr(self, "deadline") and datetime.utcnow() > self.deadline:
            self.logger.info(f"⏹ Deadline reached — stopping spider ({context})")
            self.crawler.engine.close_spider(self, reason="time_limit_reached")
            return True
        return False

    # -------------------------------------------------------------------
    # Request generation
    # -------------------------------------------------------------------
    def start_requests(self):
        if self.infinite_loop:
            code = self.start_id
            batch_end_id = code + BATCH_SIZE
            for code in range(self.start_id, batch_end_id):
                if self.stop_if_deadline("start_requests"):
                    return
                yield self._build_request(code)


        else:
            # In non-infinite loop mode, process the IDs as usual
            for code in self.ids_to_scan():
                if self.stop_if_deadline("start_requests"):
                    return  # Stop if the deadline is reached
                yield self._build_request(code)

    def _build_request(self, code):
        payload = self.PAYLOAD.format(code)
        return scrapy.Request(
            self.API_URL,
            method="POST",
            body=payload,
            headers=self.HEADERS,
            meta={"code": code, "proxy": self.get_proxy()},
            dont_filter=True,
            callback=self.parse,
            errback=self.handle_error,
        )

    def ids_to_scan(self):
        ids = list(range(self.start_id, self.end_id))
        ids = get_recent_ids(ids)
        # ids += get_backfill_ids_since_last_fetched(self.start_id - 1)
        return sorted(set(ids))

    # -------------------------------------------------------------------
    # Parsing
    # -------------------------------------------------------------------
    def parse(self, response):
        code = response.meta["code"]
        now = datetime.utcnow().isoformat()

        if self.stop_if_deadline("parse"):
            return

        try:
            legal_name = response.css('th:contains("Legal Name:") + td::text').get("").strip()
            if not legal_name:
                mark_no_data(code, now)
                return

            mailing_address = " ".join(response.css('th:contains("Mailing Address:") + td::text').getall()).strip()
            mailing_address = re.sub(r"\s+", " ", mailing_address)
            zipcode = mailing_address.split()[-1].strip() if mailing_address else ""

            item = SaferItem()
            item["dot_number"] = code
            item["legal_name"] = legal_name
            item["physical_address"] = response.css('th:contains("Physical Address:") + td::text').get("").strip()
            item["zipcode"] = zipcode
            item["mailing_code"] = mailing_address
            item["phone"] = response.css('th:contains("Phone:") + td::text').get("").strip()
            item["operating_status"] = response.css(
                'th:contains("Operating Authority Status:") + td::text'
            ).get("").strip()
            item["power_units"] = response.css('th:contains("Power Units:") + td::text').get("").strip()
            item["drivers"] = response.css('th:contains("Drivers:") + td::text').get("").strip()
            item["date_filed"] = response.css('th:contains("Form Date") + td::text').get("").strip()

            url = f"https://ai.fmcsa.dot.gov/SMS/Carrier/{code}/CarrierRegistration.aspx"
            yield scrapy.Request(
                url,
                meta={"item": item, "proxy": self.get_proxy()},
                callback=self.parse_email,
                errback=self.handle_error,
                dont_filter=True,
            )

        except Exception as e:
            self.logger.warning(f"Parse failed for DOT {code}: {e}")
            mark_no_data(code, now)

    def parse_email(self, response):
        if self.stop_if_deadline("parse_email"):
            return

        item = response.meta.get("item")
        now = datetime.utcnow().isoformat()
        item["fetched_at"] = now
        item["email"] = response.css('label:contains("Email:") + span::text').get("").strip()

        yield item
        mark_fetched(item["dot_number"], now)

    # -------------------------------------------------------------------
    # Error handler
    # -------------------------------------------------------------------
    def handle_error(self, failure):
        if self.stop_if_deadline("handle_error"):
            return

        item = failure.request.meta.get("item")
        code = failure.request.meta.get("code") or (item["dot_number"] if item else None)
        now = datetime.utcnow().isoformat()

        if item:
            item["fetched_at"] = now
            yield item
        else:
            self.logger.warning(f"⚠️ ID {code} failed: {failure.value}")
            mark_no_data(code, now)
