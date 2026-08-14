import logging
from django.utils import timezone

try:
    from celery import shared_task
except ImportError:
    # Fallback decorator if Celery is not installed in the environment
    def shared_task(func):
        return func

from .models import AWSAccount
from .services import (
    EC2Service,
    CloudWatchService,
    EBSService,
    SecurityGroupService,
    ElasticIPService,
    BillingService
)

logger = logging.getLogger(__name__)


@shared_task
def sync_ec2_instances_periodic():
    """Sync EC2 instances every 5 minutes."""
    accounts = AWSAccount.objects.filter(enabled=True)
    count = 0
    for account in accounts:
        try:
            EC2Service.sync_instances(account)
            count += 1
        except Exception as e:
            logger.error(f"Error syncing EC2 instances for {account}: {e}")
    return f"Synced EC2 instances for {count} accounts"


@shared_task
def sync_cloudwatch_metrics_periodic():
    """Sync CloudWatch metrics every 5 minutes."""
    accounts = AWSAccount.objects.filter(enabled=True)
    count = 0
    for account in accounts:
        try:
            CloudWatchService.sync_all_instance_metrics(account)
            count += 1
        except Exception as e:
            logger.error(f"Error syncing CloudWatch metrics for {account}: {e}")
    return f"Synced CloudWatch metrics for {count} accounts"


@shared_task
def sync_ebs_volumes_periodic():
    """Sync EBS volumes every 30 minutes."""
    accounts = AWSAccount.objects.filter(enabled=True)
    count = 0
    for account in accounts:
        try:
            EBSService.sync_ebs_volumes(account)
            count += 1
        except Exception as e:
            logger.error(f"Error syncing EBS volumes for {account}: {e}")
    return f"Synced EBS volumes for {count} accounts"


@shared_task
def sync_security_groups_periodic():
    """Sync Security Groups every 30 minutes."""
    accounts = AWSAccount.objects.filter(enabled=True)
    count = 0
    for account in accounts:
        try:
            SecurityGroupService.sync_security_groups(account)
            count += 1
        except Exception as e:
            logger.error(f"Error syncing Security Groups for {account}: {e}")
    return f"Synced Security Groups for {count} accounts"


@shared_task
def sync_elastic_ips_periodic():
    """Sync Elastic IPs every 30 minutes."""
    accounts = AWSAccount.objects.filter(enabled=True)
    count = 0
    for account in accounts:
        try:
            ElasticIPService.sync_elastic_ips(account)
            count += 1
        except Exception as e:
            logger.error(f"Error syncing Elastic IPs for {account}: {e}")
    return f"Synced Elastic IPs for {count} accounts"


@shared_task
def sync_billing_periodic():
    """Sync Billing summary every 12 hours."""
    accounts = AWSAccount.objects.filter(enabled=True)
    count = 0
    for account in accounts:
        try:
            BillingService.get_billing_summary(account)
            count += 1
        except Exception as e:
            logger.error(f"Error syncing Billing for {account}: {e}")
    return f"Synced Billing for {count} accounts"
