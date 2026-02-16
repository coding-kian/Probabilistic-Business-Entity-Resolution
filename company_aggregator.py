# company_aggregator.py
import requests, re, json
import pandas as pd
from bs4 import BeautifulSoup
from time import sleep
from business_finder import all_businesses, MyThread, logger
from postcode_region import postcode_to_coords
import threading
from dataclasses import dataclass


@dataclass
class AllInfo:
    websites: set
    emails: set
    mobiles: set
    csv_data: dict
    lock: threading.Lock

@dataclass
class ConditionRules:
    max_ratings: int # 350
    name_length: float # similarity
    word_count: float # similarity

FILTER_WEBSITES = ["xxx", "lloydspharmacy", "instagram", "facebook", "nhs", "youtube", "twitter", "linktr", ".pw", ".top"] # websites not wanted

with open("configs.env", "r") as f:
    config_file = json.load(f)
    api_key = config_file["key"]
    user_agent = config_file["web_agent"]
    company_house_auth = config_file["companyhouse"]


def scraping_websites(website_url: str) -> tuple[list]:
    try: response = requests.get(website_url, timeout=10, headers = {"User-Agent": user_agent})
    except: return [],[],[]
    if response.status_code != 200: return [],[],[]

    else:
        adjusted_website = website_url[:website_url.find("/", 8)]
        main_site_link = adjusted_website if len(adjusted_website) > 8 else website_url

        contact_pages, emails, all_numbers = [], [], []
        soup = BeautifulSoup(response.text, "html.parser")
        email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:\.[A-Za-z]{1,}){0,5}\b")

        # Extract emails from text content in all tags
        for tag in soup.find_all(text=True):
            emails+=re.findall(email_pattern, tag)
            all_numbers += re.findall(r"(?:\+?44|0)(?:\s?\d){10}", tag.replace("(","").replace(")", "").replace("-",""))
        for a_tag in soup.find_all("a", href=True):
            if "contact" not in website_url and "contact" in a_tag["href"]:
                if "http" in a_tag["href"]: contact_pages = [a_tag["href"]]
                else: contact_pages.append(main_site_link+a_tag["href"])
            if a_tag["href"].startswith("mailto:"):
                emails+=[a_tag["href"][7:]]
            if a_tag["href"].startswith("tel:"):
                all_numbers+=[a_tag["href"][4:]]
        
        all_emails_found = list(set(i.lower().replace(" ", "").split("?")[0] for i in emails if i and not re.match(r"^[0-9a-fA-F]+$", i[:i.find("@")]) and "%" not in i and "\\" not in i))

        all_numbers_found = []
        for i in all_numbers:
            j = i.replace(" ", "").replace("+44", "0")
            if len(j) == 11 and "00" != j[:2]: # uk mobile number length is 11
                all_numbers_found.append(j)

        if not (all_numbers_found+all_emails_found) and contact_pages:
            for i in contact_pages[:3]: # only need a few samples so capped at 3
                a, b, c = scraping_websites(i)
                all_emails_found.extend(a)
                all_numbers_found.extend(b)

        return list(set(all_emails_found)), list(set(all_numbers_found)), [i for i in set(all_numbers_found) if "07" == i[:2]]


def finding_directors(company_number: int) -> list:
    url = f"https://api.company-information.service.gov.uk/company/{company_number}/officers"
    response = requests.get(url, timeout=10, headers = {"Authorization": company_house_auth})

    if response.status_code == 200:
        all_directors = []
        response_data = response.json()
        for i in response_data["items"]:
            if not "resigned_on" in i.keys() and "date_of_birth" in i.keys() and i["officer_role"]=="director":
                name_formatted = [j.split(", ") for j in i["name"].replace("'", "").split(" ")]
                dir_name = " ".join(name_formatted[1]+name_formatted[0]).title()
                all_directors.append([dir_name, i["appointed_on"] if "appointed_on" in i.keys() else "2050-01-01", # far future data
                    i["date_of_birth"]["year"]])
        
        return sorted(all_directors, key=lambda i:i[1])


