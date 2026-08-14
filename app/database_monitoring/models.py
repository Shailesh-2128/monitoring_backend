from django.db import models
from django.utils import timezone


class Database(models.Model):
    DATABASE_TYPES = [
        ('Supabase', 'Supabase'),
        ('Neon', 'Neon'),
        ('Local PostgreSQL', 'Local PostgreSQL'),
        ('AWS RDS PostgreSQL', 'AWS RDS PostgreSQL'),
        ('MySQL', 'MySQL'),
        ('MongoDB', 'MongoDB'),
    ]

    id = models.AutoField(primary_key=True)
    project = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    db_type = models.CharField(max_length=50, choices=DATABASE_TYPES)
    
    # Credentials
    host = models.CharField(max_length=255)
    port = models.IntegerField()
    database_name = models.CharField(max_length=255, null=True, blank=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    password = models.CharField(max_length=255, null=True, blank=True)
    connection_uri = models.TextField(null=True, blank=True)

    # Cloud Infrastructure API Credentials (Supabase / Neon)
    project_ref = models.CharField(max_length=255, null=True, blank=True)
    api_key = models.CharField(max_length=512, null=True, blank=True)

    check_interval = models.IntegerField(default=60)  # in seconds
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.project} - {self.name} ({self.db_type})"


class DatabaseCheck(models.Model):
    id = models.AutoField(primary_key=True)
    database = models.ForeignKey(Database, on_delete=models.CASCADE, related_name='checks')
    status = models.CharField(max_length=50)  # Healthy, Unhealthy
    
    # Telemetry indicators
    response_time = models.FloatField(null=True, blank=True)  # query time in ms
    database_size = models.BigIntegerField(null=True, blank=True)  # in bytes
    active_connections = models.IntegerField(null=True, blank=True)
    long_running_queries = models.JSONField(default=list, blank=True)  # list of query dicts
    
    details = models.JSONField(default=dict, blank=True)  # extra metadata
    error_message = models.TextField(null=True, blank=True)
    checked_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-checked_at']
        indexes = [
            models.Index(fields=['database', 'checked_at']),
        ]

    def __str__(self):
        return f"{self.database.name} - {self.checked_at} - Status: {self.status}"
