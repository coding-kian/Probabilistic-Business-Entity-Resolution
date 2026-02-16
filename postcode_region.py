import requests, sqlite3, math

EARTH_RADIUS = 6368 # Earth radius in KM

def calculate_bounding_box(center_lat: float, center_long: float, radius_km: float) -> tuple[float]:
    # Convert latitude and longitude from degrees to radians
    center_lat_rad, center_long_rad = math.radians(center_lat), math.radians(center_long)
    angular_distance = radius_km / EARTH_RADIUS # angular distance in radians of earth surface

    # min & max long & lat, then convert from rads to degrees
    min_lat = (center_lat_rad - angular_distance)*(180.0/math.pi)
    max_lat = (center_lat_rad + angular_distance)*(180.0/math.pi)
    min_long = (center_long_rad - angular_distance/math.cos(center_lat_rad))*(180.0/math.pi)
    max_long = (center_long_rad + angular_distance/math.cos(center_lat_rad))*(180.0/math.pi)


    return round(min_lat, 7), round(max_lat, 7), round(min_long, 7), round(max_long, 7)

def postcode_to_coords(postcode: str) -> tuple[float, float]:
    results = requests.get(f"https://api.postcodes.io/postcodes/{postcode}", timeout=10).json()["result"]
    return round(results['latitude'], 7), round(results['longitude'], 7)


def eligible_postcodes(radius_km: float, postcode: str) -> list:
    center_latitude, center_longitude = postcode_to_coords(postcode)
    min_lat, max_lat, min_long, max_long = calculate_bounding_box(center_latitude, center_longitude, radius_km)

    query = "SELECT * FROM all_uk_postcodes WHERE lat > ? AND lat < ? AND long > ? AND long < ? ORDER BY long ASC;"
    with sqlite3.connect("uk_postcodes.db") as conn:
        cursor = conn.cursor()
        
        cursor.execute(query, (min_lat, max_lat, min_long, max_long))    
        return [i[0] for i in cursor.fetchall()], [min_lat, max_lat, min_long, max_long]


if __name__ == "__main__":
    radius, postcode = 3, "sa18en"
    eligible_postcodes_, coord_region = eligible_postcodes(radius, postcode)
    print(len(eligible_postcodes_))
    print(f"Bottom Right: {coord_region[0]}, {coord_region[2]}")
    print(f"Top Left: {coord_region[1]}, {coord_region[3]}")
    print(eligible_postcodes_[:10], eligible_postcodes_[::-1][:10])
