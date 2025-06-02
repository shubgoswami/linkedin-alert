import os
import hashlib
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time # Import the time module for potential sleep


# Fetch Telegram bot token and user ID from environment variables for security
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.environ.get("TELEGRAM_USER_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_USER_ID:
    raise ValueError("Telegram Bot Token or User ID is not set. Please configure them properly.")

# LinkedIn URLs to scrape jobs from
LINKEDIN_URLS = [
    "https://www.linkedin.com/jobs/search/?f_TPR=r86400&geoId=102454443&keywords=product%20manager",
    "https://www.linkedin.com/jobs/search/?f_TPR=r86400&geoId=104305776&keywords=product%20manager",
    "https://jobs.careem.com/?locations=Dubai%2C+United+Arab+Emirates&locations=Abu+Dhabi%2C+United+Arab+Emirates&query=product+manager"
]

def fetch_rendered_html(url):
    """
    Uses Playwright to open the page and wait for job listings to load.
    Returns the fully rendered HTML content.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # Run in headless mode for GitHub Actions
        page = browser.new_page()

        print(f"Navigating to URL: {url}")
        # Navigate and wait until network is idle
        # This means no more than 0 network connections for at least 500 ms.
        page.goto(url, wait_until="networkidle")
        print("Page navigation complete, waiting for content...")

        # Introduce a short, explicit wait to ensure initial content settles
        page.wait_for_timeout(3000) # Wait for 3 seconds after networkidle

        # Scroll down multiple times to trigger lazy loading of jobs
        # We can also check for a specific scrollable element if LinkedIn uses one
        # For general scrolling, repeat the scroll action
        for i in range(5): # Increased to 5 scrolls for more aggressive loading
            print(f"Scrolling down (attempt {i+1})...")
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000) # Wait for 2 seconds after each scroll

        # Attempt to wait for the selector again, but with a potentially more specific condition
        # For example, we can wait until the element is "attached" to the DOM, not just visible.
        # Or, we can simply rely on the content being present after scrolling.
        try:
            # Let's try waiting for the selector to be attached, which is a weaker condition than 'visible'
            # and might indicate it's in the DOM even if not fully rendered/interactive yet.
            page.wait_for_selector("li.base-search-card", state="attached", timeout=45000) # Increased timeout significantly
            print("Successfully found 'li.base-search-card' after extended wait.")
        except Exception as e:
            print(f"Final wait for selector failed: {e}. Attempting to get page content anyway.")


        html = page.content()
        browser.close()
    return html

def extract_jobs_from_html(html):
    """
    Parses the rendered HTML to extract job information using BeautifulSoup.
    Returns a list of job dicts containing title, company, location, posted date, uid, and URL.
    """
    soup = BeautifulSoup(html, 'html.parser')
    # Use a more robust selector if needed, but 'base-search-card' looks okay from page-source.html
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
            print(f"Failed to parse job: {e} for element: {job_elem}") # Added job_elem to debug
            continue # Continue to the next job element even if one fails

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
    print("Starting job scrape...")

    all_scraped_jobs = [] # Collect all jobs from all URLs

    for url in LINKEDIN_URLS:
        print(f"Processing URL: {url}")
        html = fetch_rendered_html(url)
        jobs = extract_jobs_from_html(html)
        print(f"Found {len(jobs)} jobs from {url}")
        all_scraped_jobs.extend(jobs)

    if all_scraped_jobs:
        message = "<b>New LinkedIn Job Alerts:</b>\n"
        for job in all_scraped_jobs:
            message += (
                f"\n• <b>Title</b>: {job['title']}"
                f"\n  <b>Company</b>: {job['company']}"
                f"\n  <b>Location</b>: {job['location']}"
                f"\n  <b>Posted</b>: {job['posted']}"
                f"\n  <b>Link</b>: {job['url']}\n" # Removed UID from Telegram message for brevity
            )
        print("Sending message to Telegram...")
        send_telegram_message(message)
    else:
        print("No new jobs found across all URLs.")

if __name__ == "__main__":
    main()