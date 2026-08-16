import time
import threading
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

_scheduler_thread = None
_scheduler_lock = threading.Lock()


def run_scheduler_loop():
    """
    Background worker thread running continuously every minute.
    Checks if configured daily_report_time matches current time (HH:MM)
    and hasn't been sent yet today.
    """
    logger.info("Starting Daily Report Scheduler Loop...")
    
    # Delay initial check slightly to let Django models finish loading
    time.sleep(10)

    while True:
        try:
            from .models import TelegramConfig
            from .report_service import DailyReportService

            config = TelegramConfig.get_config()
            if config.daily_report_enabled:
                now_local = timezone.localtime(timezone.now())
                current_time_str = now_local.strftime('%H:%M')
                today_date = now_local.date()

                target_time = (config.daily_report_time or '21:00').strip()

                if current_time_str == target_time:
                    if config.last_daily_report_sent != today_date:
                        logger.info(f"Daily report trigger time reached ({current_time_str}). Dispatching daily report...")
                        sent_count, _ = DailyReportService.dispatch_daily_report()
                        logger.info(f"Daily report dispatched successfully to {sent_count} subscribers.")

        except Exception as e:
            logger.error(f"Error in Daily Report Scheduler loop: {e}", exc_info=True)

        # Sleep for 45 seconds before next minute check
        time.sleep(45)


def start_daily_report_scheduler():
    """
    Starts the daily report scheduler background daemon thread if not already running.
    """
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread is None or not _scheduler_thread.is_alive():
            _scheduler_thread = threading.Thread(target=run_scheduler_loop, daemon=True, name="DailyReportScheduler")
            _scheduler_thread.start()
            logger.info("Daily Report Scheduler daemon thread initialized.")
