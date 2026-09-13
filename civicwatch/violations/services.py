import logging
from math import radians, cos, sin, asin, sqrt
from django.conf import settings

logger = logging.getLogger(__name__)

def haversine_distance(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    in kilometers.
    """
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371  # Radius of earth in kilometers
    return c * r

class DuplicateDetectionService:
    @staticmethod
    def find_duplicate_violations(category, latitude, longitude, radius_meters=None, exclude_id=None):
        """
        Finds active (non-resolved, non-rejected) violations with the same category
        within the specified radius (in meters).
        """
        from .models import Violation

        if latitude is None or longitude is None or not category:
            return []

        radius_m = radius_meters if radius_meters is not None else getattr(settings, 'CIVICWATCH_DUPLICATE_RADIUS_METERS', 50)
        radius_km = radius_m / 1000.0

        # Rough bounding box pre-filtering for database efficiency
        # 1 deg latitude ~= 111.32 km
        lat_delta = radius_km / 111.32
        cos_lat = cos(radians(latitude))
        lng_delta = radius_km / (111.32 * max(cos_lat, 0.0001))

        # Filter only active open violations (Pending, Adopted, Pending Verification)
        active_statuses = [
            Violation.Status.PENDING,
            Violation.Status.ADOPTED,
            Violation.Status.PENDING_VERIFICATION
        ]

        candidates = Violation.objects.filter(
            category=category,
            status__in=active_statuses,
            latitude__gte=latitude - lat_delta,
            latitude__lte=latitude + lat_delta,
            longitude__gte=longitude - lng_delta,
            longitude__lte=longitude + lng_delta
        )

        if exclude_id:
            candidates = candidates.exclude(id=exclude_id)

        duplicates = []
        for cand in candidates:
            dist_km = haversine_distance(longitude, latitude, cand.longitude, cand.latitude)
            dist_m = dist_km * 1000.0
            if dist_m <= radius_m:
                duplicates.append({
                    'violation': cand,
                    'distance_meters': round(dist_m, 1)
                })

        return duplicates

    @staticmethod
    def check_is_duplicate(category, latitude, longitude, radius_meters=None, exclude_id=None):
        """Convenience method returning (is_duplicate: bool, first_match: dict or None)."""
        dupes = DuplicateDetectionService.find_duplicate_violations(
            category=category,
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            exclude_id=exclude_id
        )
        if dupes:
            return True, dupes[0]
        return False, None

class ViolationService:
    @staticmethod
    def send_status_update_sms(user, status):
        """Simulate sending an SMS notification for status updates."""
        message = f"CivicWatch Update: Your reported issue is now marked as '{status}'."
        print(f"\n--- [SMS SENT TO {user.username}] ---\n{message}\n-------------------------------\n")
        logger.info(f"SMS sent to {user.username} regarding status: {status}")
