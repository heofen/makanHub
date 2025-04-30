# core/signals.py
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import Track, AnnoyIndexStatus
import logging

logger = logging.getLogger(__name__)

@receiver(post_delete, sender=Track)
def track_deleted_handler(sender, instance, **kwargs):
    """Устанавливает флаг перестроения индекса Annoy при удалении трека."""
    try:
        status, created = AnnoyIndexStatus.objects.get_or_create(singleton_instance_id=1)
        if not status.needs_rebuild:
            status.needs_rebuild = True
            status.save(update_fields=['needs_rebuild'])
            logger.info(f"Annoy index rebuild flag set to True due to Track deletion (ID: {instance.pk}).")
    except Exception as e:
        logger.error(f"Error setting Annoy rebuild flag on track deletion: {e}", exc_info=True) 