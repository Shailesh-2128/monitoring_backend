from django.urls import path
from .views import (
    AWSAccountListCreateView,
    AWSAccountDetailView,
    AWSAccountOverviewView,
    AWSAccountVerifyView,
    AWSAccountSyncView,
    EC2InstanceListView,
    EC2InstanceDetailView,
    EC2InstanceMetricsView,
    EC2InstanceControlView,
    EBSVolumeListView,
    SecurityGroupListView,
    ElasticIPListView,
    BillingSummaryView,
    AWSDashboardView,
    AWSCostOverviewView,
    AWSDailyCostTrendView,
    AWSCostByServiceView,
    AWSCostByAccountView,
    AWSDimensionValuesView,
    AWSCostByRegionView,
    AWSCostForecastView,
    AWSBudgetListCreateView,
    AWSBudgetDetailView,
    AWSCostRecommendationsView,
    AWSCostReportExportView
)

urlpatterns = [
    # AWS Account Management
    path('aws/accounts/', AWSAccountListCreateView.as_view(), name='aws-accounts-list-create'),
    path('aws/accounts/<int:pk>/', AWSAccountDetailView.as_view(), name='aws-account-detail'),
    path('aws/accounts/<int:pk>/overview/', AWSAccountOverviewView.as_view(), name='aws-account-overview'),
    path('aws/accounts/<int:pk>/verify/', AWSAccountVerifyView.as_view(), name='aws-account-verify'),
    path('aws/accounts/<int:pk>/sync/', AWSAccountSyncView.as_view(), name='aws-account-sync'),

    # EC2 Module
    path('aws/ec2/', EC2InstanceListView.as_view(), name='aws-ec2-list'),
    path('aws/ec2/<int:pk>/', EC2InstanceDetailView.as_view(), name='aws-ec2-detail'),
    path('aws/ec2/<int:pk>/metrics/', EC2InstanceMetricsView.as_view(), name='aws-ec2-metrics'),
    path('aws/ec2/<int:pk>/<str:action>/', EC2InstanceControlView.as_view(), name='aws-ec2-control'),

    # EBS Module
    path('aws/ebs/', EBSVolumeListView.as_view(), name='aws-ebs-list'),

    # Security Groups Module
    path('aws/security-groups/', SecurityGroupListView.as_view(), name='aws-security-groups-list'),

    # Elastic IP Module
    path('aws/elastic-ips/', ElasticIPListView.as_view(), name='aws-elastic-ips-list'),

    # Billing & Costing Module
    path('aws/billing/', BillingSummaryView.as_view(), name='aws-billing-summary'),
    path('aws/costing/overview/', AWSCostOverviewView.as_view(), name='aws-costing-overview'),
    path('aws/costing/daily-trend/', AWSDailyCostTrendView.as_view(), name='aws-costing-daily-trend'),
    path('aws/costing/by-service/', AWSCostByServiceView.as_view(), name='aws-costing-by-service'),
    path('aws/costing/by-account/', AWSCostByAccountView.as_view(), name='aws-costing-by-account'),
    path('aws/costing/dimension-values/', AWSDimensionValuesView.as_view(), name='aws-costing-dimension-values'),
    path('aws/costing/by-region/', AWSCostByRegionView.as_view(), name='aws-costing-by-region'),
    path('aws/costing/forecast/', AWSCostForecastView.as_view(), name='aws-costing-forecast'),
    path('aws/costing/recommendations/', AWSCostRecommendationsView.as_view(), name='aws-costing-recommendations'),
    path('aws/costing/export/', AWSCostReportExportView.as_view(), name='aws-costing-export'),

    # Budget Management
    path('aws/budgets/', AWSBudgetListCreateView.as_view(), name='aws-budgets-list-create'),
    path('aws/budgets/<int:pk>/', AWSBudgetDetailView.as_view(), name='aws-budget-detail'),

    # Dashboard
    path('aws/dashboard/', AWSDashboardView.as_view(), name='aws-dashboard'),
]

