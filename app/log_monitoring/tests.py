import uuid
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from app.server_monitoring.models import Server
from .models import LogEntry


class LogMonitoringTests(TestCase):
    def setUp(self):
        self.server = Server.objects.create(
            project_name="Test Project",
            name="Log Server",
            public_ip="1.2.3.4",
            private_ip="10.0.0.1",
            environment="Production",
            os="Ubuntu 24.04"
        )
        self.report_url = reverse('log_report')
        self.list_url = reverse('log_list')
        self.download_url = reverse('log_download')

    def test_log_report_success(self):
        payload = {
            "server_id": self.server.id,
            "token": str(self.server.token),
            "logs": [
                {
                    "log_type": "django",
                    "level": "ERROR",
                    "message": "Database connection failed",
                    "timestamp": "2026-08-01T12:00:00Z"
                },
                {
                    "log_type": "nginx",
                    "level": "INFO",
                    "message": "GET /index.html 200",
                    "timestamp": "2026-08-01T12:01:00Z"
                }
            ]
        }
        res = self.client.post(self.report_url, payload, content_type='application/json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.json()['ingested'], 2)
        self.assertEqual(LogEntry.objects.filter(server=self.server).count(), 2)

    def test_log_report_invalid_token(self):
        payload = {
            "server_id": self.server.id,
            "token": str(uuid.uuid4()),
            "logs": [
                {"log_type": "django", "message": "unauthorized"}
            ]
        }
        res = self.client.post(self.report_url, payload, content_type='application/json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_log_list_filtering(self):
        # Seed test logs
        LogEntry.objects.create(server=self.server, log_type="django", level="ERROR", message="Db failure", timestamp="2026-08-01T12:00:00Z")
        LogEntry.objects.create(server=self.server, log_type="nginx", level="INFO", message="Static file served", timestamp="2026-08-01T12:05:00Z")
        
        # Test server filter
        res = self.client.get(f"{self.list_url}?server_id={self.server.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.json()), 2)

        # Test log_type filter
        res = self.client.get(f"{self.list_url}?log_type=django")
        self.assertEqual(len(res.json()), 1)
        self.assertEqual(res.json()[0]['message'], "Db failure")

        # Test level filter
        res = self.client.get(f"{self.list_url}?level=INFO")
        self.assertEqual(len(res.json()), 1)

        # Test search query
        res = self.client.get(f"{self.list_url}?search=served")
        self.assertEqual(len(res.json()), 1)

    def test_log_download(self):
        LogEntry.objects.create(server=self.server, log_type="django", level="ERROR", message="Crash", timestamp="2026-08-01T12:00:00Z")
        res = self.client.get(f"{self.download_url}?server_id={self.server.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'text/plain')
        self.assertIn('attachment; filename=', res['Content-Disposition'])
        self.assertIn('[DJANGO] [ERROR] Crash', res.content.decode('utf-8'))
