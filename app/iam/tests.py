from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from app.iam.models import Team, Role, UserProfile

class IAMTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # 1. Create Role & Team
        self.admin_role = Role.objects.create(
            name='Superadmin / Admin',
            description='Admin role',
            is_system_role=True,
            permissions={
                'servers': 'write',
                'websites': 'write',
                'databases': 'write',
                'github': 'write',
                'aws': 'write',
                'aws_costing': 'write',
                'iam': 'write',
            }
        )
        
        self.viewer_role = Role.objects.create(
            name='Viewer',
            description='Viewer role',
            is_system_role=True,
            permissions={
                'servers': 'read',
                'websites': 'read',
                'databases': 'read',
                'github': 'read',
                'aws': 'read',
                'aws_costing': 'read',
                'iam': 'none',
            }
        )

        self.team = Team.objects.create(name='Core Ops', description='Operations')

        # 2. Superadmin User
        self.superadmin = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpassword'
        )
        UserProfile.objects.create(
            user=self.superadmin,
            role=self.admin_role,
            team=self.team,
            is_superadmin=True
        )

        # 3. Viewer User
        self.viewer = User.objects.create_user(
            username='viewer',
            email='viewer@test.com',
            password='viewerpassword'
        )
        UserProfile.objects.create(
            user=self.viewer,
            role=self.viewer_role,
            team=self.team,
            is_superadmin=False
        )

    def test_login_success(self):
        response = self.client.post('/api/iam/login/', {
            'username': 'admin',
            'password': 'adminpassword'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['username'], 'admin')

    def test_login_invalid_password(self):
        response = self.client.post('/api/iam/login/', {
            'username': 'admin',
            'password': 'wrongpassword'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_user_as_admin(self):
        login_res = self.client.post('/api/iam/login/', {
            'username': 'admin',
            'password': 'adminpassword'
        }, format='json')
        token = login_res.data['token']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        create_res = self.client.post('/api/iam/users/', {
            'username': 'new_dev',
            'email': 'newdev@test.com',
            'password': 'password123',
            'first_name': 'New',
            'last_name': 'Dev',
            'role_id': self.viewer_role.id,
            'team_id': self.team.id
        }, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.filter(username='new_dev').count(), 1)

    def test_viewer_iam_access_denied(self):
        login_res = self.client.post('/api/iam/login/', {
            'username': 'viewer',
            'password': 'viewerpassword'
        }, format='json')
        token = login_res.data['token']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        get_res = self.client.get('/api/iam/users/')
        self.assertEqual(get_res.status_code, status.HTTP_403_FORBIDDEN)
