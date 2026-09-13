from django.urls import path
from . import views

urlpatterns = [
    path('report/', views.report_violation, name='report_violation'),
    path('list/', views.violation_list, name='violation_list'),
    path('map/', views.map_view, name='map'),
    path('detail/<int:id>/', views.violation_detail, name='violation_detail'),
    path('certificate/<int:id>/', views.violation_certificate, name='violation_certificate'),
    
    # Workflow Actions
    path('adopt/<int:id>/', views.adopt_violation, name='adopt_violation'),
    path('submit-proof/<int:id>/', views.submit_work_proof, name='submit_work_proof'),
    path('verify-resolution/<int:id>/', views.verify_resolution, name='verify_resolution'),
    path('rate-work/<int:submission_id>/', views.rate_work_submission, name='rate_work'),
    
    # Help Requests
    path('request-help/<int:id>/', views.request_volunteer_help, name='request_help'),
    path('notification/read/<int:id>/', views.mark_notification_read, name='mark_notification_read'),
    
    # API endpoints
    path('api/list/', views.map_api, name='api_violation_list'),
    
    # Verification
    path('verify/<uuid:verification_id>/', views.verify_certificate, name='verify_certificate'),
]
