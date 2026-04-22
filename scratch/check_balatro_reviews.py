import requests
import time
from datetime import datetime

appid = 2379780
cursor = "*"
num_per_page = 100
max_pages = 5

print(f"Checking first {max_pages} pages for appid {appid}...")

for i in range(max_pages):
    url = f"https://store.steampowered.com/appreviews/{appid}"
    params = {
        "json": 1,
        "filter": "recent",
        "language": "all",
        "num_per_page": num_per_page,
        "cursor": cursor,
        "purchase_type": "steam"
    }
    resp = requests.get(url, params=params)
    data = resp.json()
    
    if not data.get("success"):
        print("API Failed")
        break
        
    reviews = data.get("reviews", [])
    if not reviews:
        print("No more reviews")
        break
        
    last_review = reviews[-1]
    ts = last_review.get("timestamp_created")
    dt = datetime.fromtimestamp(ts)
    print(f"Page {i+1}: Last review timestamp: {dt} ({ts})")
    
    cursor = data.get("cursor")
    time.sleep(1)
