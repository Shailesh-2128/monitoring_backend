from django.urls import path
from . import views

urlpatterns = [
    # Website Monitor endpoints
    path('websites/', views.website_list_create, name='website_list_create'),
    path('websites/<int:website_id>/', views.website_detail_delete, name='website_detail_delete'),
    path('websites/<int:website_id>/metrics/', views.website_metrics_history, name='website_metrics_history'),
]
