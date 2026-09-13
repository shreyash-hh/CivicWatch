from io import BytesIO
from PIL import Image
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.utils import IntegrityError
from django.contrib.auth import get_user_model

from .models import Violation, WorkSubmission, WorkSubmissionImage, WorkRating, Certificate
from .services import DuplicateDetectionService
from .validators import validate_image_file, sanitize_and_strip_exif

User = get_user_model()


class ViolationAuditBaseTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Create test users
        self.citizen = User.objects.create_user(
            username='citizen_alice',
            password='password123',
            role='citizen',
            is_verified=True,
            civic_points=0
        )
        self.volunteer = User.objects.create_user(
            username='volunteer_bob',
            password='password123',
            role='volunteer',
            is_verified=True,
            civic_points=0
        )
        self.unverified_volunteer = User.objects.create_user(
            username='volunteer_unverified',
            password='password123',
            role='volunteer',
            is_verified=False,
            civic_points=0
        )
        self.admin_user = User.objects.create_superuser(
            username='admin_charlie',
            password='password123',
            email='admin@example.com'
        )

    def create_dummy_image(self, format='JPEG', size=(200, 200), color=(255, 0, 0), with_exif=False):
        img = Image.new('RGB', size, color=color)
        out = BytesIO()
        if with_exif:
            # Add a basic EXIF segment
            exif = img.getexif()
            exif[0x0112] = 1  # Orientation Normal
            exif[0x010f] = "TestCamera"
            img.save(out, format=format, exif=exif)
        else:
            img.save(out, format=format)
        out.seek(0)
        ext = 'jpg' if format == 'JPEG' else format.lower()
        return SimpleUploadedFile(f"test_image.{ext}", out.read(), content_type=f"image/{ext}")


class StateTransitionIntegrityTests(ViolationAuditBaseTestCase):
    """(2) Tests asserting illegal state transitions are rejected and legal flows succeed."""

    def setUp(self):
        super().setUp()
        self.violation = Violation.objects.create(
            title="Broken Street Light",
            description="Dark alley near 5th ave",
            category=Violation.Category.ELECTRICITY,
            location="5th Avenue",
            latitude=12.9716,
            longitude=77.5946,
            reported_by=self.citizen,
            status=Violation.Status.PENDING
        )

    def test_illegal_transition_pending_to_resolved_rejected(self):
        """Assert direct Pending -> Resolved transition is strictly rejected."""
        can_transition = self.violation.can_transition_to(Violation.Status.RESOLVED)
        self.assertFalse(can_transition)
        
        success = self.violation.transition_to(Violation.Status.RESOLVED)
        self.assertFalse(success)
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, Violation.Status.PENDING)

    def test_illegal_transition_pending_to_pending_verification_rejected(self):
        """Assert Pending -> Pending Verification skipping adoption is rejected."""
        can_transition = self.violation.can_transition_to(Violation.Status.PENDING_VERIFICATION)
        self.assertFalse(can_transition)
        
        success = self.violation.transition_to(Violation.Status.PENDING_VERIFICATION)
        self.assertFalse(success)
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, Violation.Status.PENDING)

    def test_illegal_transition_adopted_to_resolved_rejected(self):
        """Assert Adopted -> Resolved skipping verification proof is rejected."""
        self.violation.transition_to(Violation.Status.ADOPTED, user=self.volunteer)
        self.assertEqual(self.violation.status, Violation.Status.ADOPTED)

        can_transition = self.violation.can_transition_to(Violation.Status.RESOLVED)
        self.assertFalse(can_transition)
        
        success = self.violation.transition_to(Violation.Status.RESOLVED)
        self.assertFalse(success)
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, Violation.Status.ADOPTED)

    def test_terminal_state_resolved_cannot_transition(self):
        """Assert Resolved is a terminal state and cannot transition to any other status."""
        self.violation.transition_to(Violation.Status.ADOPTED, user=self.volunteer)
        self.violation.transition_to(Violation.Status.PENDING_VERIFICATION)
        self.violation.transition_to(Violation.Status.RESOLVED)
        self.assertEqual(self.violation.status, Violation.Status.RESOLVED)

        # Attempt to transition back
        for status in [Violation.Status.PENDING, Violation.Status.ADOPTED, Violation.Status.PENDING_VERIFICATION, Violation.Status.REJECTED]:
            self.assertFalse(self.violation.can_transition_to(status))
            self.assertFalse(self.violation.transition_to(status))

    def test_legal_full_lifecycle_succeeds(self):
        """Assert valid sequential lifecycle: Pending -> Adopted -> Pending Verification -> Resolved."""
        # 1. Adopt
        self.assertTrue(self.violation.transition_to(Violation.Status.ADOPTED, user=self.volunteer))
        self.assertEqual(self.violation.status, Violation.Status.ADOPTED)
        self.assertEqual(self.violation.adopted_by, self.volunteer)

        # 2. Submit Proof / Pending Verification
        self.assertTrue(self.violation.transition_to(Violation.Status.PENDING_VERIFICATION))
        self.assertEqual(self.violation.status, Violation.Status.PENDING_VERIFICATION)

        # 3. Verify & Resolve
        self.assertTrue(self.violation.transition_to(Violation.Status.RESOLVED))
        self.assertEqual(self.violation.status, Violation.Status.RESOLVED)

    def test_rework_flow_pending_verification_to_adopted(self):
        """Assert rejecting resolution sends status back from Pending Verification to Adopted."""
        self.violation.transition_to(Violation.Status.ADOPTED, user=self.volunteer)
        self.violation.transition_to(Violation.Status.PENDING_VERIFICATION)
        
        # Reject proof
        self.assertTrue(self.violation.transition_to(Violation.Status.ADOPTED))
        self.assertEqual(self.violation.status, Violation.Status.ADOPTED)


