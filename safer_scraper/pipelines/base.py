from itemadapter import ItemAdapter


class BasePipeline:
    """Base pipeline class with common functionality"""

    def process_item(self, item, spider):
        return item

    def open_spider(self, spider):
        spider.logger.info(f"Opening {self.__class__.__name__}")

    def close_spider(self, spider):
        spider.logger.info(f"Closing {self.__class__.__name__}")