from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, VolunteerProfile, OrganizationProfile

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_verified', 'civic_points')
    fieldsets = UserAdmin.fieldsets + (
        ('Civic Info', {'fields': ('role', 'is_verified', 'civic_points', 'phone_number')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(VolunteerProfile)
admin.site.register(OrganizationProfile)
