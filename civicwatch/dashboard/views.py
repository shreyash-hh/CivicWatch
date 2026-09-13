from django.shortcuts import render
from violations.models import Violation
from django.db.models import Count
import json
from django.contrib.auth.decorators import login_required
import csv
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from user.permissions import is_verified_worker_or_admin, admin_required

User = get_user_model()

def leaderboard_view(request):
    """Leaderboard ranking users by civic points, separated by role."""
    # Top Citizens (Civic Watchers)
    top_citizens = User.objects.filter(role='citizen').order_by('-civic_points')[:20]
    
    # Top Heroes (Volunteers and Organizations)
    top_heroes = User.objects.filter(role__in=['volunteer', 'organization']).order_by('-civic_points')[:20]
    
    context = {
        'top_citizens': top_citizens,
        'top_heroes': top_heroes
    }
    return render(request, 'leaderboard.html', context)

@login_required
def dashboard_view(request):
    # Aggregated Stats
    total = Violation.objects.count()
    category_data = Violation.objects.values('category').annotate(count=Count('id'))
    
    # Status Counts
    status_counts = Violation.objects.values('status').annotate(count=Count('id'))
    status_dict = {s['status']: s['count'] for s in status_counts}
    
    # Verification Queue (Wait for approval)
    # If worker/admin, show all pending verification. If citizen, show only their reported issues.
    if is_verified_worker_or_admin(request.user):
        verification_queue = Violation.objects.filter(status='Pending Verification').order_by('-created_at')
    else:
        verification_queue = Violation.objects.filter(status='Pending Verification', reported_by=request.user).order_by('-created_at')

    recent = Violation.objects.order_by('-created_at')[:5]

    category_labels = [item['category'] for item in category_data]
    category_counts = [item['count'] for item in category_data]

    context = {
        'total': total,
        'pending': status_dict.get('Pending', 0),
        'resolved': status_dict.get('Resolved', 0),
        'waiting_approval': status_dict.get('Pending Verification', 0),
        'verification_queue': verification_queue,
        'recent': recent,
        'category_labels': json.dumps(category_labels),
        'category_counts': json.dumps(category_counts),
    }

    return render(request, 'dashboard.html', context)

@admin_required
def export_complaints_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="civicwatch_complaints.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Title', 'Category', 'Status', 'Location', 'Reported By', 'Adopted By', 'Created At'])
    
    violations = Violation.objects.all().order_by('-created_at')
    for v in violations:
        writer.writerow([
            v.id,
            v.title,
            v.get_category_display(),
            v.status,
            v.location,
            v.reported_by.username,
            v.adopted_by.username if v.adopted_by else "None",
            v.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    return response
