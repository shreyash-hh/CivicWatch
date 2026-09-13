import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'civicwatch.settings')
django.setup()

from django.test import RequestFactory
from violations.models import Violation
from user.models import CustomUser, Notification
from violations.views import request_volunteer_help
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware

print("=== Testing Notification Feature ===")

# 1. Find a pending violation
v = Violation.objects.filter(status=Violation.Status.PENDING, is_help_requested=False).first()

if not v:
    print("No pending violations found without help requested. Creating a test violation...")
    reporter = CustomUser.objects.filter(role='citizen').first()
    v = Violation.objects.create(
        title="Test Emergency Pipeline Burst",
        description="Water is gushing out on the main road.",
        category='water',
        location="Pune Center",
        latitude=18.6498,
        longitude=73.7707,
        status='Pending',
        reported_by=reporter
    )

print(f"Testing with Violation: {v.title} (ID: {v.id})")
print(f"Coordinates: {v.latitude}, {v.longitude}")

# Count notifications before
initial_notif_count = Notification.objects.count()
print(f"Total notifications in system before request: {initial_notif_count}")

# 2. Simulate the reporter requesting help
reporter = v.reported_by
print(f"Reporter requesting help: {reporter.username}")

factory = RequestFactory()
request = factory.get(f'/request-help/{v.id}/')
request.user = reporter

# Setup middleware
middleware = SessionMiddleware(lambda r: None)
middleware.process_request(request)
request.session.save()
MessageMiddleware(lambda r: None).process_request(request)

# 3. Call the view
response = request_volunteer_help(request, v.id)

# 4. Verify results
v.refresh_from_db()
print(f"\nHelp Requested Flag: {v.is_help_requested}")
print(f"Requested At: {v.requested_at}")

new_notif_count = Notification.objects.count()
print(f"Total notifications in system after request: {new_notif_count}")
print(f"Notifications generated: {new_notif_count - initial_notif_count}")

if new_notif_count > initial_notif_count:
    print("\nRecent Notifications:")
    recent = Notification.objects.order_by('-created_at')[:(new_notif_count - initial_notif_count)]
    for n in recent:
        print(f"- To: {n.user.username} ({n.user.role}) | Title: '{n.title}' | Link: {n.link}")
else:
    print("WARNING: No notifications were generated. Maybe no volunteers/orgs are within 10km?")

print("\n=== Test Completed ===")
