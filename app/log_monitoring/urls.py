from django.urls import path
from . import views

urlpatterns = [
    # Ingest logs from agent
    path('logs/report', views.log_report, name='log_report'),
    
    # Query log entries
    path('logs/', views.log_list, name='log_list'),
    
    # Download logs
    path('logs/download/', views.log_download, name='log_download'),
]
