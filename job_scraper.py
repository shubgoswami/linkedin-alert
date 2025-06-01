import requests
import json
import hashlib
import time
import os
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.environ.get("TELEGRAM_USER_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_USER_ID:
    raise ValueError("Telegram Bot Token or User ID is not set. Please configure them properly.")

LINKEDIN_URLS = [
    "https://www.linkedin.com/jobs/search/?currentJobId=4241733995&f_TPR=r3600&geoId=102454443&keywords=product%20manager",
    "https://www.linkedin.com/jobs/search/?currentJobId=4241733995&f_TPR=r3600&geoId=104305776&keywords=product%20manager"
]

SEEN_JOBS_FILE = "seen_jobs.json"

def extract_jobs_from_html(html):
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

            uid = hashlib.md5((title + company).encode()).hexdigest()
            jobs.append({"uid": uid, "title": title, "company": company, "location": location, "posted": posted, "url": url})
        except Exception as e:
            print(f"Failed to parse job: {e}")

    return jobs


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_USER_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    requests.post(url, data=payload)


def main():
    new_jobs = []

    headers = {"User-Agent": "Mozilla/5.0"}

    for url in LINKEDIN_URLS:
        resp = requests.get(url, headers=headers)
        jobs = extract_jobs_from_html(resp.text)
        new_jobs.extend(jobs)

    if new_jobs:
        message = "<b>New LinkedIn Job Alerts (Last 1 Hour):</b>\n"
        for job in new_jobs:
            message += (
                f"\n• <b>UID</b>: {job['uid']}"
                f"\n  <b>Title</b>: {job['title']}"
                f"\n  <b>Company</b>: {job['company']}"
                f"\n  <b>Location</b>: {job['location']}"
                f"\n  <b>Posted</b>: {job['posted']}"
                f"\n  <b>Link</b>: {job['url']}\n"
            )
        send_telegram_message(message)

if __name__ == "__main__":
    main()
