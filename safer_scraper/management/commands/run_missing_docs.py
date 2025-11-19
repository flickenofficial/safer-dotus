from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from safer_scraper.spiders import MissingDocsSpider


class Command(BaseCommand):
    help = "Run scraper to fetch missing DOT documents for a specific date."

    def add_arguments(self, parser):
        parser.add_argument(
            "--target-date",
            type=str,
            help="Date (YYYY-MM-DD) to backfill. Defaults to yesterday.",
        )

    def handle(self, *args, **options):
        target_date = options.get("target_date")
        if target_date:
            try:
                target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError as exc:
                raise CommandError("target-date must be YYYY-MM-DD") from exc
        settings = get_project_settings()
        settings.set(
            "ITEM_PIPELINES",
            {
                "safer_scraper.pipelines.django_item.DjangoItemPipeline": 300,
            },
        )
        settings.set("LOG_LEVEL", "INFO")
        settings.set("RETRY_TIMES", 4)
        settings.set("ROBOTSTXT_OBEY", False)
        settings.set("DOWNLOAD_DELAY", 1)
        settings.set("CONCURRENT_REQUESTS", 4)

        process = CrawlerProcess(settings=settings)
        process.crawl(MissingDocsSpider, target_date=target_date)
        process.start()
        self.stdout.write(self.style.SUCCESS("Missing DOT scraper completed"))
