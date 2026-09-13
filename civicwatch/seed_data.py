import os
import django
import random
import io
from PIL import Image, ImageDraw

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'civicwatch.settings')
django.setup()

from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta

from user.models import CustomUser, VolunteerProfile, OrganizationProfile, Notification
from violations.models import Violation, WorkSubmission, WorkSubmissionImage, WorkRating, Certificate, Comment


def create_banner_image(text, bg_color=(43, 84, 126), label="CIVICWATCH EVIDENCE", filename="evidence.jpg"):
    """Generate a clean, high-resolution placeholder civic image."""
    width, height = 800, 500
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Draw an overlay box
    draw.rectangle([(40, 40), (width - 40, height - 40)], outline=(255, 255, 255), width=3)
    
    # Draw label badge
    draw.rectangle([(60, 60), (360, 105)], fill=(15, 23, 42))
    draw.text((75, 75), label, fill=(255, 255, 255))
    
    # Draw text in the middle
    draw.text((70, 220), text, fill=(255, 255, 255))
    
    # Draw timestamp watermark
    timestamp_str = timezone.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    draw.text((70, height - 80), f"GeoTag & Timestamp Verified: {timestamp_str}", fill=(200, 220, 240))
    
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return ContentFile(buf.getvalue(), name=filename)


