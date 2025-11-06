import random
import re, sqlite3
from datetime import datetime
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

API_URL = "https://safer.fmcsa.dot.gov/query.asp"
PAYLOAD = 'searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string={}'

headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://safer.fmcsa.dot.gov",
    "referer": "https://safer.fmcsa.dot.gov/",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
}

# --- Configurable ---
BATCH_SIZE = 500
RECENT_WINDOW = 50
BACKFILL_LIMIT = 80
RETRY_INTERVALS = [3, 12, 24, 72, 168]  # hours
DB_FILE = "../sqlite3.db"


# --- DB setup ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    conn.commit()
    return conn, cur


conn, cur = get_db_connection()
cur.execute("""
CREATE TABLE IF NOT EXISTS safer_state (
    id INTEGER PRIMARY KEY,
    status TEXT,
    last_checked TEXT,
    retry_count INTEGER DEFAULT 0
)
""")
conn.commit()
cur.execute("""
CREATE TABLE IF NOT EXISTS safer_data (
    id INTEGER PRIMARY KEY,
    dot_number INTEGER,
    legal_name TEXT,
    physical_address TEXT,
    zipcode TEXT,
    mailing_code TEXT,
    phone TEXT,
    operating_status TEXT,
    power_units TEXT,
    drivers TEXT,
    date_filed TEXT,
    email TEXT,
    fetched_at TEXT
)
""")
conn.commit()


# ---------------------------
# Helper functions
# ---------------------------

def mark_no_data(id_, timestamp):
    cur.execute("""
        INSERT OR REPLACE INTO safer_state (id, status, last_checked, retry_count)
        VALUES (?, 'no_data', ?, COALESCE((SELECT retry_count FROM safer_state WHERE id=?),0))
    """, (id_, timestamp, id_))
    conn.commit()


def mark_fetched(id_, timestamp):
    cur.execute("""
        INSERT OR REPLACE INTO safer_state (id, status, last_checked, retry_count)
        VALUES (?, 'fetched', ?, 0)
    """, (id_, timestamp))
    conn.commit()


def get_last_fetched_id():
    cur.execute("SELECT MAX(id) FROM safer_state WHERE status='fetched'")
    result = cur.fetchone()[0]
    return result if result else 0  # Default to 0 if no records found


def get_last_fetched_id_last_time():
    # Calculate last's date
    today = datetime.utcnow().date().isoformat()

    # Query the database for the latest fetched ID from previous days (excluding today)
    cur.execute("""
            SELECT MAX(id) FROM safer_state
            WHERE status='fetched' AND DATE(last_checked) < ?
        """, (today,))

    result = cur.fetchone()[0]
    return result if result else 0 # Return 0 if no records found


def get_recent_ids(recent_range):
    cur.execute("SELECT id FROM safer_state WHERE status='fetched'")
    fetched_ids = {row[0] for row in cur.fetchall()}
    return [i for i in recent_range if i not in fetched_ids]


def get_backfill_ids_since_last_fetched(last_fetched_id):
    cur.execute("""
        SELECT id FROM safer_state
        WHERE status='no_data'
        ORDER BY id ASC
    """)
    return [r[0] for r in cur.fetchall()]


import scrapy


class SaferItem(scrapy.Item):
    dot_number = scrapy.Field()
    legal_name = scrapy.Field()
    physical_address = scrapy.Field()
    zipcode = scrapy.Field()
    mailing_code = scrapy.Field()
    phone = scrapy.Field()
    operating_status = scrapy.Field()
    power_units = scrapy.Field()
    drivers = scrapy.Field()
    date_filed = scrapy.Field()
    email = scrapy.Field()
    fetched_at = scrapy.Field()


