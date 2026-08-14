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

from .models import Website, WebsiteCheck
from .checker import check_website


@csrf_exempt
@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('websites')])
def website_list_create(request):
    """
    GET: Lists all websites, including their latest check result. Runs live check if needed.
    POST: Registers a new website from the dashboard and immediately probes it.
    """
    if request.method == 'GET':
        websites = Website.objects.all().order_by('-created_at')
        website_data = []

        for w in websites:
            latest = w.checks.first()
            # If no checks or latest check older than 60s, run a live probe
            if not latest or (timezone.now() - latest.checked_at).total_seconds() > 60:
                try:
                    latest = check_website(w)
                except Exception:
                    latest = w.checks.first()

            latest_data = None
            if latest:
                latest_data = {
                    "status": latest.status,
                    "http_status": latest.http_status,
                    "response_time": latest.response_time,
                    "ssl_expiry": latest.ssl_expiry.isoformat() if latest.ssl_expiry else None,
                    "ssl_valid": latest.ssl_valid,
                    "redirected": latest.redirected,
                    "redirect_url": latest.redirect_url,
                    "checked_at": latest.checked_at.isoformat()
                }

            website_data.append({
                "id": w.id,
                "project": w.project,
                "name": w.name,
                "url": w.url,
                "expected_status": w.expected_status,
                "check_interval": w.check_interval,
                "enabled": w.enabled,
                "latest_check": latest_data
            })

        return JsonResponse(website_data, safe=False, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        try:
            data = request.data
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

        project = data.get('project')
        name = data.get('name')
        url = data.get('url')

        if not project or not name or not url:
            return JsonResponse({"error": "project, name, and url are required"}, status=status.HTTP_400_BAD_REQUEST)

        website = Website.objects.create(
            project=project,
            name=name,
            url=url,
            expected_status=data.get('expected_status', 200),
            check_interval=data.get('check_interval', 60),
            enabled=data.get('enabled', True)
        )

        # Immediately trigger an initial probe
        try:
            check_website(website)
        except Exception:
            pass

        return JsonResponse({
            "id": website.id,
            "project": website.project,
            "name": website.name,
            "url": website.url
        }, status=status.HTTP_201_CREATED)


@csrf_exempt
@api_view(['GET', 'DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('websites')])
def website_detail_delete(request, website_id):
    """
    GET: Gets details for a single website and triggers live check if needed.
    DELETE: Deletes the website and its check history.
    """
    website = get_object_or_404(Website, id=website_id)

    if request.method == 'DELETE':
        website.delete()
        return JsonResponse({"status": "deleted"}, status=status.HTTP_200_OK)

    elif request.method == 'GET':
        latest = website.checks.first()
        force_refresh = request.GET.get('refresh') == 'true'

        if not latest or force_refresh or (timezone.now() - latest.checked_at).total_seconds() > 30:
            try:
                latest = check_website(website)
            except Exception:
                latest = website.checks.first()

        latest_data = None
        if latest:
            latest_data = {
                "status": latest.status,
                "http_status": latest.http_status,
                "response_time": latest.response_time,
                "ssl_expiry": latest.ssl_expiry.isoformat() if latest.ssl_expiry else None,
                "ssl_valid": latest.ssl_valid,
                "redirected": latest.redirected,
                "redirect_url": latest.redirect_url,
                "checked_at": latest.checked_at.isoformat()
            }

        return JsonResponse({
            "id": website.id,
            "project": website.project,
            "name": website.name,
            "url": website.url,
            "expected_status": website.expected_status,
            "check_interval": website.check_interval,
            "enabled": website.enabled,
            "latest_check": latest_data
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([module_permission('websites')])
def website_metrics_history(request, website_id):
    """
    GET: Returns historical website check metrics (uptime & response time timeline)
    """
    website = get_object_or_404(Website, id=website_id)

    # If no checks recorded, trigger live probe first
    if not website.checks.exists():
        try:
            check_website(website)
        except Exception:
            pass

    # Range parameters: 1h, 24h, 7d, 30d
    time_range = request.GET.get('range', '1h')
    now = timezone.now()

    if time_range == '1h':
        delta = timezone.timedelta(hours=1)
        step = 1
    elif time_range == '24h':
        delta = timezone.timedelta(hours=24)
        step = 5
    elif time_range == '7d':
        delta = timezone.timedelta(days=7)
        step = 30
    elif time_range == '30d':
        delta = timezone.timedelta(days=30)
        step = 120
    else:
        delta = timezone.timedelta(hours=1)
        step = 1

    start_time = now - delta
    checks = WebsiteCheck.objects.filter(
        website=website,
        checked_at__gte=start_time
    ).order_by('checked_at')

    # If range filter yields 0 checks, fallback to most recent checks
    if not checks.exists():
        checks = WebsiteCheck.objects.filter(website=website).order_by('-checked_at')[:50]
        # Re-sort chronologically for timeline display
        checks = list(reversed(list(checks)))

    total_checks = len(checks)
    online_checks = sum(1 for c in checks if c.status == "Online")
    uptime_percentage = (online_checks / total_checks * 100) if total_checks > 0 else 100.0

    online_readings = [c for c in checks if c.response_time is not None]
    total_response_time = sum(c.response_time for c in online_readings)
    online_count = len(online_readings)
    avg_response_time = (total_response_time / online_count) if online_count > 0 else 0.0

    checks_list = list(checks)
    downsampled = checks_list[::step] if step > 1 else checks_list

    history_data = []
    for c in downsampled:
        history_data.append({
            "timestamp": c.checked_at.isoformat(),
            "response_time": c.response_time,
            "status": c.status,
            "http_status": c.http_status,
            "ssl_valid": c.ssl_valid
        })

    return JsonResponse({
        "uptime_percentage": round(uptime_percentage, 2),
        "average_response_time": round(avg_response_time, 1),
        "history": history_data
    }, status=status.HTTP_200_OK)
