from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.exceptions import ValidationError
import datetime

from .forms import ViolationForm, WorkSubmissionForm
from .models import Violation, Comment, Certificate, WorkSubmission, WorkSubmissionImage, WorkRating
from .validators import validate_image_file
from .services import haversine_distance, DuplicateDetectionService
from user.models import Notification, VolunteerProfile, OrganizationProfile
from user.permissions import (
    is_verified_worker_or_admin,
    can_adopt_violation,
    can_submit_proof,
    can_verify_resolution,
    verified_worker_required
)


# ================= REPORT VIOLATION =================
@login_required
def report_violation(request):
    if request.method == "POST":
        form = ViolationForm(request.POST, request.FILES)
        if form.is_valid():
            violation = form.save(commit=False)
            violation.reported_by = request.user
            violation.save()
            messages.success(request, "Violation reported successfully!")
            return redirect('violation_list')
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = ViolationForm()
    return render(request, 'report.html', {'form': form})


# ================= LIST + SEARCH + FILTER =================
def violation_list(request):
    violations = Violation.objects.all()
    search_query = request.GET.get('search')
    category = request.GET.get('category')
    status = request.GET.get('status')

    if search_query:
        violations = violations.filter(title__icontains=search_query)
    if category:
        violations = violations.filter(category=category)
    if status:
        violations = violations.filter(status=status)

    paginator = Paginator(violations.order_by('-created_at'), 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'categories': Violation.Category.choices,
        'statuses': Violation.Status.choices,
        'is_worker': is_verified_worker_or_admin(request.user)
    }
    return render(request, 'list.html', context)


# ================= DETAIL VIEW =================
def violation_detail(request, id):
    v = get_object_or_404(Violation, id=id)
    comments = v.comments.all().order_by('-created_at')
    
    if request.method == 'POST' and request.user.is_authenticated:
        text = request.POST.get('text')
        if text:
            Comment.objects.create(violation=v, user=request.user, text=text)
            messages.success(request, "Comment added successfully!")
            return redirect('violation_detail', id=v.id)

    context = {
        'v': v,
        'comments': comments,
        'is_worker': is_verified_worker_or_admin(request.user),
        'can_adopt': can_adopt_violation(request.user, v),
        'can_submit_proof': can_submit_proof(request.user, v),
        'can_verify': can_verify_resolution(request.user, v),
    }
    return render(request, 'detail.html', context)


# ================= WORKFLOW ACTIONS =================

@login_required
@verified_worker_required
def adopt_violation(request, id):
    v = get_object_or_404(Violation, id=id)
    
    # Anti-Self-Dealing: Reporter cannot adopt their own issue
    if v.reported_by_id == request.user.id:
        messages.error(request, "Self-dealing prevented: You cannot adopt your own reported violation.")
        return redirect('violation_detail', id=v.id)

    if v.status != Violation.Status.PENDING:
        messages.error(request, f"Cannot adopt an issue that is in '{v.status}' status.")
        return redirect('violation_detail', id=v.id)

    if v.transition_to(Violation.Status.ADOPTED, user=request.user):
        messages.success(request, f"You have adopted '{v.title}'. Please begin work and submit proof.")
    else:
        messages.error(request, "Unable to adopt this violation.")
    return redirect('violation_detail', id=v.id)


