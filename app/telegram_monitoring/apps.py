from django.apps import AppConfig


class TelegramMonitoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.telegram_monitoring'

    def ready(self):
        import os
        # Avoid running scheduler twice in Django reloader thread
        if os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('SERVER_GATEWAY_INTERFACE'):
            try:
                from .scheduler import start_daily_report_scheduler
                start_daily_report_scheduler()
            except Exception as e:
                pass
