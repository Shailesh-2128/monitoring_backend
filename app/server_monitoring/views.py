import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework import status
from app.iam.auth import JWTAuthentication
from app.iam.permissions import module_permission
from app.iam.views import log_audit_event

from .models import Server, MetricReading


@csrf_exempt
@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('servers')])
def server_list_create(request):
    """
    GET: Lists all registered servers.
    POST: Creates a new server from the dashboard UI and returns Server ID and Monitoring Token.
    """
    if request.method == 'GET':
        servers = Server.objects.all().order_by('-last_seen', 'project_name', 'name')
        
        server_data = []
        for s in servers:
            latest = s.readings.first()
            latest_data = None
            if latest:
                latest_data = {
                    "timestamp": latest.timestamp.isoformat(),
                    "cpu": latest.cpu,
                    "ram": latest.ram,
                    "disk": latest.disk,
                    "disk_free": latest.disk_free,
                    "disk_used": latest.disk_used,
                    "network_upload": latest.network_upload,
                    "network_download": latest.network_download,
                    "uptime": latest.uptime,
                    "process_count": latest.process_count,
                    "services": latest.services if latest.services else {"nginx": False, "redis": False, "gunicorn": False, "celery": False}
                }
            
            server_data.append({
                "id": s.id,
                "project_name": s.project_name,
                "name": s.name,
                "hostname": s.hostname,
                "public_ip": s.public_ip,
                "private_ip": s.private_ip,
                "environment": s.environment,
                "os": s.os,
                "token": str(s.token),
                "cpu_model": s.cpu_model,
                "total_ram": s.total_ram,
                "total_disk": s.total_disk,
                "is_online": s.is_online,
                "last_seen": s.last_seen.isoformat() if s.last_seen else None,
                "latest_reading": latest_data
            })
            
        return JsonResponse(server_data, safe=False, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        try:
            data = request.data
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

        project_name = data.get('project_name')
        name = data.get('name')
        
        if not project_name or not name:
            return JsonResponse({"error": "project_name and name are required"}, status=status.HTTP_400_BAD_REQUEST)

        server = Server.objects.create(
            project_name=project_name,
            name=name,
            public_ip=data.get('public_ip', ''),
            private_ip=data.get('private_ip', ''),
            environment=data.get('environment', 'Production'),
            os=data.get('os', 'Ubuntu 24.04'),
        )

        log_audit_event(request, 'SERVER_CREATE', 'servers', f"Registered server node '{name}' ({project_name})")

        return JsonResponse({
            "server_id": server.id,
            "token": str(server.token)
        }, status=status.HTTP_201_CREATED)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def metrics_report(request):
    """
    Receives metrics from the running agent.
    Verifies: server_id is valid and token matches.
    """
    try:
        data = request.data
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

    server_id = data.get('server_id')
    token_str = data.get('token')

    if server_id is None or not token_str:
        return JsonResponse({"error": "server_id and token are required"}, status=status.HTTP_400_BAD_REQUEST)

    # 1. Verify server ID is valid
    try:
        server = Server.objects.get(id=server_id)
    except Server.DoesNotExist:
        return JsonResponse({"error": f"Server with ID {server_id} not found"}, status=status.HTTP_404_NOT_FOUND)

    # 2. Verify token matches
    if str(server.token) != str(token_str).strip():
        return JsonResponse({"error": "Invalid monitoring token"}, status=status.HTTP_403_FORBIDDEN)

    # Parse load average
    load_avg = data.get('load_average', [0.0, 0.0, 0.0])
    if isinstance(load_avg, list) and len(load_avg) >= 3:
        load_1m, load_5m, load_15m = load_avg[0], load_avg[1], load_avg[2]
    else:
        load_1m = data.get('load_average_1m', 0.0)
        load_5m = data.get('load_average_5m', 0.0)
        load_15m = data.get('load_average_15m', 0.0)

    # Save metrics reading
    reading = MetricReading.objects.create(
        server=server,
        cpu=data.get('cpu', 0.0),
        ram=data.get('ram', 0.0),
        disk=data.get('disk', 0.0),
        uptime=data.get('uptime', 0.0),
        disk_free=data.get('disk_free', 0),
        disk_used=data.get('disk_used', 0),
        swap_percent=data.get('swap_percent', 0.0),
        network_upload=data.get('network_upload', 0),
        network_download=data.get('network_download', 0),
        load_average_1m=load_1m,
        load_average_5m=load_5m,
        load_average_15m=load_15m,
        process_count=data.get('process_count', 0),
        top_processes=data.get('top_processes', []),
        services=data.get('services', {})
    )

    # Dynamically update static hardware specs if sent by the agent
    updated_fields = ['last_seen']
    server.last_seen = timezone.now()

    if 'cpu_model' in data and not server.cpu_model:
        server.cpu_model = data.get('cpu_model')
        updated_fields.append('cpu_model')
    if 'total_ram' in data and server.total_ram == 0:
        server.total_ram = data.get('total_ram')
        updated_fields.append('total_ram')
    if 'total_disk' in data and server.total_disk == 0:
        server.total_disk = data.get('total_disk')
        updated_fields.append('total_disk')
    if 'hostname' in data and (not server.hostname or server.hostname == server.name):
        server.hostname = data.get('hostname')
        updated_fields.append('hostname')

    server.save(update_fields=updated_fields)

    # Check for Telegram Server Overload Alerts
    try:
        from app.telegram_monitoring.models import TelegramConfig, TelegramNotificationLog
        from app.telegram_monitoring.services import TelegramService

        config = TelegramConfig.get_config()
        if config.notify_server_overload:
            reasons = []
            if reading.cpu >= config.cpu_threshold:
                reasons.append(f"CPU usage ({reading.cpu:.1f}%) >= threshold ({config.cpu_threshold:.1f}%)")
            if reading.ram >= config.ram_threshold:
                reasons.append(f"RAM usage ({reading.ram:.1f}%) >= threshold ({config.ram_threshold:.1f}%)")
            if reading.disk >= config.disk_threshold:
                reasons.append(f"Disk usage ({reading.disk:.1f}%) >= threshold ({config.disk_threshold:.1f}%)")

            if reasons:
                # Throttling check (5 minutes cooldown per server to avoid spam)
                last_log = TelegramNotificationLog.objects.filter(
                    notification_type='SERVER_OVERLOAD',
                    title__icontains=server.name
                ).order_by('-created_at').first()

                should_send = True
                if last_log and (timezone.now() - last_log.created_at).total_seconds() < 300:
                    should_send = False

                if should_send:
                    TelegramService.send_server_overload_alert(server, reading, reasons)
    except Exception as e:
        # Prevent telemetry report failure if Telegram notification fails
        pass

    return JsonResponse({"status": "success", "reading_id": reading.id}, status=status.HTTP_201_CREATED)


@api_view(['GET', 'DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('servers')])
def server_detail(request, server_id):
    """
    GET: Gets detailed status of a single server.
    DELETE: Deletes the server and all its metrics from the database.
    """
    server = get_object_or_404(Server, id=server_id)
    
    if request.method == 'DELETE':
        server.delete()
        return JsonResponse({"status": "deleted"}, status=status.HTTP_200_OK)
    
    latest = server.readings.first()
    latest_data = None
    if latest:
        latest_data = {
            "timestamp": latest.timestamp.isoformat(),
            "cpu": latest.cpu,
            "ram": latest.ram,
            "disk": latest.disk,
            "disk_free": latest.disk_free,
            "disk_used": latest.disk_used,
            "swap_percent": latest.swap_percent,
            "network_upload": latest.network_upload,
            "network_download": latest.network_download,
            "load_average_1m": latest.load_average_1m,
            "load_average_5m": latest.load_average_5m,
            "load_average_15m": latest.load_average_15m,
            "uptime": latest.uptime,
            "process_count": latest.process_count,
            "top_processes": latest.top_processes,
            "services": latest.services if latest.services else {"nginx": False, "redis": False, "gunicorn": False, "celery": False}
        }

    return JsonResponse({
        "id": server.id,
        "project_name": server.project_name,
        "name": server.name,
        "hostname": server.hostname,
        "os": server.os,
        "environment": server.environment,
        "total_ram": server.total_ram,
        "total_disk": server.total_disk,
        "public_ip": server.public_ip,
        "private_ip": server.private_ip,
        "token": str(server.token),
        "is_online": server.is_online,
        "last_seen": server.last_seen.isoformat() if server.last_seen else None,
        "latest_reading": latest_data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('servers')])
def server_metrics_history(request, server_id):
    """
    Gets historical metrics for charts, with downsampling.
    """
    server = get_object_or_404(Server, id=server_id)
    
    # Query param range: 1h, 6h, 24h, 7d
    time_range = request.GET.get('range', '1h')
    now = timezone.now()
    
    if time_range == '1h':
        delta = timezone.timedelta(hours=1)
        step = 1  # No downsampling
    elif time_range == '6h':
        delta = timezone.timedelta(hours=6)
        step = 4  # Take 1 in 4 readings
    elif time_range == '24h':
        delta = timezone.timedelta(hours=24)
        step = 15  # Take 1 in 15 readings
    elif time_range == '7d':
        delta = timezone.timedelta(days=7)
        step = 100  # Take 1 in 100 readings
    else:
        delta = timezone.timedelta(hours=1)
        step = 1
        
    start_time = now - delta
    readings = MetricReading.objects.filter(
        server=server, 
        timestamp__gte=start_time
    ).order_by('timestamp')
    
    readings_list = list(readings)
    downsampled = readings_list[::step] if step > 1 else readings_list
    
    history_data = []
    for r in downsampled:
        history_data.append({
            "timestamp": r.timestamp.isoformat(),
            "cpu_percent": r.cpu,
            "ram_percent": r.ram,
            "disk_percent": r.disk,
            "network_upload": r.network_upload,
            "network_download": r.network_download,
            "swap_percent": r.swap_percent,
            "load_average_1m": r.load_average_1m,
            "uptime": r.uptime,
        })
        
    return JsonResponse(history_data, safe=False, status=status.HTTP_200_OK)