@login_required
def submit_work_proof(request, id):
    v = get_object_or_404(Violation, id=id)
    
    # Check if user is the assigned worker
    if v.adopted_by_id != request.user.id:
        messages.error(request, "You are not the assigned worker for this issue.")
        return redirect('violation_detail', id=v.id)

    # Anti-Self-Dealing: Worker cannot be the reporter
    if v.reported_by_id == request.user.id:
        messages.error(request, "Self-dealing prevented: Reporter cannot submit work proof for their own issue.")
        return redirect('violation_detail', id=v.id)
    
    # Check if status allows proof submission
    if v.status not in [Violation.Status.ADOPTED, Violation.Status.PENDING_VERIFICATION]:
        messages.error(request, f"Cannot submit proof for an issue in '{v.status}' status.")
        return redirect('violation_detail', id=v.id)
    
    if request.method == "POST":
        form = WorkSubmissionForm(request.POST, request.FILES)
        after_photos = request.FILES.getlist('after_photos')
        
        if form.is_valid():
            # Validate all uploaded after_photos
            for photo in after_photos:
                try:
                    validate_image_file(photo)
                except ValidationError as ve:
                    form.add_error(None, f"Invalid 'After' photo: {ve.message}")
                    return render(request, 'submit_proof.html', {'form': form, 'v': v})

            has_existing_photos = False
            if hasattr(v, 'submission') and v.submission:
                has_existing_photos = v.submission.after_photos.exists()
                
            if not after_photos and not has_existing_photos:
                messages.error(request, "Please upload at least one 'After' photo as proof.")
                return render(request, 'submit_proof.html', {'form': form, 'v': v})

            # Check if a submission already exists
            submission, created = WorkSubmission.objects.get_or_create(
                violation=v,
                defaults={'worker': request.user}
            )
            
            # Update fields
            submission.worker = request.user
            submission.work_description = form.cleaned_data['work_description']
            
            # Update before photo if provided or use default
            new_before = request.FILES.get('before_photo')
            if new_before:
                submission.before_photo = new_before
            elif not submission.before_photo and v.image:
                submission.before_photo = v.image
                
            submission.save()
            
            # Update after photos if new ones are provided
            if after_photos:
                submission.after_photos.all().delete()
                for img in after_photos:
                    WorkSubmissionImage.objects.create(submission=submission, image=img)

            # Transition state to PENDING_VERIFICATION
            if v.status == Violation.Status.ADOPTED:
                v.transition_to(Violation.Status.PENDING_VERIFICATION)
            
            messages.success(request, "Work proof submitted successfully! Waiting for verification.")
            return redirect('violation_detail', id=v.id)
        else:
            messages.error(request, "Error submitting proof. Please check the form.")
    else:
        form = WorkSubmissionForm()
    
    return render(request, 'submit_proof.html', {'form': form, 'v': v})


@login_required
def verify_resolution(request, id):
    v = get_object_or_404(Violation, id=id)
    action = request.GET.get('action')

    # Centralized verification permission check
    if not can_verify_resolution(request.user, v):
        messages.error(request, "You are not authorized to verify this resolution or self-dealing was detected.")
        return redirect('violation_detail', id=v.id)

    # Anti-Self-Dealing: Reporter and worker cannot be the same user
    if v.reported_by_id == v.adopted_by_id:
        messages.error(request, "Self-dealing prevented: Reporter and worker cannot be the same user.")
        return redirect('violation_detail', id=v.id)

    if action == 'approve':
        if v.transition_to(Violation.Status.RESOLVED):
            # Point Calculation
            base_worker_points = 50 
            base_reporter_points = 10 
            
            category_impact = {
                'road': 1.5,
                'garbage': 1.0,
                'water': 1.4,
                'electricity': 1.2,
                'drainage': 1.6,
                'encroachment': 1.3,
                'traffic': 1.1,
                'noise': 0.8,
                'air': 1.2,
                'safety': 2.0,
                'animals': 1.0,
                'other': 1.0
            }
            multiplier = category_impact.get(v.category, 1.0)
            
            # Quality Bonus
            rating_bonus = int(getattr(v.submission, 'avg_rating', 0.0) * 5) if hasattr(v, 'submission') else 0
            
            total_worker_points = int((base_worker_points * multiplier) + rating_bonus)
            total_reporter_points = int(base_reporter_points * multiplier)
            
            # Award points to accounts
            if v.adopted_by:
                v.adopted_by.civic_points += total_worker_points
                v.adopted_by.save()
            v.reported_by.civic_points += total_reporter_points
            v.reported_by.save()
            
            # Issue Joint Certificate
            Certificate.objects.get_or_create(
                violation=v,
                defaults={
                    'issued_to_reporter': v.reported_by,
                    'issued_to_worker': v.adopted_by,
                    'points_awarded_reporter': total_reporter_points,
                    'points_awarded_worker': total_worker_points
                }
            )
            
            messages.success(request, f"Issue RESOLVED! {total_worker_points} pts awarded to worker, {total_reporter_points} pts to reporter.")
        else:
            messages.error(request, "Illegal state transition. Resolution could not be completed.")
    elif action == 'reject':
        if v.transition_to(Violation.Status.ADOPTED):
            messages.warning(request, "Proof rejected. The issue is back in 'Adopted' state for the worker to fix.")
        else:
            messages.error(request, "Could not reject proof.")
            
    return redirect('violation_detail', id=v.id)


