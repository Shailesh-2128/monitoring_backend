from unittest.mock import MagicMock, patch
from django.test import TestCase
from django.utils import timezone
from .models import (
    AWSAccount,
    EC2Instance,
    EC2Metric,
    EBSVolumeModel,
    SecurityGroupModel,
    ElasticIPModel
)
from .services import (
    EC2Service,
    CloudWatchService,
    EBSService,
    SecurityGroupService,
    ElasticIPService,
    BillingService,
    HealthService
)
from .exceptions import AWSAuthenticationError, AWSPermissionDeniedError


class AWSMonitoringTestCase(TestCase):
    def setUp(self):
        self.account = AWSAccount.objects.create(
            project="King Wins",
            account_name="Test AWS Account",
            access_key_id="AKIA1234567890TESTKEY",
            region="ap-south-1"
        )
        self.account.set_secret_access_key("test_secret_key_123456")
        self.account.save()

        self.instance = EC2Instance.objects.create(
            aws_account=self.account,
            instance_id="i-test123456789",
            instance_name="Test-EC2-Node",
            instance_type="t3.micro",
            state="running",
            public_ip="1.2.3.4",
            private_ip="10.0.0.1"
        )

    @patch('app.aws_monitoring.services._get_client_for_account')
    def test_sync_instances_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_ec2 = MagicMock()
        mock_client.get_client.return_value = mock_ec2
        mock_get_client.return_value = mock_client

        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-test123456789',
                    'InstanceType': 't3.medium',
                    'State': {'Name': 'running'},
                    'PublicIpAddress': '1.2.3.4',
                    'PrivateIpAddress': '10.0.0.1',
                    'Placement': {'AvailabilityZone': 'ap-south-1a'},
                    'Tags': [{'Key': 'Name', 'Value': 'Test-EC2-Node'}]
                }]
            }]
        }

        synced = EC2Service.sync_instances(self.account)
        self.assertEqual(len(synced), 1)
        self.assertEqual(synced[0].instance_type, 't3.medium')

    @patch('app.aws_monitoring.services._get_client_for_account')
    def test_start_stop_ec2_instance(self, mock_get_client):
        mock_client = MagicMock()
        mock_ec2 = MagicMock()
        mock_client.get_client.return_value = mock_ec2
        mock_get_client.return_value = mock_client

        res_start = EC2Service.start_instance(self.account, 'i-test123456789')
        self.assertIn('starting command issued', res_start['message'])

        res_stop = EC2Service.stop_instance(self.account, 'i-test123456789')
        self.assertIn('stopping command issued', res_stop['message'])

    @patch('app.aws_monitoring.services._get_client_for_account')
    def test_sync_ebs_volumes(self, mock_get_client):
        mock_client = MagicMock()
        mock_ec2 = MagicMock()
        mock_client.get_client.return_value = mock_ec2
        mock_get_client.return_value = mock_client

        mock_ec2.describe_volumes.return_value = {
            'Volumes': [{
                'VolumeId': 'vol-test123',
                'Size': 20,
                'VolumeType': 'gp3',
                'Encrypted': True,
                'State': 'in-use',
                'Attachments': [{'InstanceId': 'i-test123456789'}]
            }]
        }

        vols = EBSService.sync_ebs_volumes(self.account)
        self.assertEqual(len(vols), 1)
        self.assertEqual(vols[0].size_gb, 20)
        self.assertTrue(vols[0].encrypted)

    def test_security_score_calculation(self):
        risky_rules = [
            {'protocol': 'tcp', 'port_range': '22', 'source': '0.0.0.0/0'}
        ]
        score, has_risky = SecurityGroupService.calculate_security_score(risky_rules)
        self.assertTrue(has_risky)
        self.assertLess(score, 100)

        safe_rules = [
            {'protocol': 'tcp', 'port_range': '443', 'source': '0.0.0.0/0'}
        ]
        score_safe, has_risky_safe = SecurityGroupService.calculate_security_score(safe_rules)
        self.assertFalse(has_risky_safe)
        self.assertEqual(score_safe, 100)

    @patch('app.aws_monitoring.services._get_client_for_account')
    def test_billing_missing_permissions_friendly_response(self, mock_get_client):
        mock_get_client.side_effect = AWSPermissionDeniedError("ce:GetCostAndUsage denied")

        res = BillingService.get_billing_summary(self.account)
        self.assertFalse(res['permission_granted'])
        self.assertEqual(res['status'], 'billing_permissions_missing')
        self.assertIn('ce:getcostandusage', res['message'].lower())

    def test_health_calculation(self):
        EC2Metric.objects.create(
            instance=self.instance,
            cpu=12.5,
            network_in=100.0,
            network_out=200.0
        )
        health = HealthService.calculate_health(self.account)
        self.assertEqual(health['overall_health'], 'Healthy')
        self.assertEqual(health['total_instances'], 1)
