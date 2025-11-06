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