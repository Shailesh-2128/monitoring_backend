from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework import status
from app.iam.auth import JWTAuthentication
from app.iam.permissions import module_permission

from .models import Database, DatabaseCheck
from .checker import check_database
from .backup_service import export_database_sql, import_database_sql
from app.telegram_monitoring.services import TelegramService


def _get_connection_uri(db):
    if db.connection_uri:
        return db.connection_uri
    user = db.username or 'postgres'
    pwd = db.password or ''
    host = db.host or 'localhost'
    port = db.port or 5432
    dbname = db.database_name or 'postgres'
    
    scheme = 'mysql' if 'mysql' in (db.db_type or '').lower() else 'postgresql'
    if pwd:
        return f"{scheme}://{user}:{pwd}@{host}:{port}/{dbname}"
    else:
        return f"{scheme}://{user}@{host}:{port}/{dbname}"


@csrf_exempt
@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('databases')])
def database_list_create(request):
    """
    GET: List all databases.
    POST: Create a new database target and trigger instant connection check.
    """
    if request.method == 'GET':
        databases = Database.objects.all().order_by('-created_at')
        db_data = []
        
        for db in databases:
            latest = db.checks.first()
            if not latest:
                try:
                    latest = check_database(db)
                except Exception:
                    latest = None

            latest_data = None
            if latest:
                latest_data = {
                    "status": latest.status,
                    "response_time": latest.response_time,
                    "database_size": latest.database_size,
                    "active_connections": latest.active_connections,
                    "long_running_queries": latest.long_running_queries,
                    "error_message": latest.error_message,
                    "details": latest.details,
                    "checked_at": latest.checked_at.isoformat()
                }
            
            db_data.append({
                "id": db.id,
                "project": db.project,
                "name": db.name,
                "db_type": db.db_type,
                "host": db.host,
                "port": db.port,
                "database_name": db.database_name,
                "username": db.username,
                "connection_uri": _get_connection_uri(db),
                "project_ref": db.project_ref,
                "api_key": db.api_key,
                "check_interval": db.check_interval,
                "enabled": db.enabled,
                "latest_check": latest_data
            })
            
        return JsonResponse(db_data, safe=False, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        try:
            data = request.data
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)
            
        project = data.get('project')
        name = data.get('name')
        db_type = data.get('db_type')
        host = data.get('host')
        port = data.get('port')
        
        if not project or not name or not db_type or not host or not port:
            return JsonResponse({"error": "project, name, db_type, host, and port are required"}, status=status.HTTP_400_BAD_REQUEST)
            
        db = Database.objects.create(
            project=project,
            name=name,
            db_type=db_type,
            host=host,
            port=port,
            database_name=data.get('database_name'),
            username=data.get('username'),
            password=data.get('password'),
            connection_uri=data.get('connection_uri'),
            project_ref=data.get('project_ref'),
            api_key=data.get('api_key'),
            check_interval=data.get('check_interval', 60),
            enabled=data.get('enabled', True)
        )

        # Trigger instant connection check
        try:
            check_database(db)
        except Exception:
            pass
        
        return JsonResponse({
            "id": db.id,
            "project": db.project,
            "name": db.name,
            "db_type": db.db_type,
            "host": db.host,
            "port": db.port,
            "connection_uri": _get_connection_uri(db),
            "project_ref": db.project_ref,
            "api_key": db.api_key
        }, status=status.HTTP_201_CREATED)


