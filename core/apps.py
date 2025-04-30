from django.apps import AppConfig
import logging
import os # Для проверки запуска основного процесса

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Импортируем сигналы, чтобы они зарегистрировались
        import core.signals

        # Запуск планировщика APScheduler
        # Запускаем только в основном процессе, чтобы избежать дублирования задач при автоперезагрузке
        # или при использовании нескольких воркеров (хотя для последнего это не спасет)
        run_main = os.environ.get('RUN_MAIN') or os.environ.get('WERKZEUG_RUN_MAIN')
        if run_main:
            from .jobs import rebuild_annoy_if_needed
            from apscheduler.schedulers.background import BackgroundScheduler
            from django_apscheduler.jobstores import DjangoJobStore

            try:
                scheduler = BackgroundScheduler()
                scheduler.add_jobstore(DjangoJobStore(), "default")

                # Добавляем нашу задачу - запускать каждые 5 минут
                # replace_existing=True - чтобы не создавалась дублирующая задача при перезапусках
                scheduler.add_job(
                    rebuild_annoy_if_needed,
                    trigger='interval',
                    minutes=5,
                    id='rebuild_annoy_index_job',
                    max_instances=1,
                    replace_existing=True,
                )
                logger.info("Added job 'rebuild_annoy_index_job' to APScheduler.")

                # Запускаем планировщик
                scheduler.start()
                logger.info("APScheduler started...")

            except Exception as e:
                logger.error(f"Error starting APScheduler: {e}", exc_info=True)
        else:
             logger.info("APScheduler not starting in this process (likely autoreload worker).")
