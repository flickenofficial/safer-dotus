# API Configuration
API_URL = "https://safer.fmcsa.dot.gov/query.asp"
PAYLOAD = 'searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string={}'

# Request Headers
HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://safer.fmcsa.dot.gov",
    "referer": "https://safer.fmcsa.dot.gov/",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
}

# Scraper Configuration
BATCH_SIZE = 50
RECENT_WINDOW = 0
BACKFILL_LIMIT = 10
RETRY_INTERVALS = [3, 12, 24, 72, 168]  # hours