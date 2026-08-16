from django.db import models
from django.contrib.auth.models import User
import uuid


class TelegramConfig(models.Model):
    bot_token = models.CharField(max_length=255, default='', blank=True, help_text="Telegram Bot Token from @BotFather")
    bot_username = models.CharField(max_length=255, default='', blank=True, help_text="Telegram Bot Username (e.g. DeployOpsBot)")
    webhook_secret = models.CharField(max_length=255, default='', blank=True)
    
    # Alert thresholds
    cpu_threshold = models.FloatField(default=80.0, help_text="CPU percentage overload threshold")
    ram_threshold = models.FloatField(default=85.0, help_text="RAM percentage overload threshold")
    disk_threshold = models.FloatField(default=90.0, help_text="Disk percentage overload threshold")
    
    # Notification Toggles
    notify_server_overload = models.BooleanField(default=True)
    notify_github_push = models.BooleanField(default=True)
    notify_database_backup = models.BooleanField(default=True)
    
    # Daily Service Health Report Settings (Default: 9:00 PM / 21:00)
    daily_report_enabled = models.BooleanField(default=True, help_text="Send daily service health report to Telegram")
    daily_report_time = models.CharField(max_length=10, default='21:00', help_text="Time to send daily report in HH:MM format (24hr, e.g. 21:00 for 9:00 PM)")
    last_daily_report_sent = models.DateField(null=True, blank=True, help_text="Date when daily report was last sent")
    
    last_update_id = models.BigIntegerField(default=0, help_text="Offset for getUpdates polling")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Telegram Config (@{self.bot_username or 'Not Configured'})"

    @classmethod
    def get_config(cls):
        config, _ = cls.objects.get_or_create(id=1)
        return config


class TelegramSubscriber(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='telegram_subscribers', null=True, blank=True)
    chat_id = models.CharField(max_length=100, db_index=True, blank=True, default='')
    telegram_username = models.CharField(max_length=150, blank=True, default='')
    first_name = models.CharField(max_length=150, blank=True, default='')
    last_name = models.CharField(max_length=150, blank=True, default='')
    
    # Connection token for /start deep link flow
    verification_token = models.CharField(max_length=100, unique=True, db_index=True, default=uuid.uuid4)
    is_verified = models.BooleanField(default=False)
    connected_at = models.DateTimeField(null=True, blank=True)
    notifications_enabled = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        user_str = self.user.username if self.user else "Anonymous"
        tg_str = f"@{self.telegram_username}" if self.telegram_username else self.chat_id
        status = "Verified" if self.is_verified else "Pending"
        return f"Subscriber {user_str} - Telegram: {tg_str} [{status}]"


class TelegramNotificationLog(models.Model):
    NOTIFICATION_TYPES = [
        ('SERVER_OVERLOAD', 'Server Overload Alert'),
        ('GITHUB_PUSH', 'GitHub Push Notification'),
        ('DATABASE_BACKUP', 'Database Backup Notification'),
        ('DAILY_REPORT', 'Daily Service Health Report'),
        ('TEST', 'Test Notification'),
        ('SYSTEM', 'System Alert'),
    ]

    subscriber = models.ForeignKey(TelegramSubscriber, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    chat_id = models.CharField(max_length=100, blank=True, default='')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES, default='SYSTEM')
    title = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=50, default='SENT')  # SENT, FAILED
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notification_type}] {self.title} -> {self.chat_id} ({self.status})"