@login_required
@require_POST
def rate_work_submission(request, submission_id):
    submission = get_object_or_404(WorkSubmission, id=submission_id)
    stars = request.POST.get('stars')
    review = request.POST.get('review', '')

    # Worker cannot rate their own work
    if submission.worker_id == request.user.id:
        messages.error(request, "You cannot rate your own work submission.")
        return redirect('violation_detail', id=submission.violation.id)

    if not stars:
        messages.error(request, "Please select a star rating.")
        return redirect('violation_detail', id=submission.violation.id)

    # Create or update rating
    rating, created = WorkRating.objects.update_or_create(
        submission=submission,
        user=request.user,
        defaults={'stars': int(stars), 'review': review}
    )

    # Update submission averages
    all_ratings = submission.ratings.all()
    submission.rating_count = all_ratings.count()
    submission.avg_rating = sum([r.stars for r in all_ratings]) / submission.rating_count
    submission.save()

    messages.success(request, "Thank you for your feedback!")
    return redirect('violation_detail', id=submission.violation.id)


# ================= MAP & API =================

def map_view(request):
    return render(request, 'map.html')


def map_api(request):
    violations = Violation.objects.all().order_by('-created_at')[:100]
    data = []
    for v in violations:
        data.append({
            'id': v.id,
            'title': v.title,
            'latitude': v.latitude,
            'longitude': v.longitude,
            'category': v.get_category_display(),
            'status': v.status,
            'url': f"/violations/detail/{v.id}/",
            'has_certificate': hasattr(v, 'certificate')
        })
    return JsonResponse(data, safe=False)


# ================= PROXIMITY VOLUNTEER HELP =================

@login_required
def request_volunteer_help(request, id):
    v = get_object_or_404(Violation, id=id)
    
    if v.reported_by_id != request.user.id:
        messages.error(request, "Only the reporter can request help for this issue.")
        return redirect('violation_detail', id=v.id)
    
    if v.is_help_requested:
        messages.warning(request, "Help has already been requested for this issue.")
        return redirect('violation_detail', id=v.id)

    if v.latitude is None or v.longitude is None:
        messages.error(request, "Violation location coordinates are missing.")
        return redirect('violation_detail', id=v.id)

    # 1. Update violation status
    v.is_help_requested = True
    v.requested_at = timezone.now()
    v.save()

    # 2. Find nearby verified volunteers/orgs (within 10km)
    nearby_volunteers = VolunteerProfile.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
        user__is_verified=True
    ).exclude(user=request.user)

    nearby_orgs = OrganizationProfile.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
        user__is_verified=True
    ).exclude(user=request.user)
    
    notified_count = 0
    
    # Notify Volunteers
    for vp in nearby_volunteers:
        dist = haversine_distance(v.longitude, v.latitude, vp.longitude, vp.latitude)
        if dist <= 10:  # 10km radius
            Notification.objects.create(
                user=vp.user,
                title="New Help Request Nearby!",
                message=f"A civic issue '{v.title}' has been reported near your location ({round(dist, 1)}km). Can you help?",
                notification_type='request',
                link=f"/violations/detail/{v.id}/"
            )
            notified_count += 1

    # Notify Organizations
    for op in nearby_orgs:
        dist = haversine_distance(v.longitude, v.latitude, op.longitude, op.latitude)
        if dist <= 10:
            Notification.objects.create(
                user=op.user,
                title="NGO Assistance Requested",
                message=f"A community member requested assistance for '{v.title}' in your area ({round(dist, 1)}km).",
                notification_type='request',
                link=f"/violations/detail/{v.id}/"
            )
            notified_count += 1

    messages.success(request, f"Help request sent to {notified_count} nearby volunteers and organizations!")
    return redirect('violation_detail', id=v.id)


@login_required
def mark_notification_read(request, id):
    notification = get_object_or_404(Notification, id=id, user=request.user)
    notification.is_read = True
    notification.save()
    if notification.link:
        return redirect(notification.link)
    return redirect('profile')


# ================= CERTIFICATES =================

def violation_certificate(request, id):
    v = get_object_or_404(Violation, id=id)
    cert = getattr(v, 'certificate', None)
    if not cert:
        messages.error(request, "Certificate not yet issued.")
        return redirect('violation_detail', id=v.id)
    
    context = {
        'v': v,
        'cert': cert,
        'today': datetime.datetime.now().date(),
    }
    return render(request, 'certificate.html', context)


def verify_certificate(request, verification_id):
    cert = get_object_or_404(Certificate, verification_id=verification_id)
    return render(request, 'verify_certificate.html', {'cert': cert, 'v': cert.violation})
