import os
import django
import random
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'civicwatch.settings')
django.setup()

from django.utils import timezone
from django.db import transaction
from user.models import CustomUser
from violations.models import (
    Violation, WorkSubmission, WorkSubmissionImage,
    WorkRating, Comment, Certificate,
)

print("=" * 60)
print("STEP 1: WIPE EXISTING REPORT DATA")
print("=" * 60)

violations_deleted = Violation.objects.all().delete()
print(f"  Deleted violations + related: {violations_deleted}")

CustomUser.objects.all().update(civic_points=0)
print(f"  Reset all user civic_points to 0")

print()
print("=" * 60)
print("STEP 2: SELECT USER POOL")
print("=" * 60)

citizens = list(CustomUser.objects.filter(role='citizen').order_by('id'))
volunteers = list(CustomUser.objects.filter(role='volunteer', is_verified=True).order_by('id'))
organizations = list(CustomUser.objects.filter(role='organization', is_verified=True).order_by('id'))

workers = volunteers + organizations
random.seed(42)
random.shuffle(citizens)
random.shuffle(workers)

print(f"  Citizen reporters available: {len(citizens)}")
print(f"  Volunteer/NGO workers available: {len(workers)}")

print()
print("=" * 60)
print("STEP 3: DEFINE NEW REALISTIC REPORTS")
print("=" * 60)

CAT = Violation.Category
ST = Violation.Status

