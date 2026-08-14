from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from .models import Website, WebsiteCheck

class WebsiteMonitoringTests(TestCase):
    def setUp(self):
        self.website = Website.objects.create(
            project="Test Project",
            name="Google Target",
            url="https://www.google.com",
            expected_status=200,
            check_interval=60
        )
        self.list_create_url = reverse('website_list_create')
        self.detail_url = reverse('website_detail_delete', kwargs={'website_id': self.website.id})
        self.history_url = reverse('website_metrics_history', kwargs={'website_id': self.website.id})

    def test_list_websites(self):
        res = self.client.get(self.list_create_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], "Google Target")

    def test_create_website(self):
        payload = {
            "project": "New Web Project",
            "name": "GitHub Target",
            "url": "https://github.com",
            "expected_status": 200,
            "check_interval": 30
        }
        res = self.client.post(self.list_create_url, payload, content_type='application/json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.json()
        self.assertIn('id', data)
        self.assertEqual(data['name'], "GitHub Target")

    def test_website_detail(self):
        res = self.client.get(self.detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['id'], self.website.id)

    def test_delete_website(self):
        res = self.client.delete(self.detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(Website.objects.filter(id=self.website.id).exists())

    def test_website_metrics_history(self):
        # Create a check reading first
        WebsiteCheck.objects.create(
            website=self.website,
            status="Online",
            http_status=200,
            response_time=120.0
        )
        res = self.client.get(self.history_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn('uptime_percentage', data)
        self.assertIn('average_response_time', data)
        self.assertEqual(data['uptime_percentage'], 100.0)
        self.assertEqual(len(data['history']), 1)
