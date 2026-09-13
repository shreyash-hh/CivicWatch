from rest_framework import serializers
from .models import Violation

class ViolationSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = Violation
        fields = ['id', 'title', 'category', 'category_display', 'status', 'location', 'latitude', 'longitude', 'created_at']
