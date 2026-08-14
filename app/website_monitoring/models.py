from django.db import models
from django.utils import timezone


class Website(models.Model):
    id = models.AutoField(primary_key=True)
    project = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    url = models.URLField(max_length=1000)
    expected_status = models.IntegerField(default=200)
    check_interval = models.IntegerField(default=60)  # in seconds
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.project} - {self.name} ({self.url})"


class WebsiteCheck(models.Model):
    id = models.AutoField(primary_key=True)
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='checks')
    status = models.CharField(max_length=50)  # Online, Offline, DNS Error, SSL Error
    http_status = models.IntegerField(null=True, blank=True)
    response_time = models.FloatField(null=True, blank=True)  # in ms
    ssl_expiry = models.DateField(null=True, blank=True)
    ssl_valid = models.BooleanField(default=True)
    redirected = models.BooleanField(default=False)
    redirect_url = models.URLField(max_length=1000, null=True, blank=True)
    checked_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-checked_at']
        indexes = [
            models.Index(fields=['website', 'checked_at']),
        ]

    def __str__(self):
        return f"{self.website.name} - {self.checked_at} - Status: {self.status}"
