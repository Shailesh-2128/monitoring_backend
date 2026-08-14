import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework import status

from app.server_monitoring.models import Server
from .models import LogEntry


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def log_report(request):
    """
    POST: Ingest logs reported by the server monitoring agent.
    Payload:
    {
        "server_id": 1,
        "token": "...",
        "logs": [
            {"log_type": "django", "level": "ERROR", "message": "...", "timestamp": "..."}
        ]
    }
    """
    try:
        data = request.data
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

    server_id = data.get('server_id')
    token = data.get('token')
    logs = data.get('logs', [])

    if not server_id or not token:
        return JsonResponse({"error": "server_id and token are required"}, status=status.HTTP_400_BAD_REQUEST)

    server = get_object_or_404(Server, id=server_id)
    if str(server.token) != str(token):
        return JsonResponse({"error": "Invalid token"}, status=status.HTTP_403_FORBIDDEN)

    created_count = 0
    for entry in logs:
        log_type = entry.get('log_type')
        level = entry.get('level', 'INFO')
        message = entry.get('message')
        timestamp_str = entry.get('timestamp')

        if not log_type or not message:
            continue

        timestamp = parse_datetime(timestamp_str) if timestamp_str else timezone.now()
        if not timestamp:
            timestamp = timezone.now()

        LogEntry.objects.create(
            server=server,
            log_type=log_type,
            level=level,
            message=message,
            timestamp=timestamp
        )
        created_count += 1

    return JsonResponse({"status": "success", "ingested": created_count}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def log_list(request):
    """
    GET: List indexed log entries with queries, filters, and limits.
    """
    server_id = request.GET.get('server_id')
    log_type = request.GET.get('log_type')
    level = request.GET.get('level')
    search_query = request.GET.get('search')
    limit_str = request.GET.get('limit', '100')

    try:
        limit = int(limit_str)
    except ValueError:
        limit = 100

    queryset = LogEntry.objects.all()

    if server_id:
        queryset = queryset.filter(server_id=server_id)
    if log_type:
        queryset = queryset.filter(log_type=log_type)
    if level:
        queryset = queryset.filter(level=level)
    if search_query:
        queryset = queryset.filter(message__icontains=search_query)

    # Slice entries
    logs = queryset.order_by('-timestamp')[:limit]
    
    log_data = []
    for log in logs:
        log_data.append({
            "id": log.id,
            "log_type": log.log_type,
            "level": log.level,
            "message": log.message,
            "timestamp": log.timestamp.isoformat()
        })

    return JsonResponse(log_data, safe=False, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def log_download(request):
    """
    GET: Downloads filtered logs as a plain text file.
    """
    server_id = request.GET.get('server_id')
    log_type = request.GET.get('log_type')
    level = request.GET.get('level')
    search_query = request.GET.get('search')
    limit_str = request.GET.get('limit', '500')

    try:
        limit = int(limit_str)
    except ValueError:
        limit = 500

    queryset = LogEntry.objects.all()

    if server_id:
        server = get_object_or_404(Server, id=server_id)
        queryset = queryset.filter(server=server)
        server_name = server.name.replace(" ", "_")
    else:
        server_name = "All_Servers"

    if log_type:
        queryset = queryset.filter(log_type=log_type)
    if level:
        queryset = queryset.filter(level=level)
    if search_query:
        queryset = queryset.filter(message__icontains=search_query)

    logs = queryset.order_by('-timestamp')[:limit]

    # Format entries as plain text file lines
    lines = []
    for log in reversed(list(logs)):  # Oldest first for logical log reading order
        timestamp_str = log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        lines.append(f"[{timestamp_str}] [{log.log_type.upper()}] [{log.level}] {log.message}\n")

    content = "".join(lines)
    response = HttpResponse(content, content_type='text/plain')
    
    filename = f"{server_name}_logs_{timezone.now().strftime('%Y%m%d_%H%M%S')}.txt"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