NEW_REPORTS = [
    {
        "title": "Massive Pothole on Linking Road Endangering Commuters",
        "description": "A 3-foot-deep pothole has opened up right in the middle of the busy Linking Road near the Bandra signal. Two wheeler riders have been falling off daily. Monsoon water hides it completely during rains. Needs immediate filling before a serious accident occurs.",
        "category": CAT.ROAD,
        "location": "Linking Road, Bandra West, Mumbai",
        "latitude": 19.0610,
        "longitude": 72.8258,
        "status": ST.ADOPTED,
        "days_ago": 4,
        "work_description": "Team reached site on day 2. Excavated broken pavement layer, laid WMM base, 40mm BC wearing course. Street reopened same evening.",
        "rating_avg": 4.6,
        "rating_count": 12,
    },
    {
        "title": "Garbage Dumping Ground Next to Public Park in Indiranagar",
        "description": "For the last three weeks, garbage trucks have been illegally dumping municipal waste on the vacant plot next to Indiranagar 100 Feet Road Park. Foul smell, mosquito breeding, and stray dog menace are making the park unusable for children and morning walkers.",
        "category": CAT.GARBAGE,
        "location": "100 Feet Road, Indiranagar, Bengaluru",
        "latitude": 12.9719,
        "longitude": 77.6412,
        "status": ST.RESOLVED,
        "days_ago": 18,
        "work_description": "Coordinated with BBMP solid waste team. Removed 12 trucks of legacy waste, levelled ground, installed barbed wire fencing + anti-dumping signage with CCTV warning. Daily ward patrol now assigned.",
        "rating_avg": 4.8,
        "rating_count": 28,
    },
    {
        "title": "Broken Water Pipeline Flooding MG Road Footpath",
        "description": "A leaking water pipeline near the MG Road metro station entrance has been flowing continuously for over a week. The entire footpath is submerged, forcing pedestrians to walk on the busy main road. Massive water wastage estimated at 5000+ litres per day.",
        "category": CAT.WATER,
        "location": "MG Road, Near Metro Station, Pune",
        "latitude": 18.5214,
        "longitude": 73.8545,
        "status": ST.PENDING_VERIFICATION,
        "days_ago": 6,
        "work_description": "PMC water department reached within 4 hours of adoption. Shut off main valve, replaced 2m section of 150mm CI pipe that had corroded through. Pressure tested OK, footpath mopped dry.",
        "rating_avg": 0.0,
        "rating_count": 0,
    },
    {
        "title": "Non-Functional Street Lights Across Entire Dwarka Sector 7",
        "description": "Almost all street light poles in Dwarka Sector 7 from Pocket 1 to Pocket 4 have been dark for nearly a month. Residents fear evening robberies and women's safety is at risk. Several auto accidents reported due to poor visibility near the roundabout.",
        "category": CAT.ELECTRICITY,
        "location": "Sector 7, Dwarka, New Delhi",
        "latitude": 28.5921,
        "longitude": 77.0460,
        "status": ST.RESOLVED,
        "days_ago": 25,
        "work_description": "Complete electrical audit done. 47 LED bulbs replaced, 3 faulty underground cable joints repaired, central feeder pillar CB upgraded. All poles now burning bright post-sundown. BSES Yamuna now on quarterly preventive check cycle.",
        "rating_avg": 4.9,
        "rating_count": 56,
    },
    {
        "title": "Overflowing Drainage at Park Street Chowk",
        "description": "The drainage chamber right at Park Street crossing is bubbling over with raw sewage. Pedestrians have to jump 4 feet to cross. School children are the worst affected. Rain makes it a sewage lake every evening.",
        "category": CAT.DRAINAGE,
        "location": "Park Street Crossing, Kolkata",
        "latitude": 22.5544,
        "longitude": 88.3514,
        "status": ST.ADOPTED,
        "days_ago": 2,
        "work_description": "KMC sewer de-silting team deployed. High-pressure jet cleaning of 300m trunk line upstream, silt removed, new RCC chamber cover with lifting hooks installed.",
        "rating_avg": 0.0,
        "rating_count": 0,
    },
    {
        "title": "Illegal Encroachment on Varadaraja Perumal Temple Street",
        "description": "Temporary shops and vendors have completely encroached upon the 40-foot-wide road leading to the temple. Ambulances cannot pass, fire safety is zero risk. Devotees and residents have complained repeatedly but no action.",
        "category": CAT.ENCROACHMENT,
        "location": "Temple Street, Mylapore, Chennai",
        "latitude": 13.0330,
        "longitude": 80.2697,
        "status": ST.PENDING,
        "days_ago": 1,
    },
    {
        "title": "Wrong-Side Parking Chaos Near Amanora Mall Entrance",
        "description": "Every weekend evening, 4-wheelers are parked wrong-side directly on the main road leading out of Amanora Mall. Causes 2+ hour traffic jams and multiple honking road rage incidents. Traffic police booth is 100m away but never staffed.",
        "category": CAT.TRAFFIC,
        "location": "Amanora Mall Main Road, Hadapsar, Pune",
        "latitude": 18.5074,
        "longitude": 73.9388,
        "status": ST.PENDING,
        "days_ago": 3,
    },
    {
        "title": "24x7 Loudspeaker Noise Near Sindhi Camp Marriage Garden",
        "description": "A commercial marriage garden in the heart of residential Sindhi Camp plays DJ loudspeakers at 110dB every single night past 2 AM. Elderly residents cannot sleep, students cannot study. Multiple police complaints filed with zero follow-up.",
        "category": CAT.NOISE,
        "location": "Sindhi Camp, Station Road, Jaipur",
        "latitude": 26.9240,
        "longitude": 75.8068,
        "status": ST.RESOLVED,
        "days_ago": 32,
        "work_description": "Joint drive with Jaipur Police Noise Cell + JMC. Sound level meter reading recorded. Fine of ₹50,000 imposed on garden owner. Decibel limit signage installed, time-lock decibel limiter fitted to their main amplifier, midnight hard cutoff enforced.",
        "rating_avg": 4.7,
        "rating_count": 64,
    },
    {
        "title": "Thick Smoke from Open Waste Burning Near Iskcon Flyover",
        "description": "Every evening after 7 PM, dry leaves and plastic waste are set on fire in the open ground beneath Iskcon flyover. The smoke drifts straight into 3 nearby residential high-rises. Asthma patients in the building are on constant inhalers.",
        "category": CAT.AIR,
        "location": "ISKCON Flyover Underpass, Juhu Tara Road, Mumbai",
        "latitude": 19.0995,
        "longitude": 72.8397,
        "status": ST.PENDING_VERIFICATION,
        "days_ago": 9,
        "work_description": "Coordinated with MPCB + BMC. Naka bandobast for 3 consecutive evenings. Two habitual burners fined ₹10k each. Compost bins distributed to all nearby societies. Community beat watch group formed.",
        "rating_avg": 0.0,
        "rating_count": 0,
    },
    {
        "title": "Rusty Broken Playground Swing - Kids Getting Hurt",
        "description": "The main swing set in the Sector 29 community park has rusted chains and a broken seat. A 6-year-old fractured her arm last Tuesday when the chain snapped mid-swing. See-saw and slide also have sharp exposed metal edges.",
        "category": CAT.SAFETY,
        "location": "Community Park, Sector 29, Gurugram",
        "latitude": 28.4679,
        "longitude": 77.0678,
        "status": ST.RESOLVED,
        "days_ago": 40,
        "work_description": "Full playground equipment audit. 3 swings, 1 see-saw, 1 slide refurbished. All chains replaced with stainless steel, rubber edging fixed on all metal corners, 50mm EPDM rubber mulch safety surfacing laid under all play equipment. Certified play-safe by structural consultant.",
        "rating_avg": 4.95,
        "rating_count": 82,
    },
    {
        "title": "Stray Dog Pack Terrorizing Morning Walkers in KBR Park",
        "description": "A pack of 7-8 aggressive stray dogs has been chasing and biting morning walkers inside KBR National Park. 3 bite cases reported in the last week alone. GHMC animal birth control drives seem to have skipped this entire area.",
        "category": CAT.ANIMALS,
        "location": "KBR Park Outer Perimeter, Banjara Hills, Hyderabad",
        "latitude": 17.4230,
        "longitude": 78.4355,
        "status": ST.ADOPTED,
        "days_ago": 5,
        "work_description": "GHMC Blue Cross team on ground. ABC drive scheduled for this week - all 8 dogs will be picked up, sterilized, vaccinated, ear-notched, and relocated to peripheral forest zone. Temporary feeding point set up away from walker path.",
        "rating_avg": 0.0,
        "rating_count": 0,
    },
    {
        "title": "Dilapidated Bus Stop Shelter Near Science City",
        "description": "The only bus stop for the Science City route has a rusted tin roof that sags dangerously and is half blown off. Seats are broken. Commuters young and old stand exposed in 40-degree heat and monsoon rain for 30+ min waits.",
        "category": CAT.OTHER,
        "location": "Science City Cross Roads, Sola, Ahmedabad",
        "latitude": 23.1027,
        "longitude": 72.5488,
        "status": ST.PENDING,
        "days_ago": 7,
    },
    {
        "title": "Manhole Cover Missing Near Prahladnagar BRTS",
        "description": "A 2-foot-diameter manhole on the Prahladnagar BRTS feeder road has been completely open for 10 days. A cyclist fell in last night with serious injuries. No warning barricades or reflectors placed around it.",
        "category": CAT.SAFETY,
        "location": "Prahladnagar BRTS Road, Satellite, Ahmedabad",
        "latitude": 23.0150,
        "longitude": 72.5205,
        "status": ST.RESOLVED,
        "days_ago": 12,
        "work_description": "Emergency response. C.I. cast-iron manhole cover (12-ton rated) replaced within 3 hours of adoption. Surrounding carriageway patch repaired. AMC drainage team now doing quarterly manhole audit for entire Satellite ward.",
        "rating_avg": 4.9,
        "rating_count": 19,
    },
    {
        "title": "Plastic Garbage Choking Rabindra Sarobar Lake Inlet",
        "description": "The northern inlet of Rabindra Sarobar is completely choked with PET bottles, single use plastic bags, and thermocol. Water hyacinth is spreading fast. Migratory bird count this year is down 70% according to local birders.",
        "category": CAT.GARBAGE,
        "location": "Rabindra Sarobar Lake, North Inlet, Kolkata",
        "latitude": 22.5159,
        "longitude": 88.3626,
        "status": ST.ADOPTED,
        "days_ago": 8,
        "work_description": "50+ volunteer cleanup drive held on Sunday. 3.2 tons of plastic waste removed manually + by boat. Trash barrier mesh installed at inlet pipe. 3 bins + weekly dedicated pickup allotted by KMC at inlet point.",
        "rating_avg": 0.0,
        "rating_count": 0,
    },
    {
        "title": "Water Tanker Mafia Overcharging in Electronic City Phase 1",
        "description": "Private water tanker operators in Electronic City Phase 1 have formed a cartel and charge ₹1800 for a 6000L tanker (normal rate ₹800). They cut off supply to apartments that don't comply. BWSSB water lines promised 2 years ago never laid.",
        "category": CAT.WATER,
        "location": "Electronic City Phase 1, Hosur Road, Bengaluru",
        "latitude": 12.8410,
        "longitude": 77.6785,
        "status": ST.PENDING,
        "days_ago": 10,
    },
]

