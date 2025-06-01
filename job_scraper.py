import os
import hashlib
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Fetch Telegram bot token and user ID from environment variables for security
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.environ.get("TELEGRAM_USER_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_USER_ID:
    raise ValueError("Telegram Bot Token or User ID is not set. Please configure them properly.")

# LinkedIn URLs to scrape jobs from
LINKEDIN_URLS = [
    "https://www.linkedin.com/jobs/search/?currentJobId=4241733995&f_TPR=r3600&geoId=102454443&keywords=product%20manager",
    "https://www.linkedin.com/jobs/search/?currentJobId=4241733995&f_TPR=r3600&geoId=104305776&keywords=product%20manager"
]

def fetch_rendered_html(url):
    """
    Uses Playwright to open the page and wait for job listings to load.
    Returns the fully rendered HTML content.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url)
        # Wait for job cards to appear on the page (timeout: 15 seconds)
        page.wait_for_selector("li.base-search-card", timeout=15000)
        html = page.content()
        browser.close()
    return html

def extract_jobs_from_html(html):
    """
    Parses the rendered HTML to extract job information using BeautifulSoup.
    Returns a list of job dicts containing title, company, location, posted date, uid, and URL.
    """
    soup = BeautifulSoup(html, 'html.parser')
    job_elements = soup.find_all("li", class_="base-search-card")
    jobs = []

    for job_elem in job_elements:
        try:
            title_elem = job_elem.find("h3", class_="base-search-card__title")
            company_elem = job_elem.find("h4", class_="base-search-card__subtitle")
            location_elem = job_elem.find("span", class_="job-search-card__location")
            time_elem = job_elem.find("time")
            link_elem = job_elem.find("a", class_="base-card__full-link")

            title = title_elem.get_text(strip=True) if title_elem else "N/A"
            company = company_elem.get_text(strip=True) if company_elem else "N/A"
            location = location_elem.get_text(strip=True) if location_elem else "N/A"
            posted = time_elem.get_text(strip=True) if time_elem else "N/A"
            url = link_elem['href'] if link_elem else ""

            # Create a unique ID for the job using MD5 hash of title+company
            uid = hashlib.md5((title + company).encode()).hexdigest()

            jobs.append({
                "uid": uid,
                "title": title,
                "company": company,
                "location": location,
                "posted": posted,
                "url": url
            })
        except Exception as e:
            print(f"Failed to parse job: {e}")

    return jobs

def send_telegram_message(message):
    """
    Sends a formatted HTML message to the Telegram user using bot API.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_USER_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    response = requests.post(url, data=payload)
    if not response.ok:
        print(f"Failed to send Telegram message: {response.text}")

def main():
    print("Starting job scrape...")  # Debug print

    new_jobs = []

    for url in LINKEDIN_URLS:
        print(f"Fetching URL: {url}")  # Debug print
        html = fetch_rendered_html(url)
        jobs = extract_jobs_from_html(html)
        print(f"Found {len(jobs)} jobs")  # Debug print
        new_jobs.extend(jobs)

    if new_jobs:
        message = "<b>New LinkedIn Job Alerts:</b>\n"
        for job in new_jobs:
            message += (
                f"\n• <b>Title</b>: {job['title']}"
                f"\n  <b>Company</b>: {job['company']}"
                f"\n  <b>Location</b>: {job['location']}"
                f"\n  <b>Posted</b>: {job['posted']}"
                f"\n  <b>UID</b>: {job['uid']}"
                f"\n  <b>Link</b>: {job['url']}\n"
            )
        print("Sending message to Telegram...")  # Debug print
        send_telegram_message(message)
    else:
        print("No new jobs found.")  # Debug print

if __name__ == "__main__":
    main()
