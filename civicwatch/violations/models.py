from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
import uuid
from .validators import sanitize_and_strip_exif


class Violation(models.Model):

    class Category(models.TextChoices):
        ROAD = 'road', 'Road Damage and Potholes'
        GARBAGE = 'garbage', 'Garbage and Waste'
        WATER = 'water', 'Water Supply/Leakage'
        ELECTRICITY = 'electricity', 'Street Lighting'
        DRAINAGE = 'drainage', 'Drainage/Sewage'
        ENCROACHMENT = 'encroachment', 'Encroachment'
        TRAFFIC = 'traffic', 'Traffic & Parking'
        NOISE = 'noise', 'Noise Pollution'
        AIR = 'air', 'Air Pollution'
        SAFETY = 'safety', 'Public Safety Hazard'
        ANIMALS = 'animals', 'Stray Animals'
        OTHER = 'other', 'Other'

    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=Category.choices)
    image = models.ImageField(upload_to='violations/', null=True, blank=True)
    
    # Location info
    location = models.CharField(max_length=255)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Status(models.TextChoices):
        PENDING = 'Pending', 'Pending'
        ADOPTED = 'Adopted', 'Adopted (In Progress)'
        PENDING_VERIFICATION = 'Pending Verification', 'Pending Verification'
        RESOLVED = 'Resolved', 'Resolved'
        REJECTED = 'Rejected', 'Rejected'

    status = models.CharField(max_length=50, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reported_violations'
    )
    
    adopted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='adopted_violations'
    )
    
    # Help Request Tracking
    is_help_requested = models.BooleanField(default=False)
    requested_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(reported_by=models.F('adopted_by')),
                name='prevent_self_adoption'
            )
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.reported_by_id and self.adopted_by_id and self.reported_by_id == self.adopted_by_id:
            raise ValidationError({
                'adopted_by': "Self-dealing prevented: A user cannot adopt or resolve their own reported violation."
            })

    # Manual State Transitions & Validation
    def can_transition_to(self, new_status, user=None):
        """
        Validates state transition legality and prevents self-dealing.
        """
        # Strict state machine transition map
        allowed_transitions = {
            self.Status.PENDING: [self.Status.ADOPTED, self.Status.REJECTED],
            self.Status.ADOPTED: [self.Status.PENDING_VERIFICATION],
            self.Status.PENDING_VERIFICATION: [self.Status.RESOLVED, self.Status.ADOPTED],
            self.Status.RESOLVED: [],  # Terminal state
            self.Status.REJECTED: [self.Status.PENDING]
        }

        if new_status not in allowed_transitions.get(self.status, []):
            return False

        # Anti-self-dealing check on adoption
        if new_status == self.Status.ADOPTED:
            adopting_user = user or self.adopted_by
            if adopting_user and self.reported_by_id and adopting_user.id == self.reported_by_id:
                return False

        # Anti-self-dealing check on resolution
        if new_status == self.Status.RESOLVED:
            if self.adopted_by_id and self.reported_by_id and self.adopted_by_id == self.reported_by_id:
                return False

        return True

    def transition_to(self, new_status, user=None):
        """
        Executes transition if legal. Returns True on success, False otherwise.
        """
        if not self.can_transition_to(new_status, user=user):
            return False

        if new_status == self.Status.ADOPTED and user:
            self.adopted_by = user

        self.status = new_status
        self.save()
        return True

    def save(self, *args, **kwargs):
        # Run clean validation
        self.clean()

        # Sanitize image and strip EXIF
        if self.image and not str(self.image.name).startswith('compressed_'):
            self.image = sanitize_and_strip_exif(self.image)

        super().save(*args, **kwargs)


class WorkSubmission(models.Model):
    violation = models.OneToOneField(Violation, on_delete=models.CASCADE, related_name='submission')
    worker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    before_photo = models.ImageField(upload_to='submissions/before/', null=True, blank=True)
    work_description = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    # Rating System
    avg_rating = models.FloatField(default=0.0)
    rating_count = models.IntegerField(default=0)

    def clean(self):
        super().clean()
        if self.violation_id and self.worker_id and self.violation.reported_by_id == self.worker_id:
            raise ValidationError("Self-dealing prevented: Reporter cannot submit work proof for their own violation.")

    def save(self, *args, **kwargs):
        self.clean()
        if self.before_photo and not str(self.before_photo.name).startswith('compressed_'):
            self.before_photo = sanitize_and_strip_exif(self.before_photo)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Proof for {self.violation.title} by {self.worker.username}"


class WorkRating(models.Model):
    submission = models.ForeignKey(WorkSubmission, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stars = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    review = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('submission', 'user')

    def clean(self):
        super().clean()
        # Prevent worker from rating their own submission
        if self.submission_id and self.user_id and self.submission.worker_id == self.user_id:
            raise ValidationError("Workers cannot rate their own work submission.")


class WorkSubmissionImage(models.Model):
    submission = models.ForeignKey(WorkSubmission, on_delete=models.CASCADE, related_name='after_photos')
    image = models.ImageField(upload_to='submissions/after/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.image and not str(self.image.name).startswith('compressed_'):
            self.image = sanitize_and_strip_exif(self.image)
        super().save(*args, **kwargs)


class Comment(models.Model):
    violation = models.ForeignKey(Violation, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Certificate(models.Model):
    violation = models.OneToOneField(Violation, on_delete=models.CASCADE, related_name='certificate')
    verification_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Dual Recognition
    issued_to_reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reporter_certificates')
    issued_to_worker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='worker_certificates', null=True, blank=True)
    
    points_awarded_reporter = models.IntegerField(default=10)
    points_awarded_worker = models.IntegerField(default=20)
    
    issued_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if self.issued_to_reporter_id and self.issued_to_worker_id and self.issued_to_reporter_id == self.issued_to_worker_id:
            raise ValidationError("Self-dealing prevented: Reporter and worker cannot be the same user on a certificate.")

    def __str__(self):
        return f"Cert: {self.verification_id} - {self.violation.title}"
