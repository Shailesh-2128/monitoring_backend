from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from app.iam.models import Team, Role, UserProfile

class Command(BaseCommand):
    help = 'Seeds initial IAM default teams, system roles, and superadmin account.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding IAM teams, roles, and superadmin...')

        # 1. Teams
        teams_data = [
            {'name': 'Platform Operations', 'description': 'Infrastructure & DevOps Management'},
            {'name': 'Development Team', 'description': 'Software Engineering & Web Services'},
            {'name': 'Security & SRE', 'description': 'Site Reliability & Security Operations'},
        ]

        teams_map = {}
        for t in teams_data:
            team_obj, created = Team.objects.get_or_create(
                name=t['name'],
                defaults={'description': t['description']}
            )
            teams_map[t['name']] = team_obj
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Team: {t['name']}"))

        # 2. Roles
        roles_data = [
            {
                'name': 'Superadmin / Admin',
                'description': 'Full administrative control over all system modules and IAM user management.',
                'is_system_role': True,
                'permissions': {
                    'servers': 'write',
                    'websites': 'write',
                    'databases': 'write',
                    'github': 'write',
                    'aws': 'write',
                    'aws_costing': 'write',
                    'iam': 'write',
                }
            },
            {
                'name': 'DevOps Engineer',
                'description': 'Manage servers, databases, AWS cloud infrastructure and costing. Read access for websites & code repositories.',
                'is_system_role': True,
                'permissions': {
                    'servers': 'write',
                    'websites': 'read',
                    'databases': 'write',
                    'github': 'read',
                    'aws': 'write',
                    'aws_costing': 'write',
                    'iam': 'none',
                }
            },
            {
                'name': 'Developer',
                'description': 'Manage website monitors and GitHub repositories. Read access for servers, databases, and AWS.',
                'is_system_role': True,
                'permissions': {
                    'servers': 'read',
                    'websites': 'write',
                    'databases': 'read',
                    'github': 'write',
                    'aws': 'read',
                    'aws_costing': 'none',
                    'iam': 'none',
                }
            },
            {
                'name': 'Viewer',
                'description': 'Read-only access across all monitoring telemetry dashboards.',
                'is_system_role': True,
                'permissions': {
                    'servers': 'read',
                    'websites': 'read',
                    'databases': 'read',
                    'github': 'read',
                    'aws': 'read',
                    'aws_costing': 'read',
                    'iam': 'none',
                }
            },
        ]

        roles_map = {}
        for r in roles_data:
            role_obj, created = Role.objects.get_or_create(
                name=r['name'],
                defaults={
                    'description': r['description'],
                    'is_system_role': r['is_system_role'],
                    'permissions': r['permissions'],
                }
            )
            # Update permissions if role already exists
            if not created and role_obj.is_system_role:
                role_obj.permissions = r['permissions']
                role_obj.save()
            roles_map[r['name']] = role_obj
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Role: {r['name']}"))

        # 3. Superadmin User
        admin_user, user_created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@monitoring.local',
                'first_name': 'Super',
                'last_name': 'Admin',
                'is_superuser': True,
                'is_staff': True,
            }
        )
        if user_created or not admin_user.check_password('admin123'):
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Superadmin account 'admin' created/updated with password 'admin123'."))

        profile, prof_created = UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={
                'role': roles_map['Superadmin / Admin'],
                'team': teams_map['Platform Operations'],
                'is_superadmin': True,
                'job_title': 'Chief System Architect'
            }
        )
        if not prof_created:
            profile.role = roles_map['Superadmin / Admin']
            profile.team = teams_map['Platform Operations']
            profile.is_superadmin = True
            profile.save()

        # 4. Demo Users for quick testing
        demo_users = [
            {
                'username': 'devops_lead',
                'email': 'devops@monitoring.local',
                'password': 'password123',
                'first_name': 'Alex',
                'last_name': 'DevOps',
                'role': 'DevOps Engineer',
                'team': 'Platform Operations',
                'job_title': 'Senior DevOps Engineer'
            },
            {
                'username': 'dev_user',
                'email': 'dev@monitoring.local',
                'password': 'password123',
                'first_name': 'Sarah',
                'last_name': 'Coder',
                'role': 'Developer',
                'team': 'Development Team',
                'job_title': 'Full Stack Developer'
            },
            {
                'username': 'viewer_user',
                'email': 'viewer@monitoring.local',
                'password': 'password123',
                'first_name': 'Morgan',
                'last_name': 'Viewer',
                'role': 'Viewer',
                'team': 'Security & SRE',
                'job_title': 'Monitoring Viewer'
            }
        ]

        for d in demo_users:
            u, created = User.objects.get_or_create(
                username=d['username'],
                defaults={
                    'email': d['email'],
                    'first_name': d['first_name'],
                    'last_name': d['last_name'],
                }
            )
            if created:
                u.set_password(d['password'])
                u.save()
                UserProfile.objects.create(
                    user=u,
                    role=roles_map[d['role']],
                    team=teams_map[d['team']],
                    job_title=d['job_title']
                )
                self.stdout.write(self.style.SUCCESS(f"Created Demo User: {d['username']}"))

        self.stdout.write(self.style.SUCCESS("IAM seeding completed successfully."))