class AntiSelfDealingTests(ViolationAuditBaseTestCase):
    """(1) Tests preventing self-dealing (user adopting or resolving their own reported violation)."""

    def setUp(self):
        super().setUp()
        # Create a user who is both a reporter and a verified volunteer
        self.worker_citizen = User.objects.create_user(
            username='dual_role_user',
            password='password123',
            role='volunteer',
            is_verified=True,
            civic_points=0
        )
        self.violation = Violation.objects.create(
            title="Pothole in my street",
            description="Deep pothole",
            category=Violation.Category.ROAD,
            location="Main Street",
            latitude=12.9716,
            longitude=77.5946,
            reported_by=self.worker_citizen,
            status=Violation.Status.PENDING
        )

    def test_model_clean_prevents_self_adoption(self):
        """Assert model clean() raises ValidationError if adopted_by == reported_by."""
        self.violation.adopted_by = self.worker_citizen
        with self.assertRaises(ValidationError):
            self.violation.clean()

    def test_can_transition_to_blocks_self_adoption(self):
        """Assert can_transition_to returns False when reporter tries to adopt."""
        can_adopt = self.violation.can_transition_to(Violation.Status.ADOPTED, user=self.worker_citizen)
        self.assertFalse(can_adopt)
        self.assertFalse(self.violation.transition_to(Violation.Status.ADOPTED, user=self.worker_citizen))

    def test_adopt_view_blocks_self_adoption(self):
        """Assert /violations/adopt/<id>/ view blocks reporter from adopting their own violation."""
        self.client.login(username='dual_role_user', password='password123')
        response = self.client.get(reverse('adopt_violation', kwargs={'id': self.violation.id}), follow=True)
        
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, Violation.Status.PENDING)
        self.assertIsNone(self.violation.adopted_by)
        self.assertContains(response, "Self-dealing prevented")

    def test_work_submission_clean_blocks_self_work(self):
        """Assert WorkSubmission clean() prevents reporter from submitting proof for own report."""
        submission = WorkSubmission(
            violation=self.violation,
            worker=self.worker_citizen,
            work_description="I fixed my own issue"
        )
        with self.assertRaises(ValidationError):
            submission.clean()

    def test_certificate_clean_blocks_same_reporter_and_worker(self):
        """Assert Certificate clean() prevents reporter and worker being the exact same user."""
        cert = Certificate(
            violation=self.violation,
            issued_to_reporter=self.worker_citizen,
            issued_to_worker=self.worker_citizen,
            points_awarded_reporter=10,
            points_awarded_worker=50
        )
        with self.assertRaises(ValidationError):
            cert.clean()

    def test_verify_resolution_blocks_self_verification_by_worker(self):
        """Assert worker cannot verify and approve their own work to mint points."""
        # Setup violation reported by Alice, adopted by Bob
        v = Violation.objects.create(
            title="Drainage issue",
            description="Blocked drainage",
            category=Violation.Category.DRAINAGE,
            location="North Street",
            latitude=12.9800,
            longitude=77.6000,
            reported_by=self.citizen,
            adopted_by=self.volunteer,
            status=Violation.Status.PENDING_VERIFICATION
        )
        
        # Volunteer Bob attempts to verify their own work
        self.client.login(username='volunteer_bob', password='password123')
        response = self.client.get(reverse('verify_resolution', kwargs={'id': v.id}) + '?action=approve', follow=True)
        
        v.refresh_from_db()
        self.assertEqual(v.status, Violation.Status.PENDING_VERIFICATION)
        self.assertContains(response, "not authorized to verify")


