from django.urls import path
from . import views

urlpatterns = [
    path('settings/', views.telegram_settings, name='telegram_settings'),
    path('connect-link/', views.generate_connect_link, name='telegram_connect_link'),
    path('status/', views.connection_status, name='telegram_status'),
    path('disconnect/', views.disconnect_telegram, name='telegram_disconnect'),
    path('webhook/', views.telegram_webhook, name='telegram_webhook'),
    path('sync/', views.sync_updates_view, name='telegram_sync'),
    path('test-send/', views.send_test_notification, name='telegram_test_send'),
    path('test-overload/', views.test_overload_alert, name='telegram_test_overload'),
    path('test-push/', views.test_github_push_alert, name='telegram_test_push'),
    path('logs/', views.get_notification_logs, name='telegram_logs'),
]
