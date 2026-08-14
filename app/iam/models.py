from django.db import models
from django.contrib.auth.models import User

MODULE_CHOICES = [
    ('servers', 'Server Monitoring'),
    ('websites', 'Website Monitoring'),
    ('databases', 'Database Monitoring'),
    ('github', 'GitHub Monitoring'),
    ('aws', 'AWS Cloud Monitoring'),
    ('aws_costing', 'AWS Costing'),
    ('telegram', 'Telegram Notifications'),
    ('iam', 'User & IAM Management'),
]

PERMISSION_LEVEL_CHOICES = [
    ('none', 'None'),
    ('read', 'Read Only'),
    ('write', 'Read & Write'),
]

class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    permissions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    is_system_role = models.BooleanField(default=False)
    # permissions format: {"servers": "write", "websites": "read", "databases": "none", ...}
    permissions = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='profiles')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    is_superadmin = models.BooleanField(default=False)
    job_title = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.role.name if self.role else 'No Role'})"


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    username = models.CharField(max_length=150)
    action = models.CharField(max_length=50)
    module = models.CharField(max_length=50, choices=MODULE_CHOICES, default='iam')
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.username} - {self.action} ({self.module}): {self.description[:30]}"