@csrf_exempt
@api_view(['GET', 'POST', 'DELETE', 'PATCH', 'PUT'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('databases')])
def database_detail_delete(request, db_id):
    """
    GET: Gets details for a single database.
    DELETE: Deletes the database and its check history.
    POST/PATCH/PUT: Updates database settings (check_interval, enabled, project_ref, api_key, etc.).
    """
    db = get_object_or_404(Database, id=db_id)
    
    if request.method == 'DELETE':
        db.delete()
        return JsonResponse({"status": "deleted"}, status=status.HTTP_200_OK)
        
    elif request.method in ['POST', 'PATCH', 'PUT']:
        data = request.data
        if 'check_interval' in data:
            db.check_interval = int(data['check_interval'])
        if 'enabled' in data:
            db.enabled = bool(data['enabled'])
        if 'name' in data:
            db.name = str(data['name'])
        if 'project' in data:
            db.project = str(data['project'])
        if 'project_ref' in data:
            db.project_ref = str(data['project_ref'])
        if 'api_key' in data:
            db.api_key = str(data['api_key'])
        db.save()
        return JsonResponse({
            "id": db.id,
            "name": db.name,
            "project_ref": db.project_ref,
            "api_key": db.api_key,
            "check_interval": db.check_interval,
            "enabled": db.enabled
        }, status=status.HTTP_200_OK)

    elif request.method == 'GET':
        latest = db.checks.first()
        if not latest:
            try:
                latest = check_database(db)
            except Exception:
                latest = None

        latest_data = None
        if latest:
            latest_data = {
                "status": latest.status,
                "response_time": latest.response_time,
                "database_size": latest.database_size,
                "active_connections": latest.active_connections,
                "long_running_queries": latest.long_running_queries,
                "error_message": latest.error_message,
                "details": latest.details,
                "checked_at": latest.checked_at.isoformat()
            }
            
        return JsonResponse({
            "id": db.id,
            "project": db.project,
            "name": db.name,
            "db_type": db.db_type,
            "host": db.host,
            "port": db.port,
            "database_name": db.database_name,
            "username": db.username,
            "connection_uri": _get_connection_uri(db),
            "project_ref": db.project_ref,
            "api_key": db.api_key,
            "check_interval": db.check_interval,
            "enabled": db.enabled,
            "latest_check": latest_data
        }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST', 'PATCH', 'PUT'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('databases')])
def database_update(request, db_id):
    """
    POST/PATCH/PUT: Dedicated endpoint to update database settings & connection parameters.
    """
    db = get_object_or_404(Database, id=db_id)
    data = request.data
    if 'check_interval' in data:
        db.check_interval = int(data['check_interval'])
    if 'enabled' in data:
        db.enabled = bool(data['enabled'])
    if 'name' in data:
        db.name = str(data['name'])
    if 'project' in data:
        db.project = str(data['project'])
    if 'host' in data:
        db.host = str(data['host'])
    if 'port' in data:
        try:
            db.port = int(data['port'])
        except (ValueError, TypeError):
            pass
    if 'database_name' in data:
        db.database_name = str(data['database_name'])
    if 'username' in data:
        db.username = str(data['username'])
    if 'password' in data and data['password']:
        db.password = str(data['password'])
    if 'connection_uri' in data:
        db.connection_uri = str(data['connection_uri'])
    if 'project_ref' in data:
        db.project_ref = str(data['project_ref'])
    if 'api_key' in data:
        db.api_key = str(data['api_key'])
    db.save()
    return JsonResponse({
        "id": db.id,
        "name": db.name,
        "host": db.host,
        "port": db.port,
        "connection_uri": _get_connection_uri(db),
        "project_ref": db.project_ref,
        "api_key": db.api_key,
        "check_interval": db.check_interval,
        "enabled": db.enabled
    }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('databases')])
def run_database_check(request, db_id):
    """
    POST: Triggers an immediate connection test & telemetry check for the specified database.
    """
    db = get_object_or_404(Database, id=db_id)
    latest = check_database(db)
    
    latest_data = None
    if latest:
        latest_data = {
            "status": latest.status,
            "response_time": latest.response_time,
            "database_size": latest.database_size,
            "active_connections": latest.active_connections,
            "long_running_queries": latest.long_running_queries,
            "error_message": latest.error_message,
            "details": latest.details,
            "checked_at": latest.checked_at.isoformat()
        }
        
    return JsonResponse({
        "status": "success",
        "latest_check": latest_data
    }, status=status.HTTP_200_OK)



@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('databases')])
def database_metrics_history(request, db_id):
    """
    GET: Returns historical database check metrics (uptime percentage, average response time, size, and connection stats)
    """
    db = get_object_or_404(Database, id=db_id)
    
    # Range parameters: 1h, 24h, 7d, 30d
    time_range = request.GET.get('range', '1h')
    now = timezone.now()
    
    if time_range == '1h':
        delta = timezone.timedelta(hours=1)
        step = 1  # No downsampling
    elif time_range == '24h':
        delta = timezone.timedelta(hours=24)
        step = 5  # Take 1 in 5 checks
    elif time_range == '7d':
        delta = timezone.timedelta(days=7)
        step = 30  # Take 1 in 30 checks
    elif time_range == '30d':
        delta = timezone.timedelta(days=30)
        step = 120  # Take 1 in 120 checks
    else:
        delta = timezone.timedelta(hours=1)
        step = 1
        
    start_time = now - delta
    checks = DatabaseCheck.objects.filter(
        database=db,
        checked_at__gte=start_time
    ).order_by('checked_at')
    
    total_checks = checks.count()
    healthy_checks = checks.filter(status="Healthy").count()
    uptime_percentage = (healthy_checks / total_checks * 100) if total_checks > 0 else 100.0
    
    # Average response time
    healthy_readings = checks.filter(status="Healthy", response_time__isnull=False)
    total_response_time = sum(c.response_time for c in healthy_readings)
    healthy_count = healthy_readings.count()
    avg_response_time = (total_response_time / healthy_count) if healthy_count > 0 else 0.0
    
    # Latest database size and connections
    latest = checks.last()
    current_size = latest.database_size if latest else None
    current_connections = latest.active_connections if latest else None
    
    checks_list = list(checks)
    downsampled = checks_list[::step] if step > 1 else checks_list
    
    history_data = []
    for c in downsampled:
        history_data.append({
            "timestamp": c.checked_at.isoformat(),
            "response_time": c.response_time,
            "status": c.status,
            "database_size": c.database_size,
            "active_connections": c.active_connections
        })
        
    return JsonResponse({
        "uptime_percentage": round(uptime_percentage, 2),
        "average_response_time": round(avg_response_time, 1),
        "current_size": current_size,
        "current_connections": current_connections,
        "history": history_data
    }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('databases')])
