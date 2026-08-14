import time
from concurrent.futures import ThreadPoolExecutor
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.database_monitoring.models import Database
from app.database_monitoring.checker import check_database


class Command(BaseCommand):
    help = "Runs the DeployOps background database checker scheduling loop."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting Database Checker Scheduler Loop..."))
        
        # Limit parallel database check threads to 10
        executor = ThreadPoolExecutor(max_workers=10)
        
        try:
            while True:
                now = timezone.now()
                # Fetch all active databases
                databases = Database.objects.filter(enabled=True)
                
                for db in databases:
                    latest = db.checks.first()
                    
                    # Schedule check if never checked, or interval elapsed
                    should_check = False
                    if not latest:
                        should_check = True
                    else:
                        elapsed = (now - latest.checked_at).total_seconds()
                        # Allow 1s threshold to prevent minor drift delays
                        if elapsed >= (db.check_interval - 1):
                            should_check = True
                            
                    if should_check:
                        self.stdout.write(f"Scheduling database connection check: {db.name} ({db.db_type} -> {db.host})")
                        # Run check asynchronously inside thread pool
                        executor.submit(check_database, db)
                
                # Check for due database connection jobs every 2 seconds
                time.sleep(2)
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nStopping Database Monitor Scheduler..."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Critical error in database checker loop: {e}"))
