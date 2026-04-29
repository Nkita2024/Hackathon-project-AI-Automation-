from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import re, os, json
from bs4 import BeautifulSoup
import openai
from playwright.sync_api import sync_playwright

# Load API key securely
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()
results = []

# --- Scraping Helper (Playwright for JS-heavy sites) ---
def scrape_site(url: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # ✅ Add user agent override to look like Chrome
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                                           "Chrome/123 Safari/537.36")
        page.goto(url, timeout=60000)
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.string if soup.title else "N/A"
    emails = list(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", html)))
    phones = list(set(re.findall(r"\+?\d[\d\s-]{7,15}", html)))
    addresses = list(set(re.findall(r"\d{1,5}\s\w+\s\w+.*", html)))[:1]
    text = " ".join([p.get_text() for p in soup.find_all("p")])
    text = re.sub(r"\s+", " ", text)[:2000]

    # ✅ Fallback if no readable text
    if not text.strip():
        return {
            "website_name": title,
            "company_name": title,
            "address": "N/A",
            "mobile_number": "N/A",
            "mail": [],
            "raw_text": "No readable content found. Try another page."
        }

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
             prompt = f"""
    From the following company description, extract:
    - core_service
    - target_customer
    - probable_pain_point
    - outreach_opener (short personalized message)

    Return JSON only.
    Text: {text}
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        raw_output = response.choices[0].message["content"]
        print("AI raw output:", raw_output)  # ✅ Debug log

        # Try to parse JSON safely
        return json.loads(raw_output)
    except Exception as e:
        print("AI enrichment error:", e)
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

# --- Serve Frontend ---
@app.get("/")
def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))
