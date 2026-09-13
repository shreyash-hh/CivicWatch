import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'civicwatch.settings')
django.setup()

from user.models import CustomUser
from violations.models import Violation, Certificate, WorkSubmission
from django.test import RequestFactory
from violations.views import verify_resolution
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware

print("=== Testing Impact Points with Demo Data ===")

# Find a violation that is pending verification
violations = Violation.objects.filter(status=Violation.Status.PENDING_VERIFICATION)
if not violations.exists():
    print("No pending verification violations found. Please run seed_data.py first.")
else:
    v = violations.first()
    reporter = v.reported_by
    worker = v.adopted_by
    print(f"Testing Violation: {v.title} (Category: {v.category})")
    print(f"Reporter: {reporter.username} (Current Points: {reporter.civic_points})")
    print(f"Worker: {worker.username} (Current Points: {worker.civic_points})")
    
    print("\nSimulating reporter approving the resolution...")
    
    # Mocking a request to the verify_resolution view
    factory = RequestFactory()
    request = factory.get(f'/verify/{v.id}/?action=approve')
    request.user = reporter
    
    # Need session and messages middleware for the view to work correctly
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    
    messages_middleware = MessageMiddleware(lambda r: None)
    messages_middleware.process_request(request)
    
    # Call the view directly
    response = verify_resolution(request, v.id)
    
    # Refresh objects from DB to check new points
    v.refresh_from_db()
    reporter.refresh_from_db()
    worker.refresh_from_db()
    
    print(f"\nAfter Resolution:")
    print(f"Violation status: {v.status}")
    print(f"Reporter: {reporter.username} (New Points: {reporter.civic_points})")
    print(f"Worker: {worker.username} (New Points: {worker.civic_points})")
    
    # Verify Certificate
    cert = Certificate.objects.filter(violation=v).first()
    if cert:
        print(f"\nCertificate Issued: True")
        print(f"Points Awarded to Reporter on Cert: {cert.points_awarded_reporter}")
        print(f"Points Awarded to Worker on Cert: {cert.points_awarded_worker}")
    else:
        print("\nCertificate Issued: False")

    print("\n=== Test Completed Successfully ===")
