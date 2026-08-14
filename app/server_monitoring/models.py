import uuid
from django.db import models
from django.utils import timezone


class Server(models.Model):
    # Auto-incrementing integer ID
    id = models.AutoField(primary_key=True)
    project_name = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    hostname = models.CharField(max_length=255, blank=True)
    public_ip = models.CharField(max_length=50, blank=True)
    private_ip = models.CharField(max_length=50, blank=True)
    environment = models.CharField(max_length=50, blank=True)  # e.g., Production, Staging, Development
    os = models.CharField(max_length=255, blank=True)
    
    # Automatically generated Monitoring Token
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Dynamic hardware specs updated by the agent on reporting
    cpu_model = models.CharField(max_length=255, blank=True)
    total_ram = models.BigIntegerField(default=0)  # in bytes
    total_disk = models.BigIntegerField(default=0)  # in bytes
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.hostname:
            self.hostname = self.name
        super().save(*args, **kwargs)

    @property
    def is_online(self):
        if not self.last_seen:
            return False
        # Online if seen in the last 30 seconds
        return timezone.now() - self.last_seen < timezone.timedelta(seconds=30)

    def __str__(self):
        return f"{self.project_name} - {self.name} (ID: {self.id})"


class MetricReading(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='readings')
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    # Core requested metrics
    cpu = models.FloatField()  # cpu percent
    ram = models.FloatField()  # ram percent
    disk = models.FloatField()  # disk percent
    uptime = models.FloatField()  # in seconds
    
    # Optional extensions for premium visualization
    disk_free = models.BigIntegerField(default=0)  # in bytes
    disk_used = models.BigIntegerField(default=0)  # in bytes
    swap_percent = models.FloatField(default=0.0)
    network_upload = models.BigIntegerField(default=0)  # in bytes/sec
    network_download = models.BigIntegerField(default=0)  # in bytes/sec
    load_average_1m = models.FloatField(default=0.0)
    load_average_5m = models.FloatField(default=0.0)
    load_average_15m = models.FloatField(default=0.0)
    process_count = models.IntegerField(default=0)
    top_processes = models.JSONField(default=list, blank=True)
    services = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['server', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.server.name} (ID: {self.server.id}) - {self.timestamp} - CPU: {self.cpu}%"
