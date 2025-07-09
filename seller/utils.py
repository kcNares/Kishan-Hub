import random
import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut


def get_city_bounding_box(place_name, max_retries=3, delay=1):
    """
    Get bounding box of a city/place via Nominatim.
    Returns (south_lat, north_lat, west_lon, east_lon)
    """
    geolocator = Nominatim(user_agent="farm_tool_rental_app")
    retries = 0

    while retries < max_retries:
        try:
            location = geolocator.geocode(place_name, exactly_one=True, timeout=10)
            if location and location.raw.get("boundingbox"):
                bbox = location.raw["boundingbox"]
                south_lat, north_lat = float(bbox[0]), float(bbox[1])
                west_lon, east_lon = float(bbox[2]), float(bbox[3])
                return south_lat, north_lat, west_lon, east_lon
            return None
        except GeocoderTimedOut:
            retries += 1
            time.sleep(delay)

    return None


def get_random_point_in_location(place_name):
    """
    Generates a random lat/lon within the bounding box of the given place.
    """
    bbox = get_city_bounding_box(place_name)
    if bbox is None:
        return None, None

    south_lat, north_lat, west_lon, east_lon = bbox

    # Generate random point
    random_lat = random.uniform(south_lat, north_lat)
    random_lon = random.uniform(west_lon, east_lon)

    return random_lat, random_lon
