from django.core.management.base import BaseCommand
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from safer_scraper.spiders import SaferSpider


class Command(BaseCommand):
    help = 'Run the default SAFER scraper (for manual/backfill runs)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start_id', type=int, required=True, help='DOT number to start from'
        )
        parser.add_argument(
            '--hours', type=float, required=True, help='Number of hours to run the scraper'
        )

    def handle(self, *args, **options):
        start_id = options['start_id']
        hours = options['hours']

        settings = get_project_settings()
        settings.set('ITEM_PIPELINES', {
            'safer_scraper.pipelines.django_item.DjangoItemPipeline': 300,
        })
        settings.set('LOG_LEVEL', 'INFO')
        settings.set('RETRY_TIMES', 4)
        settings.set('ROBOTSTXT_OBEY', False)
        settings.set('DOWNLOAD_DELAY', 1)

        self.stdout.write(self.style.SUCCESS(f'Starting scraper with start_id={start_id}, hours={hours}'))

        process = CrawlerProcess(settings=settings)
        process.crawl(SaferSpider, start_id=start_id, hours_to_run=hours)
        process.start()

        self.stdout.write(self.style.SUCCESS('Scraper completed successfully'))
