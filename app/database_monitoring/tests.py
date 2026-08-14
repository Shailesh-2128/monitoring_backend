from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from .models import Database, DatabaseCheck


class DatabaseMonitoringTests(TestCase):
    def setUp(self):
        self.db_config = Database.objects.create(
            project="Test Project",
            name="Supabase Instance",
            db_type="Supabase",
            host="db.example.supabase.co",
            port=5432,
            database_name="postgres",
            username="postgres"
        )
        self.list_create_url = reverse('database_list_create')
        self.detail_url = reverse('database_detail_delete', kwargs={'db_id': self.db_config.id})
        self.history_url = reverse('database_metrics_history', kwargs={'db_id': self.db_config.id})

    def test_list_databases(self):
        res = self.client.get(self.list_create_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], "Supabase Instance")

    def test_create_database(self):
        payload = {
            "project": "New Project",
            "name": "Neon Database",
            "db_type": "Neon",
            "host": "ep-example.neon.tech",
            "port": 5432
        }
        res = self.client.post(self.list_create_url, payload, content_type='application/json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.json()
        self.assertIn('id', data)
        self.assertEqual(data['name'], "Neon Database")

    def test_database_detail(self):
        res = self.client.get(self.detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['id'], self.db_config.id)

    def test_delete_database(self):
        res = self.client.delete(self.detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(Database.objects.filter(id=self.db_config.id).exists())

    def test_database_metrics_history(self):
        # Create mock database checks
        DatabaseCheck.objects.create(
            database=self.db_config,
            status="Healthy",
            response_time=42.5,
            database_size=1024 * 1024 * 50,  # 50MB
            active_connections=10
        )
        
        res = self.client.get(self.history_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn('uptime_percentage', data)
        self.assertIn('average_response_time', data)
        self.assertEqual(data['uptime_percentage'], 100.0)
        self.assertEqual(data['average_response_time'], 42.5)
