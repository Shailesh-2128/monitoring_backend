import time
from concurrent.futures import ThreadPoolExecutor
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.website_monitoring.models import Website
from app.website_monitoring.checker import check_website


class Command(BaseCommand):
    help = "Runs the DeployOps background website checker scheduling loop."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting Website Checker Scheduler Loop..."))
        
        # Limit parallel worker threads to 10
        executor = ThreadPoolExecutor(max_workers=10)
        
        try:
            while True:
                now = timezone.now()
                # Fetch all active websites
                websites = Website.objects.filter(enabled=True)
                
                for website in websites:
                    latest = website.checks.first()
                    
                    # Schedule check if never checked, or interval elapsed
                    should_check = False
                    if not latest:
                        should_check = True
                    else:
                        elapsed = (now - latest.checked_at).total_seconds()
                        # Allow 1s threshold to prevent minor drift delays
                        if elapsed >= (website.check_interval - 1):
                            should_check = True
                            
                    if should_check:
                        self.stdout.write(f"Scheduling check: {website.name} ({website.url})")
                        # Run check asynchronously inside thread pool
                        executor.submit(check_website, website)
                
                # Check for due jobs every 2 seconds
                time.sleep(2)
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nStopping Website Monitor Scheduler..."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Critical error in checker loop: {e}"))