class SQLiteBulkPipeline:

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, timeout=30)
        self.cur = self.conn.cursor()
        self.buffer = []
        self.buffer_limit = 100  # number of items to accumulate before bulk insert

    def process_item(self, item, spider):
        self.buffer.append((
            item.get('dot_number'),
            item.get('legal_name'),
            item.get('physical_address'),
            item.get('zipcode'),
            item.get('mailing_code'),
            item.get('phone'),
            item.get('operating_status'),
            item.get('power_units'),
            item.get('drivers'),
            item.get('date_filed'),
            item.get('email'),
            item.get('fetched_at'),
        ))

        if len(self.buffer) >= self.buffer_limit:
            self.flush_buffer()
        return item

    def flush_buffer(self):
        if not self.buffer:
            return
        self.cur.executemany("""
            INSERT OR REPLACE INTO safer_data (
                dot_number, legal_name, physical_address, zipcode,
                mailing_code, phone, operating_status,
                power_units, drivers, date_filed, email, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, self.buffer)
        self.conn.commit()
        self.buffer.clear()

    def close_spider(self, spider):
        # flush any remaining items
        self.flush_buffer()
        self.conn.close()


# ---------------------------
# Scrapy spider
# ---------------------------

class SaferSpider(scrapy.Spider):
    name = "safer_smart"

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
            payload = PAYLOAD.format(code)
            yield scrapy.Request(
                API_URL,
                method="POST",
                body=payload,
                headers=headers,
                meta={"code": code, 'proxy':random.choice(proxy_list)},
                dont_filter=True,
                callback=self.parse,
                errback=self.handle_error,
            )

    def ids_to_scan(self):
        # Initial range for today's run (from self.start_id to self.end_id)
        ids = list(range(self.start_id, self.end_id))

        # Add backfill range if last day's fetched ID is different from today’s start ID
        if self.last_day_fetched_id != self.start_id:
            ids += list(range(self.last_day_fetched_id, self.start_id))

        # Remove already fetched IDs from the list (from 'safer_state' table)
        ids = get_recent_ids(ids)  # Retrieve already fetched IDs

        # Add backfill IDs from the last fetched ID to the current date
        ids += get_backfill_ids_since_last_fetched(self.start_id - 1)

        # Remove duplicates and return unique IDs
        return list(sorted(set(ids)))  # Sorting to keep the order intact

    def parse(self, response):
        code = response.meta["code"]
        now = datetime.utcnow().isoformat()
        try:
            legal_name = response.css('th:contains("Legal Name:") + td::text').get("")
            if not legal_name:
                mark_no_data(code, now)
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
            mark_no_data(code, now)

    def parse_email(self, response, **kwargs):
        item = response.meta.get('item')
        now = datetime.utcnow().isoformat()
        item['fetched_at'] = now

        item['email'] = response.css('label:contains("Email:") + span::text').get('').strip()
        yield item
        mark_fetched(item['dot_number'], now)

    def handle_error(self, failure):
        """Called when a request fails (404, 500, timeout, etc)."""
        item = failure.request.meta.get('item')
        code = failure.request.meta.get("code") or item['dot_number']
        now = datetime.utcnow().isoformat()
        if item:
            item['fetched_at'] = now
            yield item
            mark_no_data(code, now)

        else:
            self.logger.warning(f"⚠️ ID {code} failed: {failure.value}")
            mark_no_data(code, now)


# ---------------------------
# Runner
# ---------------------------
if __name__ == "__main__":

    proxy_list = [
        "http://odsodcis:e3qzapy0fw0f@142.111.48.253:7030",
        "http://odsodcis:e3qzapy0fw0f@23.95.150.145:6114",
        "http://odsodcis:e3qzapy0fw0f@198.23.239.134:6540",
        "http://odsodcis:e3qzapy0fw0f@107.172.163.27:6543",
        "http://odsodcis:e3qzapy0fw0f@216.10.27.159:6837",
        "http://odsodcis:e3qzapy0fw0f@142.147.128.93:6593"
    ]
    settings = get_project_settings()
    settings['FEEDS'] = {"safer_smart.csv": {"format": "csv"}}
    settings['ITEM_PIPELINES'] = {
        '__main__.SQLiteBulkPipeline': 300,
    }
    settings['LOG_LEVEL'] = 'INFO'
    settings['RETRY_TIMES'] = 4
    settings['ROBOTSTXT_OBEY'] = False

    process = CrawlerProcess(settings=settings)
    process.crawl(SaferSpider)
    process.start()
    conn.close()
