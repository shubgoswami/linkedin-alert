import os
import hashlib
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time
import json
import random # Import the random module

# For Playwright Stealth - you'll need to install this library
# pip install playwright-extra playwright-stealth
from playwright_stealth import stealth_sync

# Fetch Telegram bot token and user ID from environment variables for security
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.environ.get("TELEGRAM_USER_ID")
# Fetch LinkedIn cookies from environment variables
LINKEDIN_COOKIES_JSON = os.environ.get("LINKEDIN_COOKIES")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_USER_ID:
    raise ValueError("Telegram Bot Token or User ID is not set. Please configure them properly.")
if not LINKEDIN_COOKIES_JSON:
    raise ValueError("LINKEDIN_COOKIES is not set. Please configure it in GitHub Secrets.")

# LinkedIn URLs to scrape jobs from
LINKEDIN_URLS = [
    "https://www.linkedin.com/jobs/search/?f_TPR=r86400&geoId=102454443&keywords=product%20manager",
    "https://www.linkedin.com/jobs/search/?f_TPR=r86400&geoId=104305776&keywords=product%20manager"
]

# Function to generate a random delay
def random_delay(min_sec=1, max_sec=4):
    time.sleep(random.uniform(min_sec, max_sec))

def fetch_rendered_html(url):
    """
    Uses Playwright to open the page, inject cookies, and wait for job listings to load.
    Includes stealth measures and randomized delays.
    Returns the fully rendered HTML content.
    """
    with sync_playwright() as p:
        # Launch browser with headless mode for GitHub Actions
        browser = p.chromium.launch(headless=True)

        # Create a new browser context with a human-like user agent
        # and apply stealth settings
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        stealth_sync(context) # Apply stealth to the context

        try:
            cookies = json.loads(LINKEDIN_COOKIES_JSON)
            context.add_cookies(cookies)
            print("Successfully loaded and added cookies to Playwright context.")
        except json.JSONDecodeError as e:
            print(f"Error parsing LINKEDIN_COOKIES_JSON: {e}")
            print("Please ensure your LINKEDIN_COOKIES secret is valid JSON.")
            context.close() # Close context and browser on error
            browser.close()
            return "" # Return empty if cookies are invalid

        page = context.new_page()

        print(f"Navigating to URL: {url}")
        try:
            # Navigate and wait until 'domcontentloaded' with increased timeout
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            print("Page navigation complete, waiting for content...")
            random_delay(3, 7) # Longer, randomized initial delay

            # Attempt to close common sign-in or other pop-up modals
            # These might still appear even with authentication if the session is old
            # or for other prompts (e.g., notifications).
            close_button_selectors = [
                'button.modal__dismiss',
                'button.cta-modal__dismiss-btn',
                'button[aria-label="Dismiss"]',
                'button[data-modal="blurred-overlay-jobs-sign-in-modal"]'
            ]
            for selector in close_button_selectors:
                if page.is_visible(selector):
                    print(f"Attempting to close modal with selector: {selector}")
                    try:
                        page.click(selector)
                        random_delay(2, 4) # Randomized delay after clicking
                        if not page.is_visible(selector):
                            print(f"Modal closed successfully with selector: {selector}")
                            break
                    except Exception as click_error:
                        print(f"Error clicking {selector}: {click_error}. Continuing...")
                else:
                    print(f"Modal close button '{selector}' not visible.")


            # Scroll down multiple times to trigger lazy loading of jobs
            for i in range(5):
                print(f"Scrolling down (attempt {i+1})...")
                # Use evaluate for more controlled scrolling, simulating user behavior
                page.evaluate("window.scrollBy(0, document.body.scrollHeight/5)") # Scroll by partial height
                random_delay(2, 5) # Randomized delay after each scroll

            # Final wait for job cards (expecting them to be visible now)
            try:
                page.wait_for_selector("li.base-search-card", state="visible", timeout=45000)
                print("Successfully found 'li.base-search-card' after extended wait.")
            except Exception as e:
                print(f"Final wait for selector failed: {e}. Attempting to get page content anyway.")

        except Exception as e:
            print(f"Page.goto failed or other critical error during navigation/interaction: {e}. URL: {url}")
            context.close()
            browser.close()
            return "" # Return empty HTML if navigation/interaction fails

        html = page.content()
        context.close() # Close the context
        browser.close() # Close the browser
    return html

def extract_jobs_from_html(html):
    """
    Parses the rendered HTML to extract job information using BeautifulSoup.
    Returns a list of job dicts containing title, company, location, posted date, uid, and URL.
    """
    if not html: # Handle case where html is empty due to navigation failure
        return []

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
            print(f"Failed to parse job: {e} for element: {job_elem}")
            continue

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

    all_scraped_jobs = []

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
                f"\n  <b>Link</b>: {job['url']}\n"
            )
        print("Sending message to Telegram...")
        send_telegram_message(message)
    else:
        print("No new jobs found across all URLs.")

if __name__ == "__main__":
    main()