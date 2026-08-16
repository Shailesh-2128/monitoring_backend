import logging
from django.utils import timezone
from app.server_monitoring.models import Server, MetricReading
from app.website_monitoring.models import Website, WebsiteCheck
from app.database_monitoring.models import Database, DatabaseCheck
from app.github_monitoring.models import Project as GitHubProject
from app.aws_monitoring.models import AWSAccount, EC2Instance
from .models import TelegramConfig, TelegramSubscriber, TelegramNotificationLog
from .services import TelegramService

logger = logging.getLogger(__name__)


class DailyReportService:

    @classmethod
    def generate_report_data(cls) -> dict:
        """
        Gathers comprehensive metrics & status across all monitored services.
        """
        now = timezone.now()
        now_str = now.strftime('%Y-%m-%d %H:%M:%S UTC')
        date_str = now.strftime('%d %b %Y')

        # 1. Servers Report
        servers = Server.objects.all()
        server_list = []
        server_healthy_count = 0
        server_offline_count = 0

        for server in servers:
            reading = MetricReading.objects.filter(server=server).first()
            is_online = server.is_online
            cpu = reading.cpu if reading else 0.0
            ram = reading.ram if reading else 0.0
            disk = reading.disk if reading else 0.0
            
            is_healthy = is_online and cpu < 85.0 and ram < 85.0 and disk < 90.0
            if is_healthy:
                server_healthy_count += 1
            else:
                server_offline_count += 1

            server_list.append({
                'id': server.id,
                'name': server.name,
                'project_name': server.project_name,
                'hostname': server.hostname or server.name,
                'public_ip': server.public_ip or 'N/A',
                'environment': server.environment or 'Production',
                'is_online': is_online,
                'is_healthy': is_healthy,
                'cpu': round(cpu, 1),
                'ram': round(ram, 1),
                'disk': round(disk, 1),
                'last_seen': server.last_seen.strftime('%H:%M:%S UTC') if server.last_seen else 'Never'
            })

        # 2. Websites Report
        websites = Website.objects.all()
        website_list = []
        website_online_count = 0

        for web in websites:
            latest_check = WebsiteCheck.objects.filter(website=web).first()
            status = latest_check.status if latest_check else ('Online' if web.enabled else 'Disabled')
            http_code = latest_check.http_status if latest_check else 200
            resp_time = latest_check.response_time if latest_check else 0.0
            is_healthy = (status == 'Online') and (http_code == 200 or http_code == web.expected_status)

            if is_healthy:
                website_online_count += 1

            website_list.append({
                'id': web.id,
                'name': web.name,
                'project': web.project,
                'url': web.url,
                'status': status,
                'is_healthy': is_healthy,
                'http_status': http_code,
                'response_time': round(resp_time, 1) if resp_time else 0
            })

        # 3. Databases Report
        databases = Database.objects.all()
        database_list = []
        database_healthy_count = 0

        for db in databases:
            latest_check = DatabaseCheck.objects.filter(database=db).first()
            status = latest_check.status if latest_check else ('Healthy' if db.enabled else 'Unknown')
            resp_time = latest_check.response_time if latest_check else 0.0
            connections = latest_check.active_connections if latest_check else 0
            is_healthy = (status == 'Healthy')

            if is_healthy:
                database_healthy_count += 1

            database_list.append({
                'id': db.id,
                'name': db.name,
                'project': db.project,
                'db_type': db.db_type,
                'host': db.host,
                'status': status,
                'is_healthy': is_healthy,
                'response_time': round(resp_time, 1) if resp_time else 0,
                'active_connections': connections or 0
            })

        # 4. GitHub Projects Summary
        github_projects = GitHubProject.objects.all()
        github_list = [{
            'id': p.id,
            'name': p.name,
            'repo': f"{p.github_owner}/{p.github_repo}",
            'branch': p.default_branch
        } for p in github_projects]

        # 5. AWS Summary
        aws_accounts = AWSAccount.objects.all()
        aws_ec2_count = EC2Instance.objects.count()
        aws_running_ec2 = EC2Instance.objects.filter(state='running').count()

        total_services = len(servers) + len(websites) + len(databases) + len(github_projects) + len(aws_accounts)
        total_healthy = server_healthy_count + website_online_count + database_healthy_count + len(github_projects) + len(aws_accounts)
        health_score = round((total_healthy / total_services * 100), 1) if total_services > 0 else 100.0

        return {
            'timestamp': now_str,
            'date_str': date_str,
            'summary': {
                'total_services': total_services,
                'total_healthy': total_healthy,
                'total_degraded_down': total_services - total_healthy,
                'health_score': health_score,
                'server_counts': {'total': len(servers), 'healthy': server_healthy_count, 'down': server_offline_count},
                'website_counts': {'total': len(websites), 'healthy': website_online_count, 'down': len(websites) - website_online_count},
                'database_counts': {'total': len(databases), 'healthy': database_healthy_count, 'down': len(databases) - database_healthy_count},
                'github_count': len(github_projects),
                'aws_count': len(aws_accounts),
                'aws_ec2': {'total': aws_ec2_count, 'running': aws_running_ec2}
            },
            'servers': server_list,
            'websites': website_list,
            'databases': database_list,
            'github': github_list,
            'aws': [{'name': a.account_name, 'region': a.region} for a in aws_accounts]
        }

    @classmethod
    def format_telegram_report(cls, data: dict) -> str:
        """
        Formats report data into a beautiful HTML Telegram message.
        """
        summary = data['summary']
        date_str = data['date_str']

        score_emoji = "🟢" if summary['health_score'] >= 90 else ("🟡" if summary['health_score'] >= 70 else "🔴")

        msg = (
            f"📊 <b>DAILY SYSTEM HEALTH REPORT</b> 📊\n"
            f"🗓️ <b>Date:</b> {date_str} (9:00 PM Daily Check)\n"
            f"-----------------------------------------\n"
            f"{score_emoji} <b>Infrastructure Health Score: {summary['health_score']}%</b>\n"
            f"✅ Healthy Services: <b>{summary['total_healthy']}/{summary['total_services']}</b>\n\n"
        )

        # Servers
        msg += f"🖥️ <b>SERVERS REPORT ({summary['server_counts']['healthy']}/{summary['server_counts']['total']} Healthy)</b>\n"
        if data['servers']:
            for s in data['servers']:
                icon = "🟢" if s['is_healthy'] else ("🟡" if s['is_online'] else "🔴")
                status_text = "ONLINE" if s['is_online'] else "OFFLINE"
                msg += (
                    f"{icon} <b>{s['name']}</b> [{s['environment']}]\n"
                    f"   • IP: <code>{s['public_ip']}</code> | Status: {status_text}\n"
                    f"   • CPU: {s['cpu']}% | RAM: {s['ram']}% | Disk: {s['disk']}%\n"
                )
        else:
            msg += "   <i>No servers registered.</i>\n"

        # Websites
        msg += f"\n🌐 <b>WEBSITES REPORT ({summary['website_counts']['healthy']}/{summary['website_counts']['total']} Up)</b>\n"
        if data['websites']:
            for w in data['websites']:
                icon = "🟢" if w['is_healthy'] else "🔴"
                msg += (
                    f"{icon} <b>{w['name']}</b>\n"
                    f"   • URL: {w['url']}\n"
                    f"   • Status: <code>{w['status']} ({w['http_status']})</code> | Latency: {w['response_time']}ms\n"
                )
        else:
            msg += "   <i>No website monitors configured.</i>\n"

        # Databases
        msg += f"\n🗄️ <b>DATABASES REPORT ({summary['database_counts']['healthy']}/{summary['database_counts']['total']} Healthy)</b>\n"
        if data['databases']:
            for db in data['databases']:
                icon = "🟢" if db['is_healthy'] else "🔴"
                msg += (
                    f"{icon} <b>{db['name']}</b> ({db['db_type']})\n"
                    f"   • Host: <code>{db['host']}</code>\n"
                    f"   • Status: {db['status']} | Query Time: {db['response_time']}ms\n"
                )
        else:
            msg += "   <i>No databases configured.</i>\n"

        # Repos & AWS
        msg += f"\n📦 <b>REPOSITORIES & CLOUD</b>\n"
        msg += f"   • GitHub Monitored Repos: <b>{summary['github_count']}</b>\n"
        msg += f"   • AWS Accounts: <b>{summary['aws_count']}</b> (EC2: {summary['aws_ec2']['running']}/{summary['aws_ec2']['total']} Running)\n"

        msg += f"\n⏰ <i>Generated at: {data['timestamp']}</i>\n"
        msg += f"🤖 <i>DeployOps Automated Daily Monitor</i>"

        return msg

    @classmethod
    def dispatch_daily_report(cls) -> tuple[int, str]:
        """
        Generates and dispatches daily report to all verified Telegram subscribers.
        Returns (sent_count, message_text).
        """
        report_data = cls.generate_report_data()
        message_text = cls.format_telegram_report(report_data)

        subscribers = TelegramSubscriber.objects.filter(is_verified=True, notifications_enabled=True).exclude(chat_id='')
        sent_count = 0

        for sub in subscribers:
            success, err = TelegramService.send_message(sub.chat_id, message_text)
            TelegramNotificationLog.objects.create(
                subscriber=sub,
                chat_id=sub.chat_id,
                notification_type='DAILY_REPORT',
                title=f"Daily Infrastructure Health Report ({report_data['date_str']})",
                message=message_text,
                status='SENT' if success else 'FAILED',
                error_message='' if success else err
            )
            if success:
                sent_count += 1

        # Update last sent date in TelegramConfig
        config = TelegramConfig.get_config()
        config.last_daily_report_sent = timezone.now().date()
        config.save(update_fields=['last_daily_report_sent'])

        return sent_count, message_text
