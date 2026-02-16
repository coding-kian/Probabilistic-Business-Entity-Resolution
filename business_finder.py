# business_finder.py
# this uses good maps api
import threading, time, json, requests, logging
from postcode_region import calculate_bounding_box
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

class MyThread(threading.Thread):
    def __init__(self, target_function, args=()):
        super().__init__(target=target_function, args=args)
        self.result = None

    def run(self): # Call the _target function and store the result in selfresult
        self.result = self._target(*self._args)


def postcode_to_coords(postcode: str) -> tuple[float, float]:
    response = requests.get(f"https://api.postcodes.io/postcodes/{postcode}", timeout=10)
    response.raise_for_status() # raises specific error so we know why it didnt work
    results = response.json()["result"]
    return results['latitude'], results['longitude']


def locational_grid(radius: int, main_lat: float, main_long: float) -> list[tuple[float, float]]:
    radius_km = (radius*1.618)/1000 # Expands radius to reduce gaps when using a 3x3 sampling grid
    min_lat, max_lat, min_long, max_long = calculate_bounding_box(main_lat, main_long, radius_km)

    return [(min_lat, min_long), (min_lat, main_long), (min_lat, max_long),
             (main_lat, min_long), (main_lat, main_long), (main_lat, max_long),
             (max_lat, min_long), (max_lat, main_long), (max_lat, max_long)]


def businesses_subsection(radius: int, latitude: float, longitude: float, keyword: str, api_key: str) -> list:
    session = requests.Session()

    params1 = {"location": f"{latitude},{longitude}", "radius": radius, "keyword": keyword, "key": api_key}
    req1 = session.get(PLACES_NEARBY_URL, params=params1, timeout=10)
    req1.raise_for_status()
    results1 = req1.json()
    current_results = list(results1.get("results", []))
    logger.info(f"{len(current_results)}, {req1.url}")

    next_page_token = results1.get("next_page_token")

    for i in range(2): # up to 2 extra pages (60 results max)
        if not next_page_token: break
        time.sleep(2) # delay since needs time before valid token

        params2 = {"pagetoken": next_page_token, "key": api_key}
        req2 = session.get(PLACES_NEARBY_URL, params=params2, timeout=10)
        req2.raise_for_status()
        results2 = req2.json()
        extra = list(results2.get("results", []))
        logger.info(f"Extra: {len(extra)}, {req2.url}")

        next_page_token = results2.get("next_page_token")
        current_results.extend(extra)
    
    return current_results


def all_businesses(radius: int, main_lat: float, main_long: float, keywords: list) -> list:
    """
    Gets all of the ifnomation for the business
    """
    with open("configs.env", "r") as f:
        api_key = json.load(f)["key"]

    all_threads = []
    indexer = 0
    for keyword in keywords:
        for latitude, longitude in locational_grid(radius, main_lat, main_long):
            all_threads.append(MyThread(target_function=businesses_subsection, args=(radius, latitude, longitude, keyword, api_key)))
            all_threads[indexer].start()
            indexer+=1
            time.sleep(0.25)

    unique_places = dict()
    for i in all_threads:
        i.join()
        if i.result:
            for place in i.result:
                place_id = place.get("place_id")
                if place_id and place_id not in unique_places:
                    unique_places[place_id] = place

    unique_list = list(unique_places.values())

    logger.info(f"Unique: {len(unique_list)}")
    with open("places_data.json", "w", encoding="utf-8") as f:
        json.dump(unique_list, f, indent=2)

    return unique_list


if __name__ == "__main__":
    pass

