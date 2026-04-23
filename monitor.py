import json
import time
import logging
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

CONFIG_FILE = Path(__file__).parent / "config.json"
SEEN_FILE = Path(__file__).parent / "seen_jobs.json"

JOB_TYPE_MAP = {
    "internship": "I",
    "full_time": "F",
    "part_time": "P",
    "contract": "C",
}


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return json.load(f)


def load_seen() -> set:
    if SEEN_FILE.exists():
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set) -> None:
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def build_url(keywords: str, location: str, job_type: str) -> str:
    from urllib.parse import urlencode
    params = {
        "keywords": keywords,
        "location": location,
        "f_JT": JOB_TYPE_MAP.get(job_type, ""),
        "sortBy": "DD",  # sort by date
    }
    return "https://www.linkedin.com/jobs/search/?" + urlencode(params)


def scrape_jobs(page, url: str) -> list[dict]:
    jobs = []
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector(".base-card", timeout=15000)
    except PlaywrightTimeout:
        log.warning("Timeout loading %s", url)
        return jobs

    cards = page.query_selector_all(".base-card")
    for card in cards:
        try:
            title_el = card.query_selector(".base-search-card__title")
            company_el = card.query_selector(".base-search-card__subtitle")
            location_el = card.query_selector(".base-search-card__metadata")
            link_el = card.query_selector("a.base-card__full-link")

            if not title_el or not link_el:
                continue

            href = link_el.get_attribute("href") or ""
            job_id = href.split("?")[0].rstrip("/").split("-")[-1]

            jobs.append({
                "id": job_id,
                "title": title_el.inner_text().strip(),
                "company": company_el.inner_text().strip() if company_el else "Unknown",
                "location": location_el.inner_text().strip() if location_el else "",
                "url": href.split("?")[0],
            })
        except Exception as e:
            log.debug("Error parsing card: %s", e)

    return jobs


def send_discord(webhook_url: str, jobs: list[dict], search: dict) -> None:
    if not jobs:
        return

    lines = [f"**{len(jobs)} neue Job(s)** gefunden für `{search['keywords']}` in `{search['location']}`\n"]
    for job in jobs[:10]:  # Discord message length limit
        lines.append(f"**{job['title']}** @ {job['company']}\n{job['location']}\n{job['url']}\n")

    payload = {"content": "\n".join(lines)}
    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        r.raise_for_status()
        log.info("Discord notification sent (%d jobs)", len(jobs))
    except requests.RequestException as e:
        log.error("Discord notification failed: %s", e)


def run_check(config: dict, seen: set) -> set:
    new_seen = set(seen)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="de-DE",
        )
        page = context.new_page()

        for search in config["searches"]:
            url = build_url(search["keywords"], search["location"], search.get("job_type", ""))
            log.info("Checking: %s in %s", search["keywords"], search["location"])

            jobs = scrape_jobs(page, url)
            log.info("Found %d job cards", len(jobs))

            new_jobs = [j for j in jobs if j["id"] not in seen]
            if new_jobs:
                log.info("%d new jobs — sending Discord ping", len(new_jobs))
                send_discord(config["discord_webhook_url"], new_jobs, search)
                for j in new_jobs:
                    new_seen.add(j["id"])
            else:
                log.info("No new jobs")

            time.sleep(3)  # polite delay between searches

        browser.close()

    return new_seen


def main():
    config = load_config()
    if config["discord_webhook_url"] == "YOUR_DISCORD_WEBHOOK_URL":
        log.error("Set discord_webhook_url in config.json before running")
        return

    log.info("LinkedIn monitor started (interval: %d min)", config["check_interval_minutes"])
    seen = load_seen()

    while True:
        try:
            seen = run_check(config, seen)
            save_seen(seen)
        except Exception as e:
            log.error("Check failed: %s", e)

        time.sleep(config["check_interval_minutes"] * 60)


if __name__ == "__main__":
    main()