def wipe_and_seed():
    print("=========================================")
    print("CLEANING EXISTING CIVIC ENTRIES...")
    print("=========================================")
    
    # Wipe existing civic data
    Certificate.objects.all().delete()
    WorkRating.objects.all().delete()
    WorkSubmissionImage.objects.all().delete()
    WorkSubmission.objects.all().delete()
    Comment.objects.all().delete()
    Violation.objects.all().delete()
    Notification.objects.all().delete()
    
    print("All previous violations, submissions, ratings, and certificates removed.")

    # 1. Create / Ensure Standard Users
    print("\nEnsuring Citizen, Volunteer, and NGO accounts...")
    
    # Citizens
    citizens_data = [
        ("Aarav_Sharma", "aarav@example.com"),
        ("Ananya_Patil", "ananya@example.com"),
        ("Rohan_Deshmukh", "rohan@example.com"),
        ("Neha_Kulkarni", "neha@example.com"),
        ("Vikram_Joshi", "vikram@example.com"),
    ]
    citizens = []
    for username, email in citizens_data:
        user, created = CustomUser.objects.get_or_create(
            username=username,
            defaults={'role': 'citizen', 'email': email, 'is_verified': True, 'civic_points': random.randint(15, 60)}
        )
        if created:
            user.set_password('password123')
            user.save()
        citizens.append(user)

    # Volunteers
    volunteers_data = [
        ("Arjun_Volunteer", "Waste Management & Green Roads", 18.6498, 73.7707, 185),
        ("Priya_CivicHero", "Sanitation & Street Lighting", 18.6250, 73.8120, 240),
        ("Rahul_SocialWorker", "Pothole Patching & Safety", 18.5910, 73.7840, 160),
        ("Sneha_EcoWarrior", "Lake & Waterway Restoration", 18.6180, 73.7550, 210),
    ]
    volunteers = []
    for uname, skill, lat, lon, pts in volunteers_data:
        user, created = CustomUser.objects.get_or_create(
            username=uname,
            defaults={'role': 'volunteer', 'email': f"{uname.lower()}@example.com", 'is_verified': True, 'civic_points': pts}
        )
        if created:
            user.set_password('password123')
        user.civic_points = pts
        user.save()
        VolunteerProfile.objects.update_or_create(
            user=user,
            defaults={'skills': skill, 'address': "Pune Municipal Region", 'latitude': lat, 'longitude': lon}
        )
        volunteers.append(user)

    # NGOs
    orgs_data = [
        ("CleanCity_Foundation", "Clean City Foundation Pune", "NGO-MH-4821", 18.6550, 73.7750, 520),
        ("GreenEarth_Society", "Green Earth Restoration Society", "NGO-MH-8192", 18.6120, 73.8050, 430),
        ("Pothole_Action_Team", "Pune Pothole Action NGO", "NGO-MH-3310", 18.5790, 73.7430, 390),
    ]
    orgs = []
    for uname, org_name, reg_no, lat, lon, pts in orgs_data:
        user, created = CustomUser.objects.get_or_create(
            username=uname,
            defaults={'role': 'organization', 'email': f"{uname.lower()}@example.com", 'is_verified': True, 'civic_points': pts}
        )
        if created:
            user.set_password('password123')
        user.civic_points = pts
        user.save()
        OrganizationProfile.objects.update_or_create(
            user=user,
            defaults={'org_name': org_name, 'registration_number': reg_no, 'address': "Pune/PCMC", 'latitude': lat, 'longitude': lon}
        )
        orgs.append(user)

    print(f"Loaded {len(citizens)} Citizens, {len(volunteers)} Volunteers, and {len(orgs)} NGOs.")

    # 2. SEED FRESH CIVIC ISSUES ACROSS CATEGORIES & STATUSES
    print("\nCreating fresh civic issues...")

    # A. RESOLVED & VERIFIED TRANSFORMATIONS (Showcase Ready)
    resolved_cases = [
        {
            "title": "Akurdi Primary School Illegal Garbage Dump Cleared",
            "category": "garbage",
            "desc": "Over 2 tons of unsegregated domestic and commercial plastic waste was dumped right beside the primary school boundary wall, attracting stray cattle and causing foul odor.",
            "location": "Near ZP Primary School, Sector 24, Akurdi",
            "lat": 18.6482,
            "lon": 73.7695,
            "reporter": citizens[0],
            "resolver": orgs[0], # CleanCity_Foundation
            "before_text": "BEFORE: Garbage Dump & Litter Accumulation",
            "before_color": (160, 50, 50),
            "after_text": "AFTER: Cleaned, Sanitized & Boundary Fenced",
            "after_color": (34, 139, 34),
            "work_desc": "Mobilized 15 volunteers and coordinated with PCMC waste management trucks. Cleared 2.4 tons of waste, disinfected the perimeter with lime powder, and planted 10 Ashoka saplings along the wall.",
            "ratings": [
                (citizens[1], 5, "Remarkable transformation! School kids can now walk safely without the foul stench."),
                (citizens[2], 5, "Incredible speed and verified clean-up. Great work CleanCity Foundation!"),
                (citizens[3], 5, "Cleaned and sanitized within 48 hours of reporting.")
            ]
        },
        {
            "title": "Severe Crater Pothole on Old Mumbai-Pune Highway Patched",
            "category": "road",
            "desc": "A 1.5-meter wide, 8-inch deep crater pothole was causing sudden two-wheeler skids and severe traffic bottlenecks near the flyover ramp.",
            "location": "Old Mumbai-Pune Highway, Chinchwad Station",
            "lat": 18.6320,
            "lon": 73.7915,
            "reporter": citizens[1],
            "resolver": orgs[2], # Pothole_Action_Team
            "before_text": "BEFORE: 8-Inch Deep Dangerous Crater",
            "before_color": (140, 60, 40),
            "after_text": "AFTER: Cold-Bitumen Compacted & Levelled",
            "after_color": (30, 120, 80),
            "work_desc": "Used heavy-duty rapid cold-mix bitumen with vibrating plate compactor to fill and level the crater, followed by reflective yellow warning edge painting.",
            "ratings": [
                (citizens[0], 5, "Saved hundreds of daily bike commuters from serious falls. Thank you!"),
                (citizens[4], 5, "Properly compacted and flush with the tarmac. Excellent repair.")
            ]
        },
        {
            "title": "Thergaon Community Pond Plastic Pollution Cleaned",
            "category": "water",
            "desc": "Floating religious puja waste, single-use plastic bottles, and thermocol were clogging the water inlet of the Thergaon community pond.",
            "location": "Thergaon Lakeside Garden, Pune",
            "lat": 18.6080,
            "lon": 73.7780,
            "reporter": citizens[2],
            "resolver": volunteers[3], # Sneha_EcoWarrior
            "before_text": "BEFORE: Choked Water Surface & Plastic Debris",
            "before_color": (120, 70, 70),
            "after_text": "AFTER: Restored Water Basin & Aeration Net Installed",
            "after_color": (20, 110, 120),
            "work_desc": "Conducted a 4-hour morning desilting and trash netting drive. Extracted 400 kg of plastic debris and placed trash collection drums at the inlet.",
            "ratings": [
                (citizens[0], 5, "The pond is breathing again! True civic hero action."),
                (citizens[1], 5, "Inspiring work for our entire residential society.")
            ]
        },
        {
            "title": "Broken Main Streetlight Junction Fixed & Re-illuminated",
            "category": "electricity",
            "desc": "Four consecutive streetlight poles had been dark for two weeks, creating an unsafe pedestrian blind spot for women returning from the metro station.",
            "location": "Metro Pillar 142, Pimpri Station Road",
            "lat": 18.6275,
            "lon": 73.8010,
            "reporter": citizens[3],
            "resolver": volunteers[1], # Priya_CivicHero
            "before_text": "BEFORE: Pitch Dark Street Junction & Damaged Wiring",
            "before_color": (40, 40, 50),
            "after_text": "AFTER: Repaired Junction Box & High-Lumen LED Activated",
            "after_color": (180, 140, 30),
            "work_desc": "Replaced faulty fuse junction box, re-wired damaged earthing cables, and installed 90W high-efficiency LED lights on all four poles.",
            "ratings": [
                (citizens[2], 5, "The road is brightly lit and safe again! Prompt resolution."),
                (citizens[4], 5, "Great collaboration with the local power lineman.")
            ]
        }
    ]

    for idx, c in enumerate(resolved_cases):
        v = Violation.objects.create(
            title=c["title"],
            category=c["category"],
            description=c["desc"],
            location=c["location"],
            latitude=c["lat"],
            longitude=c["lon"],
            reported_by=c["reporter"],
            adopted_by=c["resolver"],
            status=Violation.Status.RESOLVED,
            image=create_banner_image(c["before_text"], bg_color=c["before_color"], label="BEFORE REPORT", filename=f"resolved_before_{idx}.jpg")
        )

        submission = WorkSubmission.objects.create(
            violation=v,
            worker=c["resolver"],
            before_photo=v.image,
            work_description=c["work_desc"]
        )

        after_img = create_banner_image(c["after_text"], bg_color=c["after_color"], label="AFTER PROOF", filename=f"resolved_after_{idx}.jpg")
        WorkSubmissionImage.objects.create(submission=submission, image=after_img)

        # Ratings
        for r_user, stars, r_text in c["ratings"]:
            WorkRating.objects.create(
                submission=submission,
                user=r_user,
                stars=stars,
                review=r_text
            )

        all_r = submission.ratings.all()
        submission.rating_count = all_r.count()
        submission.avg_rating = sum([r.stars for r in all_r]) / all_r.count()
        submission.save()

        # Certificate
        Certificate.objects.create(
            violation=v,
            issued_to_reporter=c["reporter"],
            issued_to_worker=c["resolver"],
            points_awarded_reporter=15,
            points_awarded_worker=40
        )
        print(f"  [RESOLVED] {v.title}")

    # B. PENDING VERIFICATION (Proof Submitted, Awaiting Final Review)
    verification_cases = [
        {
            "title": "Overflowing Open Sewage Line Desilted at Spine Road",
            "category": "drainage",
            "desc": "Clogged storm drain overflowing contaminated sewage onto pedestrian walkway and cycle track.",
            "location": "Spine Road, Sector 9, Bhosari",
            "lat": 18.6620,
            "lon": 73.8240,
            "reporter": citizens[4],
            "worker": volunteers[0], # Arjun_Volunteer
            "before_text": "BEFORE: Clogged Drainage Chamber & Road Overflow",
            "before_color": (90, 80, 50),
            "after_text": "AFTER: De-clogged Drain & Sealed Chamber Lid",
            "after_color": (40, 100, 140),
            "work_desc": "Used high-pressure jetting rods to clear plastic debris from the main culvert and replaced broken cement slab cover."
        },
        {
            "title": "Fallen Tree Branches Obstructing Bus Shelter",
            "category": "safety",
            "desc": "Heavy storm knocked down a large banyan branch blocking the bus stop queue and encroaching lane 1.",
            "location": "Near Sambhaji Park Bus Depot, Nigdi",
            "lat": 18.6540,
            "lon": 73.7710,
            "reporter": citizens[2],
            "worker": orgs[1], # GreenEarth_Society
            "before_text": "BEFORE: Heavy Branch Fallen on Bus Shed",
            "before_color": (80, 70, 40),
            "after_text": "AFTER: Branch Cut, Stacked & Shelter Cleared",
            "after_color": (50, 130, 60),
            "work_desc": "Sawed and cleared the obstructing branches into timber bundles, clearing the pedestrian zone and bus shelter access."
        }
    ]

    for idx, c in enumerate(verification_cases):
        v = Violation.objects.create(
            title=c["title"],
            category=c["category"],
            description=c["desc"],
            location=c["location"],
            latitude=c["lat"],
            longitude=c["lon"],
            reported_by=c["reporter"],
            adopted_by=c["worker"],
            status=Violation.Status.PENDING_VERIFICATION,
            image=create_banner_image(c["before_text"], bg_color=c["before_color"], label="HAZARD REPORT", filename=f"verify_before_{idx}.jpg")
        )
        sub = WorkSubmission.objects.create(
            violation=v,
            worker=c["worker"],
            before_photo=v.image,
            work_description=c["work_desc"]
        )
        after_img = create_banner_image(c["after_text"], bg_color=c["after_color"], label="RESOLUTION PROOF", filename=f"verify_after_{idx}.jpg")
        WorkSubmissionImage.objects.create(submission=sub, image=after_img)
        print(f"  [PENDING VERIFICATION] {v.title}")

    # C. ADOPTED (In Progress by Workers / NGOs)
    adopted_cases = [
        {
            "title": "Burst Potable Water Pipeline Gushing on Dange Chowk",
            "category": "water",
            "desc": "Continuous high-pressure leak wasting fresh municipal drinking water and flooding the low-lying market stalls.",
            "location": "Dange Chowk Flyover Junction, Wakad",
            "lat": 18.6015,
            "lon": 73.7645,
            "reporter": citizens[0],
            "worker": volunteers[2], # Rahul_SocialWorker
            "text": "IN PROGRESS: Main Valve Clamped, Pipe Welding Underway",
            "color": (40, 80, 130)
        },
        {
            "title": "Open Manhole Without Warning Barricade near Hospital",
            "category": "safety",
            "desc": "Heavy iron manhole cover stolen or missing outside City Care Hospital, extreme risk for night ambulances and bikers.",
            "location": "Opposite City Care Hospital, Thergaon",
            "lat": 18.6140,
            "lon": 73.7810,
            "reporter": citizens[3],
            "worker": orgs[0], # CleanCity_Foundation
            "text": "IN PROGRESS: Heavy-duty FRP Manhole Cover Sourced",
            "color": (150, 90, 30)
        },
        {
            "title": "Damaged Pedestrian Footpath Paver Blocks",
            "category": "encroachment",
            "desc": "Paver blocks uprooted and dumped on the tactile blind paving, forcing senior citizens to walk into vehicular traffic.",
            "location": "Kundan Nagar, Dapodi Road",
            "lat": 18.5795,
            "lon": 73.8310,
            "reporter": citizens[1],
            "worker": volunteers[0], # Arjun_Volunteer
            "text": "IN PROGRESS: Leveling Sand Bed & Re-laying Tactile Pavers",
            "color": (90, 60, 110)
        }
    ]

    for idx, c in enumerate(adopted_cases):
        v = Violation.objects.create(
            title=c["title"],
            category=c["category"],
            description=c["desc"],
            location=c["location"],
            latitude=c["lat"],
            longitude=c["lon"],
            reported_by=c["reporter"],
            adopted_by=c["worker"],
            status=Violation.Status.ADOPTED,
            image=create_banner_image(c["text"], bg_color=c["color"], label="IN PROGRESS ADOPTION", filename=f"adopted_{idx}.jpg")
        )
        print(f"  [ADOPTED] {v.title}")

    # D. PENDING (Newly Reported Community Hazards)
    pending_cases = [
        {
            "title": "Dangerous Deep Pothole Cluster outside Hinjewadi Phase 1",
            "category": "road",
            "desc": "Series of 5 consecutive potholes causing severe gridlock and bike accidents during monsoon rains.",
            "location": "Hinjewadi Phase 1 Circle, Pune",
            "lat": 18.5912,
            "lon": 73.7389,
            "reporter": citizens[0],
            "text": "NEW HAZARD: Deep Pothole Cluster at Tech Park Circle",
            "color": (160, 40, 40)
        },
        {
            "title": "Commercial Construction Debris Blockade on Cycle Track",
            "category": "garbage",
            "desc": "Truckloads of concrete rubble and plaster dumped along the dedicated public cycling and jogging path.",
            "location": "BRTS Corridor, Ravet Bridge",
            "lat": 18.6535,
            "lon": 73.7420,
            "reporter": citizens[1],
            "text": "NEW HAZARD: Illegal Rubble Dump on Cycle Track",
            "color": (130, 50, 50)
        },
        {
            "title": "Hanging High Voltage Electric Cable near Vegetable Market",
            "category": "electricity",
            "desc": "Storm loosened an overhead electric line, now dangling less than 7 feet above the busy evening street market.",
            "location": "Sant Tukaram Nagar Mandi, Pimpri",
            "lat": 18.6290,
            "lon": 73.8160,
            "reporter": citizens[2],
            "text": "NEW HAZARD: Low Hanging Live Electrical Wire",
            "color": (170, 70, 30)
        },
        {
            "title": "Stagnant Water Reservoir Breeding Dengue Mosquitos",
            "category": "drainage",
            "desc": "Abandoned plot with 3 feet of stagnant rainwater creating heavy mosquito breeding ground next to residential towers.",
            "location": "Kaspate Vasti, Wakad",
            "lat": 18.5990,
            "lon": 73.7720,
            "reporter": citizens[4],
            "text": "NEW HAZARD: Massive Stagnant Water Breeding Pool",
            "color": (120, 80, 40)
        }
    ]

    for idx, c in enumerate(pending_cases):
        v = Violation.objects.create(
            title=c["title"],
            category=c["category"],
            description=c["desc"],
            location=c["location"],
            latitude=c["lat"],
            longitude=c["lon"],
            reported_by=c["reporter"],
            status=Violation.Status.PENDING,
            image=create_banner_image(c["text"], bg_color=c["color"], label="PENDING MUNICIPAL HAZARD", filename=f"pending_{idx}.jpg")
        )
        print(f"  [PENDING] {v.title}")

    print("\n=========================================")
    print("SUCCESS: Database refreshed with fresh civic entries!")
    print(f"Total Violations: {Violation.objects.count()}")
    print(f" - Pending: {Violation.objects.filter(status='Pending').count()}")
    print(f" - In Progress (Adopted): {Violation.objects.filter(status='Adopted').count()}")
    print(f" - Pending Verification: {Violation.objects.filter(status='Pending Verification').count()}")
    print(f" - Verified Resolutions: {Violation.objects.filter(status='Resolved').count()}")
    print("=========================================")


if __name__ == "__main__":
    wipe_and_seed()