print(f"  Defined {len(NEW_REPORTS)} new civic reports")

print()
print("=" * 60)
print("STEP 4: INSERT INTO DATABASE")
print("=" * 60)

created_violations = []

with transaction.atomic():
    for i, rpt in enumerate(NEW_REPORTS):
        reporter = citizens[i % len(citizens)]
        worker = workers[i % len(workers)] if rpt["status"] != ST.PENDING else None

        created_at = timezone.now() - timedelta(days=rpt["days_ago"])

        v = Violation(
            title=rpt["title"],
            description=rpt["description"],
            category=rpt["category"],
            location=rpt["location"],
            latitude=rpt["latitude"],
            longitude=rpt["longitude"],
            status=rpt["status"],
            reported_by=reporter,
            adopted_by=worker,
            created_at=created_at,
            is_help_requested=(rpt["status"] == ST.ADOPTED and random.random() < 0.4),
            requested_at=created_at + timedelta(hours=3) if (rpt["status"] == ST.ADOPTED and random.random() < 0.4) else None,
        )
        v.save()
        created_violations.append((v, rpt, reporter, worker))
        print(f"  [OK] #{i+1:2d}  {v.status.ljust(20)}  {v.category.ljust(12)}  {v.location[:50]}")

    print()
    print("STEP 4b: Build WorkSubmissions + Ratings + Certificates for adopted/resolved items")
    print()

    TRANSFORM_CATEGORIES = ["road", "garbage", "water", "electricity", "drainage", "noise", "air", "safety", "animals"]

    for v, rpt, reporter, worker in created_violations:
        if v.status in (ST.ADOPTED, ST.PENDING_VERIFICATION, ST.RESOLVED):
            sub_time = v.created_at + timedelta(days=max(1, rpt["days_ago"] - 1))

            sub = WorkSubmission(
                violation=v,
                worker=worker,
                work_description=rpt.get("work_description", ""),
                before_photo=None,
                submitted_at=sub_time,
                avg_rating=rpt["rating_avg"],
                rating_count=rpt["rating_count"],
            )
            sub.save()
            print(f"  Submission created for: {v.title[:55]}…  (ratings: {rpt['rating_count']})")

            if v.category in TRANSFORM_CATEGORIES and rpt["rating_count"] > 0:
                for j in range(2):
                    img = WorkSubmissionImage(
                        submission=sub,
                        image=None,
                        uploaded_at=sub_time + timedelta(minutes=j * 4),
                    )
                    img.save()

            if v.status == ST.RESOLVED:
                reporter_points = 10
                worker_points = 20 + rpt["rating_count"] // 5
                cert = Certificate(
                    violation=v,
                    issued_to_reporter=reporter,
                    issued_to_worker=worker,
                    points_awarded_reporter=reporter_points,
                    points_awarded_worker=worker_points,
                    issued_at=sub_time + timedelta(days=1),
                )
                cert.save()

                reporter.civic_points += reporter_points
                worker.civic_points += worker_points
                reporter.save()
                worker.save()

            if rpt["rating_count"] > 0:
                raters = citizens[(i + 2) % len(citizens)::3][:max(3, min(7, rpt["rating_count"] // 8 + 2))]
                for idx, rtr in enumerate(raters):
                    if rtr.id == reporter.id or rtr.id == getattr(worker, 'id', None):
                        continue
                    try:
                        WorkRating.objects.get_or_create(
                            submission=sub,
                            user=rtr,
                            defaults={
                                "stars": int(max(3, min(5, round(rpt["rating_avg"] + random.uniform(-0.5, 0.5))))),
                                "review": random.choice([
                                    "Super quick turnaround, area looks brand new!",
                                    "Great work. Community is grateful.",
                                    "Follow up maintenance still being done. Thank you!",
                                    "Wish every issue was fixed this professionally.",
                                    "Before/after difference is night and day.",
                                    "Neighbourhood is actually safe for kids again.",
                                ]),
                                "created_at": sub_time + timedelta(days=idx + 1),
                            },
                        )
                    except Exception:
                        pass

    print()
    print("STEP 4c: Add community comments on active threads")
    for idx, (v, rpt, reporter, worker) in enumerate(created_violations):
        if v.status in (ST.ADOPTED, ST.PENDING_VERIFICATION):
            commenters = citizens[(idx + 1) % len(citizens):(idx + 1) % len(citizens) + 2]
            for cidx, c_user in enumerate(commenters):
                Comment.objects.create(
                    violation=v,
                    user=c_user,
                    text=random.choice([
                        "Thank you for picking this up! This road has been bad for months.",
                        "Passed by yesterday, the spot is definitely being worked on.",
                        "Our whole society has been waiting for this. 🙌",
                        "Can we get an ETA on completion? My commute goes through here.",
                        "Great initiative team! Let's keep all such spots tracked.",
                    ]),
                    created_at=v.created_at + timedelta(days=1 + cidx),
                )

print()
print("=" * 60)
print("STEP 5: FINAL REPORT")
print("=" * 60)

total = Violation.objects.count()
pending = Violation.objects.filter(status=ST.PENDING).count()
adopted = Violation.objects.filter(status=ST.ADOPTED).count()
pv = Violation.objects.filter(status=ST.PENDING_VERIFICATION).count()
resolved = Violation.objects.filter(status=ST.RESOLVED).count()
rejected = Violation.objects.filter(status=ST.REJECTED).count()
subs = WorkSubmission.objects.count()
ratings = WorkRating.objects.count()
after_imgs = WorkSubmissionImage.objects.count()
certs = Certificate.objects.count()
total_points = CustomUser.objects.aggregate(s=__import__('django.db.models').models.Sum('civic_points'))["s"] or 0

print(f"  Total Violations now        : {total}")
print(f"   ├── Pending                : {pending}")
print(f"   ├── Adopted (in progress)  : {adopted}")
print(f"   ├── Pending Verification   : {pv}")
print(f"   ├── Resolved               : {resolved}")
print(f"   └── Rejected               : {rejected}")
print(f"  Work Submissions            : {subs}")
print(f"  Community Ratings           : {ratings}")
print(f"  After-photos (transform)    : {after_imgs}")
print(f"  Certificates issued         : {certs}")
print(f"  Total Civic Credits (users) : {total_points}")
print()
print("DONE. Database reset + fresh civic reports seeded successfully.")
