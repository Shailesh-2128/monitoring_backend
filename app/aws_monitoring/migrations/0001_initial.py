from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AWSAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('project', models.CharField(default='King Wins', help_text='Project scope or environment', max_length=255)),
                ('account_name', models.CharField(max_length=255)),
                ('access_key_id', models.CharField(max_length=255)),
                ('secret_access_key', models.TextField(help_text='Fernet encrypted AWS Secret Access Key')),
                ('region', models.CharField(default='ap-south-1', max_length=100)),
                ('enabled', models.BooleanField(default=True)),
                ('last_sync', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EC2Instance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('instance_id', models.CharField(db_index=True, max_length=100)),
                ('instance_name', models.CharField(default='Unnamed-Instance', max_length=255)),
                ('instance_type', models.CharField(default='t3.micro', max_length=100)),
                ('state', models.CharField(default='unknown', max_length=50)),
                ('public_ip', models.CharField(default='N/A', max_length=100)),
                ('private_ip', models.CharField(default='N/A', max_length=100)),
                ('availability_zone', models.CharField(default='ap-south-1a', max_length=100)),
                ('launch_time', models.DateTimeField(blank=True, null=True)),
                ('platform', models.CharField(default='Linux/UNIX', max_length=100)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('aws_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='instances', to='aws_monitoring.awsaccount')),
            ],
            options={
                'ordering': ['-last_updated'],
                'unique_together': {('aws_account', 'instance_id')},
            },
        ),
        migrations.CreateModel(
            name='EC2Metric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cpu', models.FloatField(default=0.0, help_text='CPU Utilization Percentage')),
                ('network_in', models.FloatField(default=0.0, help_text='Network In KB/s')),
                ('network_out', models.FloatField(default=0.0, help_text='Network Out KB/s')),
                ('disk_read', models.FloatField(default=0.0, help_text='Disk Read MB')),
                ('disk_write', models.FloatField(default=0.0, help_text='Disk Write MB')),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('instance', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='metrics', to='aws_monitoring.ec2instance')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='EBSVolumeModel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('volume_id', models.CharField(db_index=True, max_length=100)),
                ('size_gb', models.IntegerField(default=8)),
                ('volume_type', models.CharField(default='gp3', max_length=50)),
                ('iops', models.IntegerField(default=3000)),
                ('throughput', models.IntegerField(default=125)),
                ('encrypted', models.BooleanField(default=False)),
                ('attached_instance_id', models.CharField(default='Unattached', max_length=100)),
                ('state', models.CharField(default='in-use', max_length=50)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('aws_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ebs_volumes', to='aws_monitoring.awsaccount')),
            ],
            options={
                'ordering': ['-last_updated'],
                'unique_together': {('aws_account', 'volume_id')},
            },
        ),
        migrations.CreateModel(
            name='SecurityGroupModel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group_id', models.CharField(db_index=True, max_length=100)),
                ('group_name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('vpc_id', models.CharField(default='N/A', max_length=100)),
                ('inbound_rules', models.JSONField(default=list)),
                ('outbound_rules', models.JSONField(default=list)),
                ('open_ports', models.JSONField(default=list)),
                ('security_score', models.IntegerField(default=100)),
                ('has_risky_rules', models.BooleanField(default=False)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('aws_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='security_groups', to='aws_monitoring.awsaccount')),
            ],
            options={
                'ordering': ['-last_updated'],
                'unique_together': {('aws_account', 'group_id')},
            },
        ),
        migrations.CreateModel(
            name='ElasticIPModel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public_ip', models.CharField(db_index=True, max_length=100)),
                ('allocation_id', models.CharField(default='eipalloc-na', max_length=100)),
                ('associated_instance_id', models.CharField(default='Unassociated', max_length=100)),
                ('network_interface_id', models.CharField(default='N/A', max_length=100)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('aws_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='elastic_ips', to='aws_monitoring.awsaccount')),
            ],
            options={
                'ordering': ['-last_updated'],
                'unique_together': {('aws_account', 'allocation_id')},
            },
        ),
    ]
