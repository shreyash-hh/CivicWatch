from django.urls import path
from .views import dashboard_view, export_complaints_csv, leaderboard_view

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('export/', export_complaints_csv, name='export_csv'),
    path('leaderboard/', leaderboard_view, name='leaderboard'),
]