def gathering_company_data(company_name: str, conditions: ConditionRules) -> list:
    my_company_name_adjusted = company_name.lower().replace("ltd","").replace("limited","").replace("llp", "").split(" ")
    url = f"https://api.company-information.service.gov.uk/search/companies?q={company_name}&items_per_page=100"
    response_w_name = requests.get(url, timeout=10, headers = {"Authorization": company_house_auth})

    if response_w_name.status_code == 200:
        response_data2 = response_w_name.json()
        company_dict = dict()
        for i in response_data2["items"]:
            company_name_adjusted = i["title"].lower().replace("ltd","").replace("limited","").replace("llp", "").split(" ")
            word_count = sum([1 if j in my_company_name_adjusted else 0 for j in company_name_adjusted])/len(my_company_name_adjusted)

            length_check = len(my_company_name_adjusted)/len(company_name_adjusted) > conditions.name_length and i["company_status"] == "active"
            if word_count > conditions.word_count and length_check:
                company_dict[(i["company_number"], i["title"])] = word_count

        if company_dict:
            (company_number, company_title), word_count = max(company_dict.items(), key=lambda x: x[1]) # most relevent by word_count
            all_directors = finding_directors(company_number)

            if all_directors:
                return [company_number, company_name.replace("'", "").title(), all_directors, word_count]
    
    return []


def business_element_attributes(place: dict, all_info: AllInfo, conditions: ConditionRules) -> None:
    """
    This checks the individual business details
    """
    place_keys = place.keys()
    if place["business_status"] != "CLOSED_TEMPORARILY" and place["user_ratings_total"] < conditions.max_ratings and (
        place.get("rating") or "photos" in place_keys or "opening_hours" in place_keys):  
        
        place_maps_url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place['place_id']}&key={api_key}"
        
        all_directors_thread = MyThread(target_function=gathering_company_data, args=(place["name"], conditions)); all_directors_thread.start()
        try: place_infomation = requests.get(place_maps_url, timeout=10).json()["result"]
        except: logger.info(f"Exepection"); return

        place_keys = place_infomation.keys()

        phone_number = place_infomation["formatted_phone_number"] if "formatted_phone_number" in place_keys else "x"
        website = place_infomation["website"].lower() if "website" in place_keys else "xxx"

        webcheck = any(i in website for i in FILTER_WEBSITES)
        if (website not in all_info.websites and not webcheck) or "07" == phone_number[:2]:
            all_emails_thread = MyThread(target_function=scraping_websites, args=[website]); all_emails_thread.start()
            all_emails_thread.join()
            all_directors_thread.join()

            all_emails, all_numbers, all_mobiles = all_emails_thread.result
            company_match = all_directors_thread.result
            company_name = company_match[1] if company_match else None
            all_directors = company_match[2] if company_match else []
            company_name_weight = company_match[3] if company_match else None
            

            all_emails = [e for e in all_emails if e not in all_info.emails]
            all_mobiles = [m for m in all_mobiles if m not in all_info.mobiles]
            if "07" == phone_number[:2]: all_mobiles.append(phone_number.replace(" ", ""))

            logger.info(f"{place_infomation['place_id']}, {place['name']}")
            with all_info.lock:
                all_info.websites.add(website)
                all_info.emails.update(all_emails)
                all_info.mobiles.update(all_mobiles)

                if all_emails or all_mobiles:
                    all_info.csv_data[place_infomation["place_id"]] = [
                    place["name"], company_name,
                    website, place_infomation["url"],
                    all_mobiles, all_emails, all_directors, company_name_weight]


if __name__ == "__main__":
    postcode = "sa18en" ## this is a test postcode
    keywords = ["cafe|food|meal|coffee|breakfast",
    "jewelry|gift_shop|pawnshop",
    "fashion|clothes|designer|tailor",
    "pharmacy|medicine|vacination",
    "beauty|salon|spa|health",
    "bakery|cake|wedding|party"] # max possible results about 4000

    main_lat, main_long = postcode_to_coords(postcode)
    all_results: list[dict] = all_businesses(5000, main_lat, main_long, keywords)
    all_info = AllInfo(websites=set(), emails=["info@thepharmacycentre.com"], mobiles=[], csv_data=dict(), lock=threading.Lock())
    conditions = ConditionRules(max_ratings=350, name_length=0.63, word_count=0.66)

    business_element_thread = []
    last_joined = -1
    for index, place in enumerate(all_results):        
        business_element_thread.append(MyThread(target_function=business_element_attributes, args=(place, all_info, conditions)))
        business_element_thread[index].start()
        sleep(0.05)

        if not index%100:
            logger.info(f"{len(business_element_thread)}")
            for i in business_element_thread[index:]:
                i.join()
            last_joined = index

    for i in business_element_thread[last_joined+1:]:
        i.join()

    df = pd.DataFrame(list(all_info.csv_data.values()), columns=["name", "comapny", "website", "url", "mobile", "emails", "directors", "name_weight"])
    df.to_csv("business_emails.csv", index=False)

    print(len(all_results), len(all_info.csv_data))


