from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('citizen', 'Citizen'),
        ('volunteer', 'Volunteer/Helper'),
        ('organization', 'Organization/NGO'),
        ('admin', 'Admin'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='citizen')
    civic_points = models.IntegerField(default=0)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    
    # Verification status for Volunteers/Orgs
    is_verified = models.BooleanField(default=False)
    
    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            if self.role == 'volunteer':
                VolunteerProfile.objects.get_or_create(user=self)
            elif self.role == 'organization':
                OrganizationProfile.objects.get_or_create(user=self, org_name=self.username)

    @property
    def is_worker_or_admin(self):
        return self.is_superuser or self.role in ['admin', 'volunteer', 'organization']

class VolunteerProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='volunteer_profile')
    skills = models.CharField(max_length=255, help_text="Plumbing, Cleanup, Tech, etc.")
    identity_proof = models.ImageField(upload_to='verification/volunteers/', null=True, blank=True, help_text="Upload Govt ID (Aadhaar/License)")
    verification_id = models.CharField(max_length=50, blank=True, null=True)
    
    # Address and Location
    address = models.CharField(max_length=255, blank=True, null=True)
    service_radius_km = models.IntegerField(default=5)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Volunteer: {self.user.username}"

class OrganizationProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='org_profile')
    org_name = models.CharField(max_length=255)
    registration_document = models.ImageField(upload_to='verification/orgs/', null=True, blank=True, help_text="Upload NGO/Company Registration")
    registration_number = models.CharField(max_length=100)
    impact_description = models.TextField(blank=True)
    
    # Address and Location
    address = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    adopted_area_name = models.CharField(max_length=255, blank=True, null=True)
    website_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.org_name

class Notification(models.Model):
    TYPE_CHOICES = (
        ('request', 'Help Request'),
        ('info', 'Information'),
        ('status', 'Status Update'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    link = models.CharField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"
