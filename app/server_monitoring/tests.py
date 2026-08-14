import uuid
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from .models import Server, MetricReading

class ServerMonitoringTests(TestCase):
    def setUp(self):
        self.server = Server.objects.create(
            project_name="Test Project",
            name="Test Server",
            public_ip="1.2.3.4",
            private_ip="10.0.0.1",
            environment="Production",
            os="Ubuntu 24.04"
        )
        self.list_create_url = reverse('server_list_create')
        self.detail_url = reverse('server_detail', kwargs={'server_id': self.server.id})
        self.metrics_report_url = reverse('metrics_report')
        self.history_url = reverse('server_metrics_history', kwargs={'server_id': self.server.id})

    def test_list_servers(self):
        res = self.client.get(self.list_create_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], "Test Server")

    def test_create_server(self):
        payload = {
            "project_name": "New Project",
            "name": "New Server",
            "public_ip": "5.6.7.8",
            "private_ip": "192.168.1.1",
            "environment": "Staging",
            "os": "Debian 12"
        }
        res = self.client.post(self.list_create_url, payload, content_type='application/json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.json()
        self.assertIn('server_id', data)
        self.assertIn('token', data)

    def test_server_detail(self):
        res = self.client.get(self.detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['id'], self.server.id)

    def test_delete_server(self):
        res = self.client.delete(self.detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(Server.objects.filter(id=self.server.id).exists())

    def test_metrics_report_success(self):
        payload = {
            "server_id": self.server.id,
            "token": str(self.server.token),
            "cpu": 15.5,
            "ram": 60.2,
            "disk": 45.1,
            "uptime": 3600.0,
            "load_average": [0.5, 0.4, 0.2],
            "services": {"nginx": True, "redis": False, "gunicorn": True, "celery": False}
        }
        res = self.client.post(self.metrics_report_url, payload, content_type='application/json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        reading = MetricReading.objects.filter(server=self.server).first()
        self.assertIsNotNone(reading)
        self.assertEqual(reading.services.get('nginx'), True)
        self.assertEqual(reading.services.get('redis'), False)

    def test_metrics_report_invalid_token(self):
        payload = {
            "server_id": self.server.id,
            "token": str(uuid.uuid4()),
            "cpu": 15.5,
            "ram": 60.2,
            "disk": 45.1,
            "uptime": 3600.0
        }
        res = self.client.post(self.metrics_report_url, payload, content_type='application/json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
