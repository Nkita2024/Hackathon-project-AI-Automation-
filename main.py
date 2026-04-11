from fastapi import FastAPI
from pydantic import BaseModel
import requests, re
from bs4 import BeautifulSoup
import openai

openai.api_key = "sk-xxxx..."   # paste your API key here

app = FastAPI()
results = []

# --- Scraping Helper ---
def scrape_site(url: str) -> dict:
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    title = soup.title.string if soup.title else "N/A"
    emails = list(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", r.text)))
    phones = list(set(re.findall(r"\+?\d[\d\s-]{7,15}", r.text)))
    addresses = list(set(re.findall(r"\d{1,5}\s\w+\s\w+.*", r.text)))[:1]

    text = " ".join([p.get_text() for p in soup.find_all("p")])
    text = re.sub(r"\s+", " ", text)[:2000]

    return {
        "website_name": title,
        "company_name": title,
        "address": addresses[0] if addresses else "N/A",
        "mobile_number": phones[0] if phones else "N/A",
        "mail": emails if emails else [],
        "raw_text": text
    }

# --- AI Helper ---
def ai_enrich(text: str) -> dict:
    if not text.strip():
        return {
            "core_service": "N/A",
            "target_customer": "N/A",
            "probable_pain_point": "N/A",
            "outreach_opener": "N/A"
        }

    prompt = f"""
    From the following company description, extract:
    - core_service
    - target_customer
    - probable_pain_point
    - outreach_opener (short personalized message)

    Return JSON only.
    Text: {text}
    """

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        temperature=0
    )
    try:
        return eval(response.choices[0].message["content"])
    except:
        return {
            "core_service": "N/A",
            "target_customer": "N/A",
            "probable_pain_point": "N/A",
            "outreach_opener": "N/A"
        }

# --- API Endpoints ---
class URLInput(BaseModel):
    url: str

@app.post("/enrich")
def enrich(input: URLInput):
    base_data = scrape_site(input.url)
    ai_data = ai_enrich(base_data["raw_text"])
    result = {
        "website_name": base_data["website_name"],
        "company_name": base_data["company_name"],
        "address": base_data["address"],
        "mobile_number": base_data["mobile_number"],
        "mail": base_data["mail"],
        "core_service": ai_data.get("core_service", "N/A"),
        "target_customer": ai_data.get("target_customer", "N/A"),
        "probable_pain_point": ai_data.get("probable_pain_point", "N/A"),
        "outreach_opener": ai_data.get("outreach_opener", "N/A")
    }
    results.append(result)
    return result

@app.get("/results")
def get_results():
    return results