def export_database_backup(request, db_id):
    """
    GET: Dumps full SQL database backup and streams as downloadable backup.sql file.
    Triggers Telegram alert notification.
    """
    db = get_object_or_404(Database, id=db_id)
    username = request.user.username if getattr(request, 'user', None) and request.user.is_authenticated else "System User"

    try:
        sql_content = export_database_sql(db)
        clean_name = db.name.lower().replace(" ", "_")
        filename = f"{clean_name}_backup.sql"
        size_bytes = len(sql_content.encode('utf-8'))
        
        # Format size string
        if size_bytes > 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
        elif size_bytes > 1024:
            size_str = f"{size_bytes / 1024:.2f} KB"
        else:
            size_str = f"{size_bytes} Bytes"

        # Dispatch Telegram Alert
        try:
            TelegramService.send_database_backup_alert(
                database=db,
                action_type="EXPORT",
                file_name=filename,
                file_size_str=size_str,
                username=username,
                is_success=True
            )
        except Exception as te:
            pass

        response = HttpResponse(sql_content, content_type='application/sql')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        err_msg = str(e)
        clean_name = db.name.lower().replace(" ", "_")
        filename = f"{clean_name}_backup.sql"
        try:
            TelegramService.send_database_backup_alert(
                database=db,
                action_type="EXPORT",
                file_name=filename,
                username=username,
                is_success=False,
                error_msg=err_msg
            )
        except Exception:
            pass

        return JsonResponse({"error": f"Backup export failed: {err_msg}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('databases')])
def import_database_backup(request, db_id):
    """
    POST: Uploads an .sql file and executes it on the specified database.
    Triggers Telegram alert notification.
    """
    db = get_object_or_404(Database, id=db_id)
    username = request.user.username if getattr(request, 'user', None) and request.user.is_authenticated else "System User"

    if 'file' not in request.FILES:
        return JsonResponse({"error": "No SQL backup file provided in request. Use form-data field 'file'."}, status=status.HTTP_400_BAD_REQUEST)

    uploaded_file = request.FILES['file']
    filename = uploaded_file.name
    size_bytes = uploaded_file.size

    if size_bytes > 1024 * 1024:
        size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
    elif size_bytes > 1024:
        size_str = f"{size_bytes / 1024:.2f} KB"
    else:
        size_str = f"{size_bytes} Bytes"

    try:
        sql_content = uploaded_file.read().decode('utf-8', errors='ignore')
        result = import_database_sql(db, sql_content)

        # Dispatch Telegram Alert
        try:
            TelegramService.send_database_backup_alert(
                database=db,
                action_type="IMPORT",
                file_name=filename,
                file_size_str=size_str,
                username=username,
                is_success=True
            )
        except Exception:
            pass

        return JsonResponse({
            "status": "success",
            "message": f"Successfully executed backup queries against database {db.name}",
            "details": result
        }, status=status.HTTP_200_OK)

    except Exception as e:
        err_msg = str(e)
        try:
            TelegramService.send_database_backup_alert(
                database=db,
                action_type="IMPORT",
                file_name=filename,
                file_size_str=size_str,
                username=username,
                is_success=False,
                error_msg=err_msg
            )
        except Exception:
            pass

        return JsonResponse({"error": f"Backup import failed: {err_msg}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@csrf_exempt
@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('databases')])
def database_list_create(request):
    """
    GET: Lists all databases, including their latest check result.
    POST: Registers a new database configuration.
    """
    if request.method == 'GET':
        databases = Database.objects.all().order_by('-created_at')
        db_data = []
        
        for db in databases:
            latest = db.checks.first()
            latest_data = None
            if latest:
                latest_data = {
                    "status": latest.status,
                    "response_time": latest.response_time,
                    "database_size": latest.database_size,
                    "active_connections": latest.active_connections,
                    "checked_at": latest.checked_at.isoformat()
                }
            
            db_data.append({
                "id": db.id,
                "project": db.project,
                "name": db.name,
                "db_type": db.db_type,
                "host": db.host,
                "port": db.port,
                "database_name": db.database_name,
                "username": db.username,
                "check_interval": db.check_interval,
                "enabled": db.enabled,
                "latest_check": latest_data
            })
            
        return JsonResponse(db_data, safe=False, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        try:
            data = request.data
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)
            
        project = data.get('project')
        name = data.get('name')
        db_type = data.get('db_type')
        host = data.get('host')
        port = data.get('port')
        
        if not project or not name or not db_type or not host or not port:
            return JsonResponse({"error": "project, name, db_type, host, and port are required"}, status=status.HTTP_400_BAD_REQUEST)
            
        db = Database.objects.create(
            project=project,
            name=name,
            db_type=db_type,
            host=host,
            port=port,
            database_name=data.get('database_name'),
            username=data.get('username'),
            password=data.get('password'),
            connection_uri=data.get('connection_uri'),
            check_interval=data.get('check_interval', 60),
            enabled=data.get('enabled', True)
        )
        
        return JsonResponse({
            "id": db.id,
            "project": db.project,
            "name": db.name,
            "db_type": db.db_type,
            "host": db.host,
            "port": db.port
        }, status=status.HTTP_201_CREATED)


@csrf_exempt
@api_view(['GET', 'DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('databases')])
def database_detail_delete(request, db_id):
    """
    GET: Gets details for a single database.
    DELETE: Deletes the database and its check history.
    """
    db = get_object_or_404(Database, id=db_id)
    
    if request.method == 'DELETE':
        db.delete()
        return JsonResponse({"status": "deleted"}, status=status.HTTP_200_OK)
        
    elif request.method == 'GET':
        latest = db.checks.first()
        latest_data = None
        if latest:
            latest_data = {
                "status": latest.status,
                "response_time": latest.response_time,
                "database_size": latest.database_size,
                "active_connections": latest.active_connections,
                "long_running_queries": latest.long_running_queries,
                "error_message": latest.error_message,
                "details": latest.details,
                "checked_at": latest.checked_at.isoformat()
            }
            
        return JsonResponse({
            "id": db.id,
            "project": db.project,
            "name": db.name,
            "db_type": db.db_type,
            "host": db.host,
            "port": db.port,
            "database_name": db.database_name,
            "username": db.username,
            "check_interval": db.check_interval,
            "enabled": db.enabled,
            "latest_check": latest_data
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('databases')])
def database_metrics_history(request, db_id):
    """
    GET: Returns historical database check metrics (uptime percentage, average response time, size, and connection stats)
    """
    db = get_object_or_404(Database, id=db_id)
    
    # Range parameters: 1h, 24h, 7d, 30d
    time_range = request.GET.get('range', '1h')
    now = timezone.now()
    
    if time_range == '1h':
        delta = timezone.timedelta(hours=1)
        step = 1  # No downsampling
    elif time_range == '24h':
        delta = timezone.timedelta(hours=24)
        step = 5  # Take 1 in 5 checks
    elif time_range == '7d':
        delta = timezone.timedelta(days=7)
        step = 30  # Take 1 in 30 checks
    elif time_range == '30d':
        delta = timezone.timedelta(days=30)
        step = 120  # Take 1 in 120 checks
    else:
        delta = timezone.timedelta(hours=1)
        step = 1
        
    start_time = now - delta
    checks = DatabaseCheck.objects.filter(
        database=db,
        checked_at__gte=start_time
    ).order_by('checked_at')
    
    total_checks = checks.count()
    healthy_checks = checks.filter(status="Healthy").count()
    uptime_percentage = (healthy_checks / total_checks * 100) if total_checks > 0 else 100.0
    
    # Average response time
    healthy_readings = checks.filter(status="Healthy", response_time__isnull=False)
    total_response_time = sum(c.response_time for c in healthy_readings)
    healthy_count = healthy_readings.count()
    avg_response_time = (total_response_time / healthy_count) if healthy_count > 0 else 0.0
    
    # Latest database size and connections
    latest = checks.last()
    current_size = latest.database_size if latest else None
    current_connections = latest.active_connections if latest else None
    
    checks_list = list(checks)
    downsampled = checks_list[::step] if step > 1 else checks_list
    
    history_data = []
    for c in downsampled:
        history_data.append({
            "timestamp": c.checked_at.isoformat(),
            "response_time": c.response_time,
            "status": c.status,
            "database_size": c.database_size,
            "active_connections": c.active_connections
        })
        
    return JsonResponse({
        "uptime_percentage": round(uptime_percentage, 2),
        "average_response_time": round(avg_response_time, 1),
        "current_size": current_size,
        "current_connections": current_connections,
        "history": history_data
    }, status=status.HTTP_200_OK)
