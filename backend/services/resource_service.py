"""Resource Service — Location-based resource ranking.
Follows PRD.md F6 and DATABASE_SCHEMA.md resources table.
"""
import math
import logging
from sqlalchemy.orm import Session
from db.models import Resource

logger = logging.getLogger(__name__)

# Category priority order per risk level
CATEGORY_PRIORITY = {
    "CRITICAL": ["ambulance", "police", "hospital", "shelter", "mental_health", "helpline"],
    "HIGH": ["mental_health", "shelter", "hospital", "police", "helpline", "ngo"],
    "MEDIUM": ["helpline", "mental_health", "ngo", "shelter", "hospital"],
    "LOW": ["helpline", "ngo", "mental_health"],
    "UNKNOWN": ["helpline", "mental_health", "ngo"],
}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in km between two lat/lng points."""
    R = 6371  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class ResourceService:
    def __init__(self, db: Session):
        self.db = db

    def get_ranked_resources(
        self,
        city: str | None = None,
        state: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        risk_level: str = "MEDIUM",
        categories: list[str] | None = None,
        languages: list[str] | None = None,
        limit: int = 8
    ) -> list[dict]:
        """Get resources ranked by risk level priority and distance."""
        query = self.db.query(Resource).filter(Resource.active == True)

        # Geographic filter
        if city:
            query = query.filter(Resource.city.ilike(f"%{city}%"))
        elif state:
            query = query.filter(Resource.state.ilike(f"%{state}%"))

        # Category filter
        if categories:
            query = query.filter(Resource.category.in_(categories))

        resources = query.all()

        # Add national (no city/state) resources
        national = self.db.query(Resource).filter(
            Resource.active == True,
            Resource.city == None,
            Resource.state == None
        ).all()
        all_resources = resources + [r for r in national if r not in resources]

        # Compute distance and score each
        category_order = CATEGORY_PRIORITY.get(risk_level, CATEGORY_PRIORITY["MEDIUM"])

        def rank_key(r: Resource):
            # Category priority score (lower = better)
            try:
                cat_rank = category_order.index(r.category)
            except ValueError:
                cat_rank = 99

            # Distance score
            dist_km = 999.0
            if lat and lng and r.lat and r.lng:
                dist_km = haversine_km(lat, lng, r.lat, r.lng)

            # Effectiveness
            effectiveness = r.follow_through_rate or 0.5

            return (cat_rank, dist_km, -effectiveness)

        sorted_resources = sorted(all_resources, key=rank_key)[:limit]

        result = []
        for r in sorted_resources:
            dist_km = None
            if lat and lng and r.lat and r.lng:
                dist_km = round(haversine_km(lat, lng, r.lat, r.lng), 1)

            result.append({
                "id": str(r.id),
                "name": r.name,
                "name_hi": r.name_hi,
                "category": r.category,
                "phone": r.phone,
                "address": r.address,
                "city": r.city,
                "state": r.state,
                "lat": r.lat,
                "lng": r.lng,
                "available_24x7": r.available_24x7,
                "hours": r.hours,
                "distance_km": dist_km,
                "dispatchable": r.dispatchable,
                "dispatch_type": r.dispatch_type,
                "follow_through_rate": r.follow_through_rate,
            })

        return result

    def get_by_id(self, resource_id: str) -> Resource | None:
        from uuid import UUID
        try:
            return self.db.query(Resource).filter(
                Resource.id == UUID(resource_id)
            ).first()
        except ValueError:
            return None
