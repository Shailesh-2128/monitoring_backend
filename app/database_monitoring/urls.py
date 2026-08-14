from django.urls import path
from . import views

urlpatterns = [
    # Database Monitor endpoints
    path('databases/', views.database_list_create, name='database_list_create'),
    path('databases/<int:db_id>/', views.database_detail_delete, name='database_detail_delete'),
    path('databases/<int:db_id>/update/', views.database_update, name='database_update'),
    path('databases/<int:db_id>/metrics/', views.database_metrics_history, name='database_metrics_history'),
    path('databases/<int:db_id>/export-backup/', views.export_database_backup, name='export_database_backup'),
    path('databases/<int:db_id>/import-backup/', views.import_database_backup, name='import_database_backup'),
    path('databases/<int:db_id>/check/', views.run_database_check, name='run_database_check'),
]


