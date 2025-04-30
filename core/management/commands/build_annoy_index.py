from django.core.management.base import BaseCommand
from django.conf import settings
from core.annoy_service import AnnoyService # Импортируем наш сервис
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Builds the Annoy index from tracks in the database and saves it to a file.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--num_trees',
            type=int,
            default=settings.ANNOY_NUM_TREES,
            help='Number of trees to build in the Annoy index.'
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting Annoy index build...")
        num_trees = options['num_trees']
        try:
            # Создаем экземпляр сервиса специально для построения
            # (не используем глобальный annoy_service, чтобы избежать конфликтов состояний)
            builder_service = AnnoyService()
            builder_service.build_index_from_db(num_trees=num_trees)

            if builder_service.index.get_n_items() > 0:
                self.stdout.write(self.style.SUCCESS(
                    f"Successfully built and saved Annoy index with {builder_service.index.get_n_items()} items "
                    f"to {builder_service.index_path}"
                ))
            else:
                 self.stdout.write(self.style.WARNING("Annoy index build completed, but no items were added (no valid embeddings found?)."))

        except Exception as e:
            logger.error(f"Error building Annoy index: {e}", exc_info=True)
            self.stderr.write(self.style.ERROR(f"Error building Annoy index: {e}")) 