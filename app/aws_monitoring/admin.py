from django.contrib import admin
from .models import (
    AWSAccount,
    EC2Instance,
    EC2Metric,
    EBSVolumeModel,
    SecurityGroupModel,
    ElasticIPModel
)


@admin.register(AWSAccount)
class AWSAccountAdmin(admin.ModelAdmin):
    list_display = ('account_name', 'project', 'masked_access_key', 'region', 'enabled', 'last_sync', 'created_at')
    list_filter = ('enabled', 'region', 'project')
    search_fields = ('account_name', 'access_key_id', 'project')
    readonly_fields = ('created_at', 'last_sync')


@admin.register(EC2Instance)
class EC2InstanceAdmin(admin.ModelAdmin):
    list_display = ('instance_id', 'instance_name', 'aws_account', 'state', 'instance_type', 'public_ip', 'private_ip', 'availability_zone', 'last_updated')
    list_filter = ('state', 'instance_type', 'availability_zone', 'aws_account')
    search_fields = ('instance_id', 'instance_name', 'public_ip', 'private_ip')


@admin.register(EC2Metric)
class EC2MetricAdmin(admin.ModelAdmin):
    list_display = ('instance', 'cpu', 'network_in', 'network_out', 'disk_read', 'disk_write', 'timestamp')
    list_filter = ('instance__aws_account', 'timestamp')
    search_fields = ('instance__instance_id', 'instance__instance_name')


@admin.register(EBSVolumeModel)
class EBSVolumeAdmin(admin.ModelAdmin):
    list_display = ('volume_id', 'aws_account', 'size_gb', 'volume_type', 'encrypted', 'attached_instance_id', 'state', 'last_updated')
    list_filter = ('volume_type', 'encrypted', 'state', 'aws_account')
    search_fields = ('volume_id', 'attached_instance_id')


@admin.register(SecurityGroupModel)
class SecurityGroupAdmin(admin.ModelAdmin):
    list_display = ('group_id', 'group_name', 'aws_account', 'vpc_id', 'security_score', 'has_risky_rules', 'last_updated')
    list_filter = ('has_risky_rules', 'aws_account')
    search_fields = ('group_id', 'group_name', 'vpc_id')


@admin.register(ElasticIPModel)
class ElasticIPAdmin(admin.ModelAdmin):
    list_display = ('public_ip', 'allocation_id', 'aws_account', 'associated_instance_id', 'network_interface_id', 'last_updated')
    list_filter = ('aws_account',)
    search_fields = ('public_ip', 'allocation_id', 'associated_instance_id')
