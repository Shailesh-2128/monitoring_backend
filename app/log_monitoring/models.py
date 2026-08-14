from django.db import models
from app.server_monitoring.models import Server


class LogEntry(models.Model):
    LOG_TYPES = [
        ('django', 'Django'),
        ('gunicorn', 'Gunicorn'),
        ('nginx', 'Nginx'),
        ('celery', 'Celery'),
        ('system', 'System'),
    ]

    LEVELS = [
        ('INFO', 'INFO'),
        ('WARNING', 'WARNING'),
        ('ERROR', 'ERROR'),
        ('DEBUG', 'DEBUG'),
    ]

    id = models.AutoField(primary_key=True)
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='logs')
    log_type = models.CharField(max_length=50, choices=LOG_TYPES)
    level = models.CharField(max_length=20, choices=LEVELS, default='INFO')
    message = models.TextField()
    timestamp = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['server', 'log_type', 'level', 'timestamp']),
        ]

    def __str__(self):
        return f"[{self.level}] {self.server.name} - {self.log_type} - {self.message[:50]}"
