from django.urls import path
from . import views

urlpatterns = [
    # Server creation and listing
    path('servers/', views.server_list_create, name='server_list_create'),
    
    # Metrics reporting (Agent endpoint)
    path('metrics', views.metrics_report, name='metrics_report'),
    
    # Detail and History endpoints
    path('servers/<int:server_id>/', views.server_detail, name='server_detail'),
    path('servers/<int:server_id>/metrics/', views.server_metrics_history, name='server_metrics_history'),
]