class DuplicateViolationDetectionTests(ViolationAuditBaseTestCase):
    """(3) Tests duplicate violation detection within configurable geo-radius + category match."""

    def setUp(self):
        super().setUp()
        self.existing_violation = Violation.objects.create(
            title="Pothole at Indiranagar 100ft Road",
            description="Large pothole near signal",
            category=Violation.Category.ROAD,
            location="100ft Road, Indiranagar",
            latitude=12.971891,
            longitude=77.641154,
            reported_by=self.citizen,
            status=Violation.Status.PENDING
        )

    def test_exact_location_and_same_category_detected_as_duplicate(self):
        """Assert issue at exact same location and category is flagged as duplicate."""
        is_dup, match = DuplicateDetectionService.check_is_duplicate(
            category=Violation.Category.ROAD,
            latitude=12.971891,
            longitude=77.641154,
            radius_meters=50
        )
        self.assertTrue(is_dup)
        self.assertIsNotNone(match)
        self.assertEqual(match['violation'].id, self.existing_violation.id)
        self.assertLessEqual(match['distance_meters'], 1.0)

    def test_close_location_within_radius_detected_as_duplicate(self):
        """Assert issue reported ~20 meters away in same category is detected as duplicate."""
        # Offset latitude by ~0.00018 deg (~20 meters)
        nearby_lat = 12.971891 + 0.00018
        nearby_lng = 77.641154

        is_dup, match = DuplicateDetectionService.check_is_duplicate(
            category=Violation.Category.ROAD,
            latitude=nearby_lat,
            longitude=nearby_lng,
            radius_meters=50
        )
        self.assertTrue(is_dup)
        self.assertIsNotNone(match)
        self.assertEqual(match['violation'].id, self.existing_violation.id)
        self.assertLessEqual(match['distance_meters'], 50.0)

    def test_different_category_same_location_not_duplicate(self):
        """Assert different category at exact same location is NOT flagged as duplicate."""
        is_dup, match = DuplicateDetectionService.check_is_duplicate(
            category=Violation.Category.GARBAGE,  # Different category
            latitude=12.971891,
            longitude=77.641154,
            radius_meters=50
        )
        self.assertFalse(is_dup)
        self.assertIsNone(match)

    def test_far_location_same_category_not_duplicate(self):
        """Assert issue > 50 meters away in same category is NOT flagged as duplicate."""
        # ~200 meters away
        far_lat = 12.971891 + 0.002
        far_lng = 77.641154

        is_dup, match = DuplicateDetectionService.check_is_duplicate(
            category=Violation.Category.ROAD,
            latitude=far_lat,
            longitude=far_lng,
            radius_meters=50
        )
        self.assertFalse(is_dup)

    def test_resolved_issue_not_flagged_as_active_duplicate(self):
        """Assert resolved issues in the same spot do not block new reports."""
        self.existing_violation.status = Violation.Status.RESOLVED
        self.existing_violation.save()

        is_dup, match = DuplicateDetectionService.check_is_duplicate(
            category=Violation.Category.ROAD,
            latitude=12.971891,
            longitude=77.641154,
            radius_meters=50
        )
        self.assertFalse(is_dup)

    def test_report_form_duplicate_validation_blocks_submission(self):
        """Assert ViolationForm raises ValidationError when duplicate is detected."""
        from .forms import ViolationForm
        form_data = {
            'title': 'Another pothole near signal',
            'description': 'Same pothole report',
            'category': Violation.Category.ROAD,
            'location': '100ft Road',
            'latitude': 12.971891,
            'longitude': 77.641154,
        }
        form = ViolationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertTrue(len(form.non_field_errors()) > 0)
        self.assertIn("A similar active 'Road Damage and Potholes' issue", form.non_field_errors().data[0].message)




