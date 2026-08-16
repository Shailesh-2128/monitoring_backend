import json
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status

from app.iam.auth import JWTAuthentication
from app.iam.permissions import module_permission
from app.iam.views import log_audit_event

from .models import TelegramConfig, TelegramSubscriber, TelegramNotificationLog
from .serializers import TelegramConfigSerializer, TelegramSubscriberSerializer, TelegramNotificationLogSerializer
from .services import TelegramService


@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('telegram')])
def telegram_settings(request):
    """
    GET: Retrieves global Telegram Configuration.
    POST: Updates Telegram Bot Token, username, and threshold settings.
    """
    config = TelegramConfig.get_config()

    if request.method == 'GET':
        serializer = TelegramConfigSerializer(config)
        return JsonResponse(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        data = request.data
        config.bot_token = data.get('bot_token', config.bot_token).strip()
        config.bot_username = data.get('bot_username', config.bot_username).strip().replace('@', '')
        config.cpu_threshold = float(data.get('cpu_threshold', config.cpu_threshold))
        config.ram_threshold = float(data.get('ram_threshold', config.ram_threshold))
        config.disk_threshold = float(data.get('disk_threshold', config.disk_threshold))
        config.notify_server_overload = bool(data.get('notify_server_overload', config.notify_server_overload))
        config.notify_github_push = bool(data.get('notify_github_push', config.notify_github_push))
        config.save()

        log_audit_event(request, 'TELEGRAM_CONFIG_UPDATE', 'telegram', "Updated Telegram Bot & Alert settings")

        return JsonResponse(TelegramConfigSerializer(config).data, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def generate_connect_link(request):
    """
    Generates a unique verification token for the logged in user
    and returns Telegram Bot start deep link URL: https://t.me/<bot_username>?start=<verification_token>
    """
    config = TelegramConfig.get_config()
    if not config.bot_token or not config.bot_username:
        return JsonResponse({
            "error": "Telegram Bot is not fully configured by administrator. Please set Bot Token and Bot Username first."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Get or create subscriber for user
    sub, created = TelegramSubscriber.objects.get_or_create(user=request.user)
    
    # Generate new token if not verified
    if not sub.is_verified:
        sub.verification_token = f"tg_{uuid.uuid4().hex[:16]}"
        sub.save()

    start_url = f"https://t.me/{config.bot_username}?start={sub.verification_token}"

    log_audit_event(request, 'TELEGRAM_CONNECT_INIT', 'telegram', f"Initiated Telegram connection link for user {request.user.username}")

    return JsonResponse({
        "verification_token": sub.verification_token,
        "bot_username": config.bot_username,
        "start_url": start_url,
        "instructions": "Open our Telegram bot and press START",
        "is_verified": sub.is_verified,
        "chat_id": sub.chat_id,
        "telegram_username": sub.telegram_username
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def connection_status(request):
    """
    Checks connection status for logged in user.
    Also triggers a background update sync if user is pending verification.
    """
    sub = TelegramSubscriber.objects.filter(user=request.user).first()
    
    if sub and not sub.is_verified:
        # Quick poll Telegram API to see if user hit /start
        TelegramService.sync_updates()
        sub.refresh_from_db()

    config = TelegramConfig.get_config()

    if not sub:
        return JsonResponse({
            "is_connected": False,
            "is_verified": False,
            "bot_configured": bool(config.bot_token and config.bot_username)
        }, status=status.HTTP_200_OK)

    return JsonResponse({
        "is_connected": sub.is_verified,
        "is_verified": sub.is_verified,
        "chat_id": sub.chat_id,
        "telegram_username": sub.telegram_username,
        "first_name": sub.first_name,
        "last_name": sub.last_name,
        "connected_at": sub.connected_at.isoformat() if sub.connected_at else None,
        "verification_token": sub.verification_token,
        "notifications_enabled": sub.notifications_enabled,
        "bot_configured": bool(config.bot_token and config.bot_username),
        "bot_username": config.bot_username
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def disconnect_telegram(request):
    """
    Disconnects Telegram account for logged in user.
    """
    sub = TelegramSubscriber.objects.filter(user=request.user).first()
    if sub:
        sub.is_verified = False
        sub.chat_id = ''
        sub.telegram_username = ''
        sub.connected_at = None
        sub.verification_token = f"tg_{uuid.uuid4().hex[:16]}"
        sub.save()

    log_audit_event(request, 'TELEGRAM_DISCONNECT', 'telegram', f"Disconnected Telegram for user {request.user.username}")

    return JsonResponse({"status": "disconnected"}, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def telegram_webhook(request):
    """
    Public webhook receiver for Telegram Bot updates.
    """
    try:
        data = request.data if hasattr(request, 'data') else json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

    result = TelegramService.process_telegram_update(data)
    return JsonResponse(result, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def sync_updates_view(request):
    """
    Polls getUpdates from Telegram API.
    """
    res = TelegramService.sync_updates()
    return JsonResponse(res, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def send_test_notification(request):
    """
    Sends a test Telegram alert to current user's connected Telegram.
    """
    sub = TelegramSubscriber.objects.filter(user=request.user, is_verified=True).first()
    if not sub or not sub.chat_id:
        return JsonResponse({"error": "Telegram account is not connected. Please connect Telegram first."}, status=status.HTTP_400_BAD_REQUEST)

    test_msg = (
        f"🧪 <b>TEST NOTIFICATION</b>\n\n"
        f"Hello <b>{sub.first_name or request.user.username}</b>!\n"
        f"This is a test notification from your <b>DeployOps Monitoring Suite</b>.\n\n"
        f"✅ Your Telegram integration is working perfectly!\n"
        f"⏰ <i>Sent at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
    )

    success, err = TelegramService.send_message(sub.chat_id, test_msg)

    TelegramNotificationLog.objects.create(
        subscriber=sub,
        chat_id=sub.chat_id,
        notification_type='TEST',
        title='Test Notification',
        message=test_msg,
        status='SENT' if success else 'FAILED',
        error_message='' if success else err
    )

    if success:
        return JsonResponse({"message": "Test notification sent successfully to Telegram!"}, status=status.HTTP_200_OK)
    else:
        return JsonResponse({"error": f"Failed to send Telegram message: {err}"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def test_overload_alert(request):
    """
    Simulates a server overload alert notification.
    """
    class DummyServer:
        id = 99
        name = "Production API Cluster #1"
        project_name = "King Wins Core"
        hostname = "ip-10-0-1-45.ec2.internal"
        public_ip = "54.210.12.89"
        environment = "Production"

    class DummyReading:
        cpu = 94.8
        ram = 91.2
        disk = 88.5
        load_average_1m = 12.45

    reasons = [
        "CPU Usage is CRITICAL (94.8% >= 80.0%)",
        "RAM Usage is HIGH (91.2% >= 85.0%)",
        "System 1m Load Average is 12.45"
    ]

    sent_count = TelegramService.send_server_overload_alert(DummyServer(), DummyReading(), reasons)
    return JsonResponse({"message": f"Server Overload simulation sent to {sent_count} verified subscriber(s)."}, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def test_github_push_alert(request):
    """
    Simulates a GitHub push notification.
    """
    commits = [
        {"id": "a1b2c3d4e5f6", "message": "Fix database connection pool bottleneck under high load"},
        {"id": "f9e8d7c6b5a4", "message": "Update Docker deployment configuration"}
    ]
    sent_count = TelegramService.send_github_push_alert(
        repo_name="shailesh/king_wins_backend",
        branch="main",
        pusher="Shailesh (DevOps Lead)",
        commits=commits,
        commit_url="https://github.com/shailesh/king_wins_backend/commit/a1b2c3d4e5f6"
    )
    return JsonResponse({"message": f"GitHub Push simulation sent to {sent_count} verified subscriber(s)."}, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_notification_logs(request):
    """
    Retrieves recent Telegram notification logs.
    """
    logs = TelegramNotificationLog.objects.all().order_by('-created_at')[:50]
    serializer = TelegramNotificationLogSerializer(logs, many=True)
    return JsonResponse(serializer.data, safe=False, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def send_daily_report_view(request):
    """
    Manually triggers sending the daily 9:00 PM system health report to Telegram subscribers.
    """
    from .report_service import DailyReportService
    try:
        sent_count, msg_text = DailyReportService.dispatch_daily_report()
        return JsonResponse({
            "message": f"Daily Health Report dispatched to {sent_count} subscriber(s).",
            "sent_count": sent_count,
            "report_preview": msg_text
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"error": f"Failed to dispatch daily report: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def preview_daily_report_view(request):
    """
    Returns live preview of the daily service health report.
    """
    from .report_service import DailyReportService
    try:
        report_data = DailyReportService.generate_report_data()
        formatted_text = DailyReportService.format_telegram_report(report_data)
        return JsonResponse({
            "report_data": report_data,
            "formatted_text": formatted_text
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"error": f"Failed to generate report preview: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def report_config_view(request):
    """
    GET: Retrieves daily report schedule settings.
    POST: Updates daily report schedule settings (enabled toggle, scheduled time).
    """
    config = TelegramConfig.get_config()
    if request.method == 'POST':
        data = request.data
        if 'daily_report_enabled' in data:
            config.daily_report_enabled = bool(data['daily_report_enabled'])
        if 'daily_report_time' in data and data['daily_report_time']:
            config.daily_report_time = str(data['daily_report_time']).strip()
        config.save()

    return JsonResponse({
        "daily_report_enabled": config.daily_report_enabled,
        "daily_report_time": config.daily_report_time or "21:00",
        "last_daily_report_sent": str(config.last_daily_report_sent) if config.last_daily_report_sent else None
    }, status=status.HTTP_200_OK)

