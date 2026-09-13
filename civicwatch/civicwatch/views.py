from django.shortcuts import render
from user.models import CustomUser, OrganizationProfile

def home(request):
    # Top 5 Organizations by Impact (mock logic based on points)
    top_orgs = CustomUser.objects.filter(role='organization', is_verified=True).order_by('-civic_points')[:5]
    
    # Top 5 Volunteers
    top_volunteers = CustomUser.objects.filter(role='volunteer').order_by('-civic_points')[:5]
    
    context = {
        'top_orgs': top_orgs,
        'top_volunteers': top_volunteers
    }
    return render(request, 'home.html', context)
