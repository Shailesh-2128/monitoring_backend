from django.db import models
from django.utils import timezone
from .crypto import encrypt_credential, decrypt_credential


class AWSAccount(models.Model):
    project = models.CharField(max_length=255, default='King Wins', help_text="Project scope or environment")
    account_name = models.CharField(max_length=255)
    access_key_id = models.CharField(max_length=255)
    secret_access_key = models.TextField(help_text="Fernet encrypted AWS Secret Access Key")
    region = models.CharField(max_length=100, default='ap-south-1')
    enabled = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.account_name} ({self.region})"

    def masked_access_key(self):
        if self.access_key_id and len(self.access_key_id) > 6:
            return f"{self.access_key_id[:4]}...{self.access_key_id[-4:]}"
        return self.access_key_id

    def set_secret_access_key(self, raw_secret: str):
        self.secret_access_key = encrypt_credential(raw_secret)

    def get_decrypted_secret_key(self) -> str:
        return decrypt_credential(self.secret_access_key)


class EC2Instance(models.Model):
    aws_account = models.ForeignKey(AWSAccount, on_delete=models.CASCADE, related_name='instances')
    instance_id = models.CharField(max_length=100, db_index=True)
    instance_name = models.CharField(max_length=255, default='Unnamed-Instance')
    instance_type = models.CharField(max_length=100, default='t3.micro')
    state = models.CharField(max_length=50, default='unknown')
    public_ip = models.CharField(max_length=100, default='N/A')
    private_ip = models.CharField(max_length=100, default='N/A')
    availability_zone = models.CharField(max_length=100, default='ap-south-1a')
    launch_time = models.DateTimeField(null=True, blank=True)
    platform = models.CharField(max_length=100, default='Linux/UNIX')
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('aws_account', 'instance_id')
        ordering = ['-last_updated']

    def __str__(self):
        return f"{self.instance_name} ({self.instance_id})"


class EC2Metric(models.Model):
    instance = models.ForeignKey(EC2Instance, on_delete=models.CASCADE, related_name='metrics')
    cpu = models.FloatField(default=0.0, help_text="CPU Utilization Percentage")
    network_in = models.FloatField(default=0.0, help_text="Network In KB/s")
    network_out = models.FloatField(default=0.0, help_text="Network Out KB/s")
    disk_read = models.FloatField(default=0.0, help_text="Disk Read MB")
    disk_write = models.FloatField(default=0.0, help_text="Disk Write MB")
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Metrics for {self.instance.instance_id} at {self.timestamp}"


class EBSVolumeModel(models.Model):
    aws_account = models.ForeignKey(AWSAccount, on_delete=models.CASCADE, related_name='ebs_volumes')
    volume_id = models.CharField(max_length=100, db_index=True)
    size_gb = models.IntegerField(default=8)
    volume_type = models.CharField(max_length=50, default='gp3')
    iops = models.IntegerField(default=3000)
    throughput = models.IntegerField(default=125)
    encrypted = models.BooleanField(default=False)
    attached_instance_id = models.CharField(max_length=100, default='Unattached')
    state = models.CharField(max_length=50, default='in-use')
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('aws_account', 'volume_id')
        ordering = ['-last_updated']

    def __str__(self):
        return f"EBS {self.volume_id} ({self.size_gb}GB)"


class SecurityGroupModel(models.Model):
    aws_account = models.ForeignKey(AWSAccount, on_delete=models.CASCADE, related_name='security_groups')
    group_id = models.CharField(max_length=100, db_index=True)
    group_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    vpc_id = models.CharField(max_length=100, default='N/A')
    inbound_rules = models.JSONField(default=list)
    outbound_rules = models.JSONField(default=list)
    open_ports = models.JSONField(default=list)
    security_score = models.IntegerField(default=100)
    has_risky_rules = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('aws_account', 'group_id')
        ordering = ['-last_updated']

    def __str__(self):
        return f"SG {self.group_name} ({self.group_id})"


class ElasticIPModel(models.Model):
    aws_account = models.ForeignKey(AWSAccount, on_delete=models.CASCADE, related_name='elastic_ips')
    public_ip = models.CharField(max_length=100, db_index=True)
    allocation_id = models.CharField(max_length=100, default='eipalloc-na')
    associated_instance_id = models.CharField(max_length=100, default='Unassociated')
    network_interface_id = models.CharField(max_length=100, default='N/A')
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('aws_account', 'allocation_id')
        ordering = ['-last_updated']

    def __str__(self):
        return f"EIP {self.public_ip} ({self.allocation_id})"


class AWSBudget(models.Model):
    aws_account = models.ForeignKey(AWSAccount, on_delete=models.CASCADE, related_name='budgets')
    name = models.CharField(max_length=255)
    monthly_budget = models.DecimalField(max_digits=12, decimal_places=2, default=50.00)
    currency = models.CharField(max_length=10, default='USD')
    email_alert = models.EmailField(blank=True, null=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} (${self.monthly_budget})"

