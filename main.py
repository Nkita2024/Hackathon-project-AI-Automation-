from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import re, os, json
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
results = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Scraping Helper (Playwright for JS-heavy sites) ---
def scrape_site(url: str) -> dict:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                                               "Chrome/123 Safari/537.36")
            page.goto(url, timeout=60000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")

        title = soup.title.string if soup.title else "N/A"
        emails = list(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", html)))
        phones = list(set(re.findall(r"\+?\d{7,15}", html)))  # stricter phone regex
        addresses = [tag.get_text() for tag in soup.find_all("address")]  # look for <address> tags
        text = " ".join([p.get_text() for p in soup.find_all("p")])
        text = re.sub(r"\s+", " ", text)[:2000]

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
    except Exception as e:
        return {
            "website_name": "Error",
            "company_name": "Error",
            "address": "N/A",
            "mobile_number": "N/A",
            "mail": [],
            "raw_text": f"Scraping failed: {str(e)}"
        }

# --- AI Helper (Bypass Mode) ---
def ai_enrich(text: str) -> dict:
    # Temporary bypass: return placeholders instead of calling OpenAI
    return {
        "core_service": "Bypass mode",
        "target_customer": "Bypass mode",
        "probable_pain_point": "Bypass mode",
        "outreach_opener": "Bypass mode"
    }

# --- API Endpoints ---
class URLInput(BaseModel):
    url: str

@app.post("/enrich")
def enrich(input: URLInput):
    try:
        base_data = scrape_site(input.url)
        ai_data = ai_enrich(base_data.get("raw_text", ""))

        result = {
            "website_name": base_data.get("website_name", "N/A"),
            "company_name": base_data.get("company_name", "N/A"),
            "address": base_data.get("address", "N/A"),
            "mobile_number": base_data.get("mobile_number", "N/A"),
            "mail": base_data.get("mail", []),
            "core_service": ai_data.get("core_service", "N/A"),
            "target_customer": ai_data.get("target_customer", "N/A"),
            "probable_pain_point": ai_data.get("probable_pain_point", "N/A"),
            "outreach_opener": ai_data.get("outreach_opener", "N/A")
        }
        results.append(result)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/results")
def get_results():
    return results

# --- Serve Frontend ---
@app.get("/")
def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))

