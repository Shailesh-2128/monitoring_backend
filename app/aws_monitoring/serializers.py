from rest_framework import serializers
from .models import (
    AWSAccount,
    EC2Instance,
    EC2Metric,
    EBSVolumeModel,
    SecurityGroupModel,
    ElasticIPModel,
    AWSBudget
)


class AWSAccountSerializer(serializers.ModelSerializer):
    secret_access_key = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    access_key_masked = serializers.CharField(source='masked_access_key', read_only=True)

    class Meta:
        model = AWSAccount
        fields = [
            'id',
            'project',
            'account_name',
            'access_key_id',
            'secret_access_key',
            'access_key_masked',
            'region',
            'enabled',
            'last_sync',
            'created_at'
        ]
        read_only_fields = ['id', 'last_sync', 'created_at']

    def to_internal_value(self, data):
        mutable_data = data.copy() if hasattr(data, 'copy') else dict(data)
        if 'name' in mutable_data and 'account_name' not in mutable_data:
            mutable_data['account_name'] = mutable_data['name']
        if 'access_key' in mutable_data and 'access_key_id' not in mutable_data:
            mutable_data['access_key_id'] = mutable_data['access_key']
        if 'secret_key' in mutable_data and 'secret_access_key' not in mutable_data:
            mutable_data['secret_access_key'] = mutable_data['secret_key']
        return super().to_internal_value(mutable_data)

    def create(self, validated_data):
        raw_secret = validated_data.pop('secret_access_key')
        account = AWSAccount(**validated_data)
        account.set_secret_access_key(raw_secret)
        account.save()
        return account

    def update(self, instance, validated_data):
        if 'secret_access_key' in validated_data:
            raw_secret = validated_data.pop('secret_access_key')
            instance.set_secret_access_key(raw_secret)
        return super().update(instance, validated_data)



class EC2InstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = EC2Instance
        fields = [
            'id',
            'aws_account',
            'instance_id',
            'instance_name',
            'instance_type',
            'state',
            'public_ip',
            'private_ip',
            'availability_zone',
            'launch_time',
            'platform',
            'last_updated'
        ]


class EC2MetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = EC2Metric
        fields = [
            'id',
            'instance',
            'cpu',
            'network_in',
            'network_out',
            'disk_read',
            'disk_write',
            'timestamp'
        ]


class EBSVolumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EBSVolumeModel
        fields = [
            'id',
            'aws_account',
            'volume_id',
            'size_gb',
            'volume_type',
            'iops',
            'throughput',
            'encrypted',
            'attached_instance_id',
            'state',
            'last_updated'
        ]


class SecurityGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityGroupModel
        fields = [
            'id',
            'aws_account',
            'group_id',
            'group_name',
            'description',
            'vpc_id',
            'inbound_rules',
            'outbound_rules',
            'open_ports',
            'security_score',
            'has_risky_rules',
            'last_updated'
        ]


class ElasticIPSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElasticIPModel
        fields = [
            'id',
            'aws_account',
            'public_ip',
            'allocation_id',
            'associated_instance_id',
            'network_interface_id',
            'last_updated'
        ]


class AWSDashboardSerializer(serializers.Serializer):
    instances = serializers.IntegerField()
    running = serializers.IntegerField()
    stopped = serializers.IntegerField()
    average_cpu = serializers.FloatField()
    network_in = serializers.CharField()
    network_out = serializers.CharField()
    security_groups = serializers.IntegerField()
    elastic_ips = serializers.IntegerField()
    volumes = serializers.IntegerField()
    estimated_monthly_cost = serializers.CharField()
    health = serializers.CharField()


class AWSBudgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = AWSBudget
        fields = [
            'id',
            'aws_account',
            'name',
            'monthly_budget',
            'currency',
            'email_alert',
            'enabled',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

