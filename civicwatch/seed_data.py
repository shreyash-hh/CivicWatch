import os
import django
import random
import requests
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'civicwatch.settings')
django.setup()

from user.models import CustomUser, VolunteerProfile, OrganizationProfile, Notification
from violations.models import Violation, WorkSubmission, WorkSubmissionImage, WorkRating, Certificate

def download_image(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return ContentFile(response.content)
    except Exception as e:
        print(f"Error downloading image: {e}")
    return None

def seed_data():
    print("Starting database seeding...")

    # 1. Create Users
    # Citizens
    citizens = []
    for i in range(5):
        username = f"citizen_{i+1}"
        user, created = CustomUser.objects.get_or_create(
            username=username,
            defaults={'role': 'citizen', 'email': f"{username}@example.com", 'is_verified': True}
        )
        if created:
            user.set_password('password123')
            user.save()
        citizens.append(user)

    # Volunteers
    volunteers = []
    volunteer_names = ["Arjun_Volunteer", "Priya_Helper", "Rahul_Social", "Sneha_Civic"]
    skills_list = ["Waste Management", "Civil Engineering", "Basic Plumbing", "Community Cleanup"]
    for name in volunteer_names:
        user, created = CustomUser.objects.get_or_create(
            username=name,
            defaults={'role': 'volunteer', 'email': f"{name.lower()}@example.com", 'is_verified': True, 'civic_points': random.randint(50, 200)}
        )
        if created:
            user.set_password('password123')
            user.save()
            vp, created_vp = VolunteerProfile.objects.update_or_create(
                user=user,
                defaults={
                    'skills': random.choice(skills_list),
                    'address': "Akurdi, Pune",
                    'latitude': 18.6498 + (random.uniform(-0.02, 0.02)),
                    'longitude': 73.7707 + (random.uniform(-0.02, 0.02))
                }
            )
        volunteers.append(user)

    # NGOs
    orgs = []
    org_names = ["CleanPune_NGO", "GreenEarth_Society", "CityWatch_Foundation"]
    for name in org_names:
        user, created = CustomUser.objects.get_or_create(
            username=name,
            defaults={'role': 'organization', 'email': f"{name.lower()}@example.com", 'is_verified': True, 'civic_points': random.randint(200, 500)}
        )
        if created:
            user.set_password('password123')
            user.save()
            op, created_op = OrganizationProfile.objects.update_or_create(
                user=user,
                defaults={
                    'org_name': name.replace("_", " "),
                    'registration_number': f"NGO-{random.randint(1000, 9999)}",
                    'address': "PCMC, Pune",
                    'latitude': 18.6298 + (random.uniform(-0.02, 0.02)),
                    'longitude': 73.7997 + (random.uniform(-0.02, 0.02))
                }
            )
        orgs.append(user)

    print("Users, Volunteers, and NGOs created.")

    # 2. Create Reports (Violations)
    report_data = [
        ("Massive Pothole on Main Road", "road", "https://images.unsplash.com/photo-1599385552341-a393952a2559?w=800"),
        ("Illegal Garbage Dumping near Park", "garbage", "https://images.unsplash.com/photo-1611284446314-60a58ac0deb9?w=800"),
        ("Broken Streetlight on 5th Ave", "electricity", "https://images.unsplash.com/photo-1517487216335-573516568856?w=800"),
        ("Water Leakage from Main Pipe", "water", "https://images.unsplash.com/photo-1585702138250-482433552097?w=800"),
        ("Encroachment on Footpath", "encroachment", "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?w=800"),
    ]

    for title, cat, img_url in report_data:
        reporter = random.choice(citizens)
        v, created = Violation.objects.get_or_create(
            title=title,
            defaults={
                'category': cat,
                'description': f"This is a sample report for {title}. Needs immediate attention from local authorities.",
                'location': "Near Akurdi Railway Station, Pune",
                'latitude': 18.6498 + (random.uniform(-0.01, 0.01)),
                'longitude': 73.7707 + (random.uniform(-0.01, 0.01)),
                'reported_by': reporter,
                'status': 'Pending'
            }
        )
        if created and not v.image:
            img_file = download_image(img_url)
            if img_file:
                v.image.save(f"demo_{cat}.jpg", img_file)
            v.save()

    print("Pending reports created.")

    # 3. Create a "Resolved" Report with Proof and Certificate
    res_title = "Street Cleanup Drive Complete"
    res_v, created = Violation.objects.get_or_create(
        title=res_title,
        defaults={
            'category': 'garbage',
            'description': "Heavy garbage accumulation near the local primary school.",
            'location': "Sector 24, Nigdi, Pune",
            'latitude': 18.6550,
            'longitude': 73.7750,
            'reported_by': citizens[0],
            'status': 'Resolved',
            'adopted_by': orgs[0]
        }
    )
    
    if created:
        # Download before image
        before_img_data = download_image("https://images.unsplash.com/photo-1530587191325-3db32d826c18?w=800")
        if before_img_data:
            res_v.image.save("school_garbage_before.jpg", before_img_data)
        res_v.save()

        # Create Work Submission
        submission = WorkSubmission.objects.create(
            violation=res_v,
            worker=orgs[0],
            work_description="Our NGO team cleaned the entire area and coordinated with the municipal corp for waste collection."
        )
        
        # Add "After" photos
        after_urls = [
            "https://images.unsplash.com/photo-1542601906990-b4d3fb778b09?w=800",
            "https://images.unsplash.com/photo-1563453392212-326f5e854473?w=800"
        ]
        for idx, url in enumerate(after_urls):
            after_img_data = download_image(url)
            if after_img_data:
                img_obj = WorkSubmissionImage(submission=submission)
                img_obj.image.save(f"resolved_{idx}.jpg", after_img_data)
                img_obj.save()
        
        # Add a Certificate
        Certificate.objects.create(
            violation=res_v,
            issued_to_reporter=citizens[0],
            issued_to_worker=orgs[0],
            points_awarded_reporter=10,
            points_awarded_worker=25
        )

        # Add some ratings
        for citizen in citizens[1:4]:
            WorkRating.objects.create(
                submission=submission,
                user=citizen,
                stars=random.randint(4, 5),
                review="Great job by the NGO! The area is much cleaner now."
            )
        
        # Update submission averages
        all_ratings = submission.ratings.all()
        submission.rating_count = all_ratings.count()
        submission.avg_rating = sum([r.stars for r in all_ratings]) / submission.rating_count
        submission.save()

    print("Resolved report with multi-photo proof and certificate created.")

    # 4. Create a "Waiting Approval" Report
    wait_v, created = Violation.objects.get_or_create(
        title="Blocked Drainage Pipeline",
        defaults={
            'category': 'drainage',
            'description': "Water is overflowing on the road due to a blocked drain.",
            'location': "Dange Chowk, Pune",
            'latitude': 18.6010,
            'longitude': 73.7640,
            'reported_by': citizens[1],
            'status': 'Pending Verification',
            'adopted_by': volunteers[0]
        }
    )
    
    if created:
        # Download before image
        before_img_data = download_image("https://images.unsplash.com/photo-1545127398-14699f92334b?w=800")
        if before_img_data:
            wait_v.image.save("drain_before.jpg", before_img_data)
        wait_v.save()

        # Create Work Submission
        submission = WorkSubmission.objects.create(
            violation=wait_v,
            worker=volunteers[0],
            work_description="I have cleared the surface blockage and notified the plumbing department for internal repairs."
        )
        
        # Add "After" photo
        after_img_data = download_image("https://images.unsplash.com/photo-1584622650111-993a426fbf0a?w=800")
        if after_img_data:
            img_obj = WorkSubmissionImage(submission=submission)
            img_obj.image.save("drain_after_0.jpg", after_img_data)
            img_obj.save()

    print("Waiting approval queue populated.")
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    seed_data()
