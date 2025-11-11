from django.core.management.base import BaseCommand
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from safer_scraper.spiders import SaferSpider
from safer_scraper.utils import get_last_fetched_id
from safer_scraper.models.scraper_job import ScraperJob


class Command(BaseCommand):
    help = 'Run the default SAFER scraper (for manual/backfill runs)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start_id', type=int, help='DOT number to start from'
        )
        parser.add_argument(
            '--hours', type=float, help='Number of hours to run the scraper'
        )
        parser.add_argument(
            '--job-id', type=int, help='Existing ScraperJob ID to reuse'
        )

    def handle(self, *args, **options):
        provided_start_id = options.get('start_id')
        provided_hours = options.get('hours')
        job_id = options.get('job_id')

        if job_id:
            job = ScraperJob.objects.get(id=job_id)
            start_id = provided_start_id or job.start_id or get_last_fetched_id() + 1
            hours = provided_hours or job.hours_to_run or 4.0
            # Keep DB record aligned with the inputs we actually use
            job.start_id = start_id
            job.hours_to_run = hours
            job.status = 'pending'
            job.save(update_fields=['start_id', 'hours_to_run', 'status'])
        else:
            start_id = provided_start_id or get_last_fetched_id() + 1
            hours = provided_hours or 4.0  # default 4 hours
            job = ScraperJob.objects.create(
                start_id=start_id,
                hours_to_run=hours,
                status='pending'
            )
        job.mark_as_running()

        self.stdout.write(self.style.SUCCESS(
            f'Starting scraper with start_id={start_id}, hours={hours}'
        ))

        settings = get_project_settings()
        settings.set('ITEM_PIPELINES', {
            'safer_scraper.pipelines.django_item.DjangoItemPipeline': 300,
        })
        settings.set('LOG_LEVEL', 'INFO')
        settings.set('RETRY_TIMES', 4)
        settings.set('ROBOTSTXT_OBEY', False)
        settings.set('DOWNLOAD_DELAY', 1)

        try:
            process = CrawlerProcess(settings=settings)
            process.crawl(SaferSpider, start_id=start_id, hours_to_run=hours)
            process.start()
            job.mark_as_completed()
            self.stdout.write(self.style.SUCCESS('Scraper completed successfully'))
        except Exception as e:
            job.mark_as_failed(str(e))
            self.stderr.write(self.style.ERROR(f'Scraper failed: {e}'))
