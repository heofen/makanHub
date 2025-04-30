# core/jobs.py
import logging
from django.utils import timezone
from .models import AnnoyIndexStatus
from .annoy_service import AnnoyService # Используем новый экземпляр для построения
from django.conf import settings

logger = logging.getLogger(__name__)

def rebuild_annoy_if_needed():
    """Проверяет флаг и перестраивает индекс Annoy, если требуется."""
    logger.info("Checking if Annoy index rebuild is needed...")
    try:
        status, created = AnnoyIndexStatus.objects.get_or_create(singleton_instance_id=1)
        if status.needs_rebuild or created: # Перестраиваем и при первой проверке
            logger.info("Annoy index rebuild required. Starting build...")
            try:
                builder_service = AnnoyService() # Создаем новый экземпляр сервиса
                builder_service.build_index_from_db(num_trees=settings.ANNOY_NUM_TREES)

                # Обновляем статус после успешного построения
                status.needs_rebuild = False
                status.last_build_time = timezone.now()
                status.save(update_fields=['needs_rebuild', 'last_build_time'])
                logger.info(f"Annoy index successfully rebuilt and saved to {builder_service.index_path}. Flag reset.")

            except Exception as build_error:
                logger.error(f"Error during scheduled Annoy index rebuild: {build_error}", exc_info=True)
                # Флаг не сбрасываем, чтобы попробовать снова в следующий раз
        else:
            logger.info("Annoy index rebuild not needed.")
    except Exception as status_error:
         logger.error(f"Error checking Annoy index status: {status_error}", exc_info=True) 