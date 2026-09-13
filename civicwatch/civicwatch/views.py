from django.shortcuts import render
from django.db.models import Sum
from user.models import CustomUser
from violations.models import Violation


def home(request):
    # Platform High-Impact Aggregations
    total_reports = Violation.objects.count()
    active_in_progress = Violation.objects.filter(
        status__in=[Violation.Status.ADOPTED, Violation.Status.PENDING_VERIFICATION]
    ).count()
    verified_resolutions = Violation.objects.filter(status=Violation.Status.RESOLVED).count()
    total_civic_credits = CustomUser.objects.aggregate(total=Sum('civic_points'))['total'] or 0

    # Transformations in Action (Resolved violations with submissions & verified photos)
    recent_transformations = Violation.objects.filter(
        status=Violation.Status.RESOLVED,
        submission__isnull=False
    ).select_related('submission', 'adopted_by', 'reported_by').prefetch_related('submission__after_photos').order_by('-created_at')[:6]

    # Top Organizations by Verified Impact
    top_orgs = CustomUser.objects.filter(
        role='organization',
        is_verified=True
    ).order_by('-civic_points')[:5]

    # Top Volunteer Changemakers
    top_volunteers = CustomUser.objects.filter(
        role='volunteer'
    ).order_by('-civic_points')[:5]

    context = {
        'total_reports': total_reports,
        'active_in_progress': active_in_progress,
        'verified_resolutions': verified_resolutions,
        'total_civic_credits': total_civic_credits,
        'recent_transformations': recent_transformations,
        'top_orgs': top_orgs,
        'top_volunteers': top_volunteers,
    }
    return render(request, 'home.html', context)
