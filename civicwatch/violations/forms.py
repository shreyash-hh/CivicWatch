from django import forms
from django.core.exceptions import ValidationError
from .models import Violation, WorkSubmission
from .validators import validate_image_file
from .services import DuplicateDetectionService


class ViolationForm(forms.ModelForm):

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            validate_image_file(image)
        return image

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')

        if category and latitude is not None and longitude is not None:
            exclude_id = self.instance.id if self.instance and self.instance.pk else None
            is_dup, match = DuplicateDetectionService.check_is_duplicate(
                category=category,
                latitude=latitude,
                longitude=longitude,
                exclude_id=exclude_id
            )
            if is_dup and match:
                dup_v = match['violation']
                dist = match['distance_meters']
                raise ValidationError(
                    f"A similar active '{dup_v.get_category_display()}' issue ('{dup_v.title}', ID #{dup_v.id}) "
                    f"has already been reported {dist} meters away from this location."
                )

        return cleaned_data

    class Meta:
        model = Violation
        fields = [
            'category',
            'title',
            'description',
            'image',
            'location',
            'latitude',
            'longitude'
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select mb-3'}),
            'title': forms.TextInput(attrs={'class': 'form-control mb-3', 'placeholder': 'What is the issue?'}),
            'description': forms.Textarea(attrs={'class': 'form-control mb-3', 'rows': 3, 'placeholder': 'Describe the issue in detail...'}),
            'location': forms.TextInput(attrs={'class': 'form-control mb-3', 'placeholder': 'Enter location or use GPS'}),
        }


class WorkSubmissionForm(forms.ModelForm):
    class Meta:
        model = WorkSubmission
        fields = ['before_photo', 'work_description']
        widgets = {
            'work_description': forms.Textarea(attrs={'class': 'form-control mb-3', 'rows': 4, 'placeholder': 'Describe the work performed...'}),
            'before_photo': forms.FileInput(attrs={'class': 'form-control mb-3'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'before_photo' in self.fields:
            self.fields['before_photo'].required = False

    def clean_before_photo(self):
        photo = self.cleaned_data.get('before_photo')
        if photo:
            validate_image_file(photo)
        return photo