class RolePermissionCentralizationTests(ViolationAuditBaseTestCase):
    """(4) Tests asserting centralized role and permission decorators."""

    def setUp(self):
        super().setUp()
        self.violation = Violation.objects.create(
            title="Garbage Dump",
            description="Overflowing bins",
            category=Violation.Category.GARBAGE,
            location="East Market",
            latitude=12.9500,
            longitude=77.5800,
            reported_by=self.citizen,
            status=Violation.Status.PENDING
        )

    def test_unverified_volunteer_cannot_adopt(self):
        """Assert unverified volunteer is rejected by @verified_worker_required decorator."""
        self.client.login(username='volunteer_unverified', password='password123')
        response = self.client.get(reverse('adopt_violation', kwargs={'id': self.violation.id}), follow=True)
        
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, Violation.Status.PENDING)
        self.assertContains(response, "pending verification by an administrator")

    def test_regular_citizen_cannot_adopt(self):
        """Assert citizen role cannot adopt violations."""
        self.client.login(username='citizen_alice', password='password123')
        response = self.client.get(reverse('adopt_violation', kwargs={'id': self.violation.id}), follow=True)
        
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, Violation.Status.PENDING)
        self.assertContains(response, "do not have permission")

    def test_verified_volunteer_can_adopt(self):
        """Assert verified volunteer is allowed to adopt violations."""
        self.client.login(username='volunteer_bob', password='password123')
        response = self.client.get(reverse('adopt_violation', kwargs={'id': self.violation.id}), follow=True)
        
        self.violation.refresh_from_db()
        self.assertEqual(self.violation.status, Violation.Status.ADOPTED)
        self.assertEqual(self.violation.adopted_by, self.volunteer)
        self.assertContains(response, "You have adopted")

    def test_admin_required_protects_csv_export(self):
        """Assert non-admin cannot access export CSV endpoint."""
        # Citizen
        self.client.login(username='citizen_alice', password='password123')
        res = self.client.get(reverse('export_csv'), follow=True)
        self.assertContains(res, "Administrator privileges required")

        # Admin
        self.client.login(username='admin_charlie', password='password123')
        res_admin = self.client.get(reverse('export_csv'))
        self.assertEqual(res_admin.status_code, 200)
        self.assertEqual(res_admin['Content-Type'], 'text/csv')


class FileUploadValidationAndExifTests(ViolationAuditBaseTestCase):
    """(5) Tests file upload validation (MIME allowlist, size limits, EXIF stripping)."""

    def test_valid_image_allowed(self):
        """Assert valid JPEG/PNG image passes validation."""
        valid_img = self.create_dummy_image(format='JPEG')
        validated = validate_image_file(valid_img, max_size_mb=5)
        self.assertIsNotNone(validated)

    def test_oversized_file_rejected(self):
        """Assert file exceeding size limit raises ValidationError."""
        dummy_file = SimpleUploadedFile("big_image.jpg", b"0" * (6 * 1024 * 1024), content_type="image/jpeg")
        with self.assertRaises(ValidationError) as ctx:
            validate_image_file(dummy_file, max_size_mb=5)
        self.assertIn("exceeds the maximum allowed limit", str(ctx.exception))

    def test_disallowed_mime_type_rejected(self):
        """Assert fake image file with disallowed MIME type or corrupted bytes is rejected."""
        fake_file = SimpleUploadedFile("script.jpg", b"<?php echo 'malicious'; ?>", content_type="image/jpeg")
        with self.assertRaises(ValidationError):
            validate_image_file(fake_file, max_size_mb=5)

    def test_exif_metadata_stripped_on_sanitization(self):
        """Assert EXIF tags and metadata are stripped while preserving image pixels."""
        img_with_exif = self.create_dummy_image(format='JPEG', with_exif=True)
        
        # Verify initial image has EXIF
        initial_img = Image.open(img_with_exif)
        self.assertIsNotNone(initial_img.getexif())
        img_with_exif.seek(0)

        # Sanitize
        clean_file = sanitize_and_strip_exif(img_with_exif)
        self.assertIsNotNone(clean_file)

        # Inspect sanitized image
        sanitized_img = Image.open(clean_file)
        exif_tags = sanitized_img.getexif()
        # EXIF dictionary should be empty after sanitization
        self.assertEqual(len(exif_tags), 0)
