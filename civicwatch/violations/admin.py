from django.contrib import admin
from .models import Violation, WorkSubmission, Comment, Certificate


class ViolationAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'status', 'reported_by', 'adopted_by']
    list_filter = ['status', 'category']
    search_fields = ['title', 'description']

admin.site.register(Violation, ViolationAdmin)
admin.site.register(WorkSubmission)
admin.site.register(Comment)
admin.site.register(Certificate)
