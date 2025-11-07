from django.core.management.base import BaseCommand
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from safer_scraper.spiders import SaferSpider


class Command(BaseCommand):
    help = 'Run the default SAFER scraper (for manual/backfill runs)'

    def handle(self, *args, **options):
        settings = get_project_settings()
        settings.set('ITEM_PIPELINES', {
            'safer_scraper.pipelines.django_item.DjangoItemPipeline': 300,
        })
        settings.set('LOG_LEVEL', 'INFO')
        settings.set('RETRY_TIMES', 4)
        settings.set('ROBOTSTXT_OBEY', False)
        settings.set('DOWNLOAD_DELAY', 1)

        process = CrawlerProcess(settings=settings)
        process.crawl(SaferSpider)
        process.start()

        self.stdout.write(self.style.SUCCESS('Scraper completed successfully'))