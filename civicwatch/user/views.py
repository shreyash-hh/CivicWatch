from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, get_user_model
from django.contrib import messages
from .forms import CustomUserCreationForm
from violations.models import Violation
from django.contrib.auth.decorators import login_required

User = get_user_model()

def register_request(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful.")
            return redirect("violation_list")
        messages.error(request, "Unsuccessful registration. Invalid information.")
    else:
        form = CustomUserCreationForm()
    return render(request, "registration/register.html", {"form": form})

@login_required
def profile_view(request):
    user_violations = Violation.objects.filter(reported_by=request.user).order_by('-created_at')
    resolved_count = user_violations.filter(status='Resolved').count()
    
    context = {
        'user_violations': user_violations,
        'civic_score': request.user.civic_points,
        'resolved_count': resolved_count
    }
    return render(request, 'profile.html', context)

def public_profile(request, username):
    user = get_object_or_404(User, username=username)
    
    # Reports filed by this user
    reported_violations = Violation.objects.filter(reported_by=user).order_by('-created_at')
    
    # Issues resolved by this user (if they are a volunteer/org)
    resolved_by_user = Violation.objects.filter(adopted_by=user, status='Resolved').order_by('-created_at')
    
    context = {
        'profile_user': user,
        'reported_violations': reported_violations,
        'resolved_by_user': resolved_by_user,
        'is_own_profile': request.user == user
    }
    return render(request, 'public_profile.html', context)
