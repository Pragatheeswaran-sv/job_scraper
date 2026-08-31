from playwright.sync_api import sync_playwright
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import re
import time
from urllib.parse import quote
import logging
from fastapi import status
from src.config import get_logger
from datetime import datetime

from sqlalchemy.orm import Session
from src.jobs.models import Job
from src.database import SessionLocal

logger = get_logger(__name__)

load_dotenv()

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY","")


SEARCH_KEYWORD = "Python"
MAX_PAGINATION_PAGES = 100
SEARCH_DEBUG_FILE = "linkedin_search_debug.html"
GROQ_MODEL = "openai/gpt-oss-120b"

if not LINKEDIN_EMAIL:
    raise ValueError("LINKEDIN_EMAIL is missing")
if not LINKEDIN_PASSWORD:
    raise ValueError("LINKEDIN_PASSWORD is missing")

GROQ_ENABLED = bool(GROQ_API_KEY)

if GROQ_ENABLED:
    client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
else:
    client = None

def clean_text(text):
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\u200c", "")
    text = text.replace("\u200d", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def normalize_posted_time(posted_text):
    if not posted_text:
        return {"value": "", "minutes_ago": None}

    original = clean_text(posted_text)
    text = original.lower().strip()

    if "just now" in text:
        return {"value": original, "minutes_ago": 0}

    match = re.search(r"(\d+)\s*(minute|minutes|hour|hours|day|days|week|weeks|month|months)", text)

    if not match:
        return {"value": original, "minutes_ago": None}

    number = int(match.group(1))
    unit = match.group(2)

    if unit in ["minute", "minutes"]:
        minutes = number
    elif unit in ["hour", "hours"]:
        minutes = number * 60
    elif unit in ["day", "days"]:
        minutes = number * 24 * 60
    elif unit in ["week", "weeks"]:
        minutes = number * 7 * 24 * 60
    elif unit in ["month", "months"]:
        minutes = number * 30 * 24 * 60
    else:
        minutes = None

    return {"value": original, "minutes_ago": minutes}

def linkedin_login(page):
    logger.info("Opening LinkedIn login...")

    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(5000)

    if "/feed" in page.url:
        logger.info("Already logged in.")
        return True

    try:
        email_input = page.locator("input[type='email']").last
        email_input.wait_for(state="visible", timeout=30000)
        email_input.fill(LINKEDIN_EMAIL)

        password_input = page.locator("input[type='password']").last
        password_input.wait_for(state="visible", timeout=30000)
        password_input.fill(LINKEDIN_PASSWORD)
        password_input.press("Enter")
        logger.info("Login submitted...")
    except Exception as e:
        logger.info(" ".join(str(value) for value in ("Primary login method failed:", e,)))

        try:
            email_input = page.locator(
                "input[autocomplete='username'], input[name='session_key'], input[type='email']"
            ).last
            email_input.wait_for(state="visible", timeout=15000)
            email_input.fill(LINKEDIN_EMAIL)

            password_input = page.locator("input[type='password']").last
            password_input.wait_for(state="visible", timeout=15000)
            password_input.fill(LINKEDIN_PASSWORD)
            password_input.press("Enter")
            logger.info("Fallback login submitted...")
        except Exception as fallback_error:
            logger.info(" ".join(str(value) for value in ("Fallback login also failed:", fallback_error,)))
            return False

    try:
        page.wait_for_url("**/feed/**", timeout=120000)
        logger.info("Login successful.")
        return True
    except Exception:
        logger.info("Feed URL was not detected.")
        logger.info(" ".join(str(value) for value in ("Current URL:", page.url,)))
        page.wait_for_timeout(15000)

        if "/feed" in page.url:
            logger.info("Login successful.")
            return True

        return False

# def build_search_url(start=0):
#     keyword = quote(SEARCH_KEYWORD)
#     location = quote(SEARCH_LOCATION)

#     return (
#         "https://www.linkedin.com/jobs/search/"
#         f"?keywords={keyword}"
#         f"&location={location}"
#         "&f_TPR=r86400"
#         "&f_WT=2"
#         f"&start={start}"
#     )

def build_search_url(start, search_location):
    keyword = quote(SEARCH_KEYWORD)

    url = (
        "https://www.linkedin.com/jobs/search/"
        f"?keywords={keyword}"
        "&f_TPR=r86400"
        "&f_WT=2"
        f"&start={start}"
    )

    if search_location:
        url += f"&location={quote(search_location)}"

    return url

def open_job_search(page, search_location):
    search_url = build_search_url(0, search_location)

    logger.info("Opening LinkedIn job search...")
    logger.info(" ".join(str(value) for value in ("Keyword:", SEARCH_KEYWORD,)))
    logger.info(" ".join(str(value) for value in ("Location:", search_location,)))
    logger.info(" ".join(str(value) for value in ("Search URL:", search_url,)))

    page.goto(search_url, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(8000)

    logger.info(" ".join(str(value) for value in ("Current URL:", page.url,)))

def get_total_result_count(page):
    try:
        body_text = page.locator("body").inner_text(timeout=15000)
        body_text = clean_text(body_text)

        patterns = [
            r"([\d,]+)\s*\+?\s+results?",
            r"([\d,]+)\s*\+?\s+jobs?",
            r"([\d,]+)\s*\+?\s+job\s+results?",
            r"([\d,]+)\s*\+?\s+search\s+results?"
        ]

        numbers = []

        for pattern in patterns:
            matches = re.findall(pattern, body_text, flags=re.IGNORECASE)

            for value in matches:
                try:
                    numbers.append(int(value.replace(",", "")))
                except Exception:
                    pass

        if numbers:
            total = max(numbers)
            logger.info(" ".join(str(value) for value in ("Total matching jobs:", total,)))
            return total

    except Exception as e:
        logger.info(" ".join(str(value) for value in ("Result count error:", e,)))

    return None

def save_search_debug(page):
    try:
        html = page.content()

        with open(SEARCH_DEBUG_FILE, "w", encoding="utf-8") as file:
            file.write(html)

        logger.info(f"Saved {SEARCH_DEBUG_FILE}")
    except Exception as e:
        logger.info(" ".join(str(value) for value in ("Could not save search HTML:", e,)))

def extract_job_id_from_url(job_url):
    if not job_url:
        return None

    match = re.search(r"/jobs/view/(\d+)", job_url)

    if match:
        return match.group(1)

    return None

def get_unmatched_job_ids(db:Session, job_links):
    job_ids = []

    for job_url in job_links:
        job_id = extract_job_id_from_url(job_url)

        if job_id and job_id not in job_ids:
            job_ids.append(job_id)

    existing_ids = {
        row[0]
        for row in db.query(Job.job_url_id)
        .filter(Job.job_url_id.in_(job_ids))
        .all()
    }

    unmatched_ids = [
        job_id
        for job_id in job_ids
        if job_id not in existing_ids
    ]

    logger.info(
        "Total job IDs: %s | Existing: %s | New: %s",
        len(job_ids),
        len(existing_ids),
        len(unmatched_ids)
    )

    return unmatched_ids


def extract_job_id(href):
    if not href:
        return None

    match = re.search(r"/jobs/view/(\d+)", href)

    if match:
        return match.group(1)

    return None

def collect_job_links_from_dom(page, job_links, seen_ids, max_jobs):
    new_jobs = 0

    try:
        anchors = page.locator("a")
        count = anchors.count()

        for i in range(count):
            # if len(job_links) >= max_jobs:
            if max_jobs is not None and len(job_links) >= max_jobs:
                break

            try:
                href = anchors.nth(i).get_attribute("href")
                job_id = extract_job_id(href)

                if not job_id:
                    continue

                if job_id in seen_ids:
                    continue

                seen_ids.add(job_id)

                job_url = "https://www.linkedin.com/jobs/view/" + job_id + "/"
                job_links.append(job_url)
                new_jobs += 1
            except Exception:
                continue

    except Exception as e:
        logger.info(" ".join(str(value) for value in ("DOM job extraction error:", e,)))

    return new_jobs

def collect_job_links_from_html(page, job_links, seen_ids, max_jobs):
    new_jobs = 0

    try:
        html = page.content()
        matches = re.findall(r"/jobs/view/(\d+)", html)

        for job_id in matches:
            # if len(job_links) >= max_jobs:
            if max_jobs is not None and len(job_links) >= max_jobs:
                break

            if job_id in seen_ids:
                continue

            seen_ids.add(job_id)

            job_url = "https://www.linkedin.com/jobs/view/" + job_id + "/"
            job_links.append(job_url)
            new_jobs += 1

    except Exception as e:
        logger.info(" ".join(str(value) for value in ("HTML fallback error:", e,)))

    return new_jobs

def find_job_list_container(page):
    selectors = [
        "div.jobs-search-results-list__list",
        "div.jobs-search-results-list",
        "div.scaffold-layout__list",
        "ul.jobs-search__results-list",
        "div.jobs-search-results-list__container"
    ]

    for selector in selectors:
        try:
            elements = page.locator(selector)
            count = elements.count()

            if count == 0:
                continue

            for i in range(count):
                try:
                    element = elements.nth(i)

                    if not element.is_visible():
                        continue

                    info = element.evaluate(
                        """
                        element => ({
                            scrollHeight: element.scrollHeight,
                            clientHeight: element.clientHeight,
                            scrollTop: element.scrollTop
                        })
                        """
                    )

                    if info["scrollHeight"] > info["clientHeight"] + 100:
                        return element
                except Exception:
                    continue

            for i in range(count):
                try:
                    element = elements.nth(i)

                    if element.is_visible():
                        return element
                except Exception:
                    continue

        except Exception:
            continue

    return None

def scroll_job_list(page, job_links, seen_ids, max_jobs, scroll_round=1):
    before_count = len(job_links)

    container = find_job_list_container(page)

    if container:
        try:
            container.evaluate(
                """
                element => {
                    element.scrollTop =
                        element.scrollTop +
                        Math.max(
                            element.clientHeight * 0.8,
                            600
                        );
                }
                """
            )

            page.wait_for_timeout(2500)
        except Exception as e:
            logger.info(" ".join(str(value) for value in ("Container scrolling error:", e,)))

    try:
        page.mouse.move(400, 700)
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(2000)
    except Exception as e:
        logger.info(" ".join(str(value) for value in ("Mouse scrolling error:", e,)))

    try:
        page.evaluate(
            """
            () => {
                const selectors = [
                    'div.jobs-search-results-list__list',
                    'div.jobs-search-results-list',
                    'div.scaffold-layout__list',
                    'ul.jobs-search__results-list'
                ];

                for (const selector of selectors) {
                    const elements =
                        document.querySelectorAll(selector);

                    for (const element of elements) {
                        if (element.scrollHeight > element.clientHeight) {
                            element.scrollTop =
                                element.scrollTop +
                                Math.max(
                                    element.clientHeight * 0.8,
                                    600
                                );
                        }
                    }
                }

                window.scrollBy(0, 500);
            }
            """
        )

        page.wait_for_timeout(2500)
    except Exception as e:
        logger.info(" ".join(str(value) for value in ("JavaScript scrolling error:", e,)))

    new_jobs = collect_job_links_from_dom(page, job_links, seen_ids, max_jobs)

    # if len(job_links) < max_jobs:
    if max_jobs is None or len(job_links) < max_jobs:
        new_jobs += collect_job_links_from_html(page, job_links, seen_ids, max_jobs)

    after_count = len(job_links)

    logger.info(f"Scroll {scroll_round}: "
        f"before={before_count}, "
        f"new={new_jobs}, "
        f"total={after_count}")

    return new_jobs

def collect_all_job_links(page, search_location, max_scroll_per_page, linkedin_page_size, max_jobs):
    logger.info("Collecting job links...")

    job_links = []
    seen_ids = set()
    page_number = 1

    while ((max_jobs is None or len(job_links) < max_jobs) and page_number <= MAX_PAGINATION_PAGES):
        start = (page_number - 1) * linkedin_page_size

        logger.info(f"Pagination page {page_number}, offset {start}")

        page_url = build_search_url(start, search_location)

        try:
            page.goto(page_url, wait_until="domcontentloaded", timeout=120000)
        except Exception as e:
            logger.info(" ".join(str(value) for value in ("Pagination navigation error:", e,)))
            break

        page.wait_for_timeout(5000)

        page_start_count = len(job_links)
        no_new_count = 0

        collect_job_links_from_dom(page, job_links, seen_ids, max_jobs)

        if max_jobs is None or len(job_links) < max_jobs:
            collect_job_links_from_html(page, job_links, seen_ids, max_jobs)

        for scroll_round in range(1, max_scroll_per_page + 1):
            if max_jobs is not None and len(job_links) >= max_jobs:
                break

            before_scroll_count = len(job_links)

            scroll_job_list(
                page,
                job_links,
                seen_ids,
                max_jobs,
                scroll_round,
            )

            after_scroll_count = len(job_links)

            if after_scroll_count > before_scroll_count:
                no_new_count = 0
            else:
                no_new_count += 1

            if no_new_count >= 4:
                break

            page.wait_for_timeout(1500)

        page_jobs_found = len(job_links) - page_start_count

        logger.info(f"Page {page_number}: "
            f"{page_jobs_found} jobs, "
            f"{len(job_links)} total")

        if max_jobs is not None and len(job_links) >= max_jobs:
            break

        if page_jobs_found == 0:
            logger.info("No jobs found on pagination page. Stopping.")
            break

        page_number += 1
        page.wait_for_timeout(2000)

    logger.info(" ".join(str(value) for value in ("Unique job URLs collected:", len(job_links),)))
    logger.info(" ".join(str(value) for value in ("Pagination pages checked:", page_number,)))

    return job_links

def extract_header_from_title(page):
    result = {
        "job_title": "",
        "company": ""
    }

    try:
        title = page.title()

        if title:
            title = re.sub(
                r"\s*\|\s*LinkedIn\s*$",
                "",
                title,
                flags=re.IGNORECASE
            )

            parts = [x.strip() for x in title.split("|")]

            if len(parts) >= 2:
                result["job_title"] = parts[0]
                result["company"] = parts[1]
    except Exception:
        pass

    return result

def get_main_text(page):
    try:
        main = page.locator("main")

        if main.count() > 0:
            texts = []

            for i in range(main.count()):
                try:
                    text = main.nth(i).inner_text(timeout=10000)

                    if text:
                        texts.append(text)
                except Exception:
                    continue

            if texts:
                return clean_text(max(texts, key=len))
    except Exception as e:
        logger.info(" ".join(str(value) for value in ("Main extraction error:", e,)))

    try:
        body_text = page.locator("body").inner_text(timeout=15000)
        return clean_text(body_text)
    except Exception as e:
        logger.info(" ".join(str(value) for value in ("Body extraction error:", e,)))

    return ""

def extract_job_header(page, main_text):
    result = extract_header_from_title(page)

    title = result["job_title"]
    company = result["company"]
    location = ""
    posted = ""

    lines = [
        clean_text(line)
        for line in main_text.splitlines()
    ]

    lines = [line for line in lines if line]

    about_index = -1

    for i, line in enumerate(lines):
        if line.lower() == "about the job":
            about_index = i
            break

    header_lines = lines

    if about_index > 0:
        header_lines = lines[max(0, about_index - 20):about_index]

    if not title:
        for line in header_lines:
            if (
                len(line) > 3
                and line.lower() not in {
                    "about the job",
                    "set alert",
                    "show more",
                    "save"
                }
            ):
                lower = line.lower()

                if (
                    "ago" not in lower
                    and "remote" not in lower
                    and "easy apply" not in lower
                    and "full-time" not in lower
                    and "part-time" not in lower
                ):
                    title = line
                    break

    if not company:
        for i, line in enumerate(header_lines):
            if line == title:
                if i + 1 < len(header_lines):
                    candidate = header_lines[i + 1]

                    if candidate and "ago" not in candidate.lower():
                        company = candidate
                        break

    posted_patterns = [
        r"\b\d+\s+(?:minute|minutes|hour|hours|day|days|week|weeks|month|months)\s+ago\b",
        r"\b\d+\s+(?:minute|minutes|hour|hours|day|days|week|weeks|month|months)\b",
        r"^just now$"
    ]

    for line in header_lines:
        for pattern in posted_patterns:
            match = re.search(pattern, line, flags=re.IGNORECASE)

            if match:
                posted = match.group(0)
                break

        if posted:
            break

    location_patterns = [
        r"^(.+?)\s+\((?:Remote|Hybrid|On-site)\)$",
        r"^India\s+\((?:Remote|Hybrid|On-site)\)$",
        r"^Remote$",
        r"^Hybrid$",
        r"^On-site$"
    ]

    for line in header_lines:
        if line == title or line == company:
            continue

        for pattern in location_patterns:
            match = re.search(pattern, line, flags=re.IGNORECASE)

            if match:
                if match.groups():
                    location = clean_text(match.group(1))
                else:
                    location = clean_text(match.group(0))
                break

        if location:
            break

    posted_time = normalize_posted_time(posted)

    return {
        "job_title": clean_text(title),
        "company": clean_text(company),
        "job_location": clean_text(location),
        "posted_time": posted_time
    }

def extract_about_job_from_text(main_text):
    if not main_text:
        return ""

    lines = [
        clean_text(line)
        for line in main_text.splitlines()
    ]

    lines = [line for line in lines if line]
    start_index = None

    for i, line in enumerate(lines):
        normalized = line.lower().strip()

        if normalized == "about the job":
            start_index = i + 1
            break

        if normalized.startswith("about the job"):
            start_index = i + 1
            break

    if start_index is None:
        return ""

    lines = lines[start_index:]

    stop_patterns = [
        r"^set alert$",
        r"^set alert for similar jobs$",
        r"^more jobs$",
        r"^see more jobs like this$",
        r"^job search faster with premium$",
        r"^job search smarter with premium$",
        r"^access company insights",
        r"^backfilling a role\??$",
        r"^post a job$",
        r"^about$",
        r"^accessibility$",
        r"^talent solutions$",
        r"^community guidelines$",
        r"^careers$",
        r"^marketing solutions$",
        r"^privacy & terms$",
        r"^ad choices$",
        r"^advertising$",
        r"^sales solutions$",
        r"^mobile$",
        r"^small business$",
        r"^safety center$",
        r"^linkedin corporation",
        r"^questions\??$",
        r"^visit our help center$",
        r"^manage your account",
        r"^go to your settings$",
        r"^recommendation transparency$",
        r"^select language$",
        r"^people you can reach out to$"
    ]

    result_lines = []

    for line in lines:
        normalized = line.lower().strip()

        if normalized in {"… more", "... more", "…more", "...more"}:
            break

        should_stop = False

        for pattern in stop_patterns:
            if re.search(pattern, normalized, flags=re.IGNORECASE):
                should_stop = True
                break

        if should_stop:
            break

        result_lines.append(line)

    return clean_text("\n".join(result_lines))

def extract_about_job_from_dom(page):
    selectors = [
        "div.jobs-description-content__text",
        "div.jobs-box__html-content",
        "div.jobs-description__content",
        "section.jobs-description",
        "div.jobs-description",
        "article.jobs-description",
        "[class*='jobs-description-content']",
        "[class*='jobs-description']"
    ]

    candidates = []

    for selector in selectors:
        try:
            elements = page.locator(selector)
            count = elements.count()

            for i in range(count):
                try:
                    text = elements.nth(i).inner_text(timeout=5000)
                    text = clean_text(text)

                    if len(text) > 100:
                        candidates.append(text)
                except Exception:
                    continue
        except Exception:
            continue

    if candidates:
        best = max(candidates, key=len)
        return extract_about_job_from_text("About the job\n" + best)

    return ""

def extract_about_job(page, main_text):
    result = extract_about_job_from_text(main_text)

    if len(result) >= 100:
        return result

    result = extract_about_job_from_dom(page)

    if result:
        return result

    return ""

def extract_people_you_can_reach_out(main_text):
    if not main_text:
        return ""

    lines = [
        clean_text(line)
        for line in main_text.splitlines()
    ]

    lines = [line for line in lines if line]
    start_index = None

    for i, line in enumerate(lines):
        normalized = line.lower().strip()

        if normalized == "people you can reach out to":
            start_index = i + 1
            break

    if start_index is None:
        return ""

    result_lines = []

    stop_patterns = [
        r"^more jobs$",
        r"^see more jobs like this$",
        r"^job search faster with premium$",
        r"^job search smarter with premium$",
        r"^access company insights",
        r"^backfilling a role\??$",
        r"^post a job$",
        r"^about$",
        r"^accessibility$",
        r"^talent solutions$",
        r"^community guidelines$",
        r"^careers$",
        r"^marketing solutions$",
        r"^privacy & terms$",
        r"^ad choices$",
        r"^advertising$",
        r"^sales solutions$",
        r"^mobile$",
        r"^small business$",
        r"^safety center$",
        r"^linkedin corporation",
        r"^questions\??$",
        r"^visit our help center$",
        r"^manage your account",
        r"^go to your settings$",
        r"^recommendation transparency$",
        r"^select language$"
    ]

    for line in lines[start_index:]:
        normalized = line.lower().strip()

        if normalized in {"… more", "... more", "…more", "...more"}:
            break

        should_stop = False

        for pattern in stop_patterns:
            if re.search(pattern, normalized, flags=re.IGNORECASE):
                should_stop = True
                break

        if should_stop:
            break

        result_lines.append(line)

    return clean_text("\n".join(result_lines))

def save_filtered_text(run_id, index, header, about_text, people_text):

    os.makedirs(f"logs/{run_id}", exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"logs/{run_id}/{index}_{timestamp}.txt"
    parts = []

    parts.append("JOB TITLE:\n" + header.get("job_title", ""))
    parts.append("COMPANY:\n" + header.get("company", ""))
    parts.append("JOB LOCATION:\n" + header.get("job_location", ""))

    posted_time = header.get("posted_time", {})

    parts.append(
        "POSTED TIME:\n" +
        posted_time.get("value", "")
    )

    parts.append("ABOUT THE JOB:\n" + about_text)

    if people_text:
        parts.append(
            "PEOPLE YOU CAN REACH OUT TO:\n" +
            people_text
        )

    result = "\n\n".join(parts)

    try:
        with open(filename, "w", encoding="utf-8") as file:
            file.write(result)

        logger.info(f"Saved filtered text: {filename}")
    except Exception as e:
        filename = None
        logger.info(" ".join(str(value) for value in ("Filtered text save error:", e,)))

    return result, filename

def extract_job_with_groq(filtered_text, linkedin_url):
    if not GROQ_ENABLED:
        return ""

    if not filtered_text:
        return ""

    if len(filtered_text.strip()) < 100:
        return ""

    prompt = f"""
Extract structured job information from the supplied LinkedIn job text.

Return ONLY valid JSON.

Schema:

{{
    "job_title": "",
    "company": "",
    "company_location": "",
    "job_location": "",
    "job_description": "",
    "responsibilities": [],
    "qualifications": [],
    "required_skills": [],
    "preferred_skills": [],
    "experience_required": {{
        "min_exp": null,
        "max_exp": null,
        "unit": "years"
    }},
    "education_required": "",
    "employment_type": "",
    "work_type": "",
    "salary": {{
        "min_sal": null,
        "max_sal": null,
        "currency": "",
        "payment_period": null
    }},
    "company_information": "",
    "posted_by": {{
        "name": "",
        "title": "",
        "linkedin_url": ""
    }},
    "recommended_contacts": [],
    "linkedin_job_url": "{linkedin_url}"
}}

IMPORTANT RULES:

- Use ONLY information present in supplied text.
- Do not guess or invent information.
- Missing strings must be "".
- Missing arrays must be [].
- Missing numeric values must be null.
- Return valid JSON only.
- Do not add markdown.
- Do not add explanations.

JOB DESCRIPTION:

Create a concise but complete description based only on About the Job.

RESPONSIBILITIES:

Extract actual responsibilities.

QUALIFICATIONS:

Extract actual candidate qualifications.

REQUIRED SKILLS:

Extract only actual skills, technologies, programming languages,
frameworks, libraries, databases, platforms, tools, methodologies,
or domain names.

PREFERRED SKILLS:

Extract only actual skills, technologies, programming languages,
frameworks, libraries, databases, platforms, tools, methodologies,
or domain names.

EXPERIENCE:

Normalize experience into:

"experience_required": {{
    "min_exp": number or null,
    "max_exp": number or null,
    "unit": "years"
}}

Examples:

"2-5 years"
=> min 2, max 5

"2+ years"
=> min 2, max null

"minimum 3 years"
=> min 3, max null

"1 year"
=> min 1, max 1

"freshers"
=> min 0, max 0

SALARY:

Normalize salary into:

"salary": {{
    "min_sal": number or null,
    "max_sal": number or null,
    "currency": "",
    "payment_period": null
}}

Currency:

₹ or Rs or INR => INR
$ or USD => USD
€ or EUR => EUR
£ or GBP => GBP

Payment period:

hour
day
week
month
year

or null.

POSTED TIME:

Do not calculate or modify posted time.

PEOPLE YOU CAN REACH OUT TO:

Extract only actual people explicitly present.

For posted_by:

- Populate only when explicitly identified.
- Do not use "Meet the hiring team" as a person's name.
- Do not invent LinkedIn URLs.

Recommended contacts format:

{{
    "name": "",
    "title": "",
    "company": "",
    "linkedin_url": "",
    "reason": ""
}}

Do not invent people.

COMPANY LOCATION:

Extract only if explicitly available.

JOB LOCATION:

Extract actual job location.

EMPLOYMENT TYPE:

Extract Full-time, Part-time, Contract, Internship, etc.

WORK TYPE:

Extract Remote, Hybrid, or On-site.

JOB TEXT:

{filtered_text}
"""

    try:
        response = client.responses.create(
            model=GROQ_MODEL,
            input=prompt
        )

        return response.output_text
    except Exception as e:
        logger.info(" ".join(str(value) for value in ("Groq API error:", e,)))
        return ""

def parse_groq_response(response, url, header):
    if not response:
        return None

    response = response.strip()

    if response.startswith("```"):
        response = re.sub(
            r"^```(?:json)?",
            "",
            response,
            flags=re.IGNORECASE
        )

        response = re.sub(r"```$", "", response)
        response = response.strip()

    try:
        data = json.loads(response)
    except Exception as e:
        logger.info(" ".join(str(value) for value in ("JSON parsing error:", e,)))
        logger.info(" ".join(str(value) for value in ("Raw Groq response:", response,)))
        return None

    defaults = {
        "job_title": "",
        "company": "",
        "company_location": "",
        "job_location": "",
        "job_description": "",
        "responsibilities": [],
        "qualifications": [],
        "required_skills": [],
        "preferred_skills": [],
        "experience_required": {
            "min_exp": None,
            "max_exp": None,
            "unit": "years"
        },
        "education_required": "",
        "employment_type": "",
        "work_type": "",
        "salary": {
            "min_sal": None,
            "max_sal": None,
            "currency": "",
            "payment_period": None
        },
        "company_information": "",
        "posted_by": {
            "name": "",
            "title": "",
            "linkedin_url": ""
        },
        "recommended_contacts": [],
        "linkedin_job_url": url
    }

    for key, default in defaults.items():
        if key not in data:
            data[key] = default

    for field in ["job_title", "company", "job_location"]:
        if not data.get(field):
            data[field] = header.get(field, "")

    array_fields = [
        "responsibilities",
        "qualifications",
        "required_skills",
        "preferred_skills"
    ]

    for field in array_fields:
        value = data.get(field, [])
        cleaned = []

        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    item = clean_text(item)

                    if item:
                        cleaned.append(item)

                elif isinstance(item, dict):
                    text = clean_text(str(item.get("text", "")))

                    if text:
                        cleaned.append(text)

        data[field] = cleaned

    string_fields = [
        "job_title",
        "company",
        "company_location",
        "job_location",
        "job_description",
        "education_required",
        "employment_type",
        "work_type",
        "company_information"
    ]

    for field in string_fields:
        value = data.get(field, "")

        if value is None:
            value = ""

        if not isinstance(value, str):
            value = str(value)

        data[field] = clean_text(value)

    experience = data.get("experience_required", {})

    if not isinstance(experience, dict):
        experience = {}

    min_exp = experience.get("min_exp")
    max_exp = experience.get("max_exp")

    try:
        if min_exp is not None:
            min_exp = float(min_exp)

            if min_exp.is_integer():
                min_exp = int(min_exp)
    except Exception:
        min_exp = None

    try:
        if max_exp is not None:
            max_exp = float(max_exp)

            if max_exp.is_integer():
                max_exp = int(max_exp)
    except Exception:
        max_exp = None

    data["experience_required"] = {
        "min_exp": min_exp,
        "max_exp": max_exp,
        "unit": "years"
    }

    salary = data.get("salary", {})

    if not isinstance(salary, dict):
        salary = {}

    min_sal = salary.get("min_sal")
    max_sal = salary.get("max_sal")

    try:
        if min_sal is not None:
            min_sal = float(min_sal)

            if min_sal.is_integer():
                min_sal = int(min_sal)
    except Exception:
        min_sal = None

    try:
        if max_sal is not None:
            max_sal = float(max_sal)

            if max_sal.is_integer():
                max_sal = int(max_sal)
    except Exception:
        max_sal = None

    currency = clean_text(
        str(salary.get("currency", "") or "")
    ).upper()

    payment_period = salary.get("payment_period")

    if payment_period:
        payment_period = clean_text(
            str(payment_period)
        ).lower()

    allowed_periods = {
        "hour",
        "day",
        "week",
        "month",
        "year"
    }

    if payment_period not in allowed_periods:
        payment_period = None

    data["salary"] = {
        "min_sal": min_sal,
        "max_sal": max_sal,
        "currency": currency,
        "payment_period": payment_period
    }

    posted_by = data.get("posted_by", {})

    if not isinstance(posted_by, dict):
        posted_by = {}

    data["posted_by"] = {
        "name": clean_text(
            str(posted_by.get("name", "") or "")
        ),
        "title": clean_text(
            str(posted_by.get("title", "") or "")
        ),
        "linkedin_url": clean_text(
            str(posted_by.get("linkedin_url", "") or "")
        )
    }

    if data["posted_by"]["name"].lower() in {
        "meet the hiring team",
        "hiring team"
    }:
        data["posted_by"] = {
            "name": "",
            "title": "",
            "linkedin_url": ""
        }

    contacts = data.get("recommended_contacts", [])
    cleaned_contacts = []

    if isinstance(contacts, list):
        for contact in contacts:
            if not isinstance(contact, dict):
                continue

            name = clean_text(
                str(contact.get("name", "") or "")
            )

            if not name:
                continue

            if name.lower() in {
                "meet the hiring team",
                "hiring team"
            }:
                continue

            cleaned_contacts.append({
                "name": name,
                "title": clean_text(
                    str(contact.get("title", "") or "")
                ),
                "company": clean_text(
                    str(contact.get("company", "") or "")
                ),
                "linkedin_url": clean_text(
                    str(contact.get("linkedin_url", "") or "")
                ),
                "reason": clean_text(
                    str(contact.get("reason", "") or "")
                )
            })

    data["recommended_contacts"] = cleaned_contacts
    data["linkedin_job_url"] = url
    data["posted_time"] = header.get(
        "posted_time",
        {
            "value": "",
            "minutes_ago": None
        }
    )

    return data

def process_job(page, url, run_id, index, job_id):
    logger.info(f"Processing job {index}: {url}")

    try:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=120000
        )
    except Exception as e:
        logger.info(" ".join(str(value) for value in ("Navigation error:", e,)))
        return None

    page.wait_for_timeout(7000)

    main_text = get_main_text(page)

    if not main_text:
        logger.info("Could not extract page text.")
        return None

    header = extract_job_header(page, main_text)
    about_text = extract_about_job(page, main_text)
    people_text = extract_people_you_can_reach_out(main_text)

    filtered_text, raw_file_path  = save_filtered_text(
        run_id,
        index,
        header,
        about_text,
        people_text
    )

    if len(about_text.strip()) < 100:
        logger.info("About the Job section was not extracted.")
        return None

    if not GROQ_ENABLED:
        return {
            "job_id": job_id,
            "job_title": header["job_title"],
            "company": header["company"],
            "company_location": "",
            "job_location": header["job_location"],
            "job_description": about_text,
            "responsibilities": [],
            "qualifications": [],
            "required_skills": [],
            "preferred_skills": [],
            "experience_required": {
                "min_exp": None,
                "max_exp": None,
                "unit": "years"
            },
            "education_required": "",
            "employment_type": "",
            "work_type": "",
            "salary": {
                "min_sal": None,
                "max_sal": None,
                "currency": "",
                "payment_period": None
            },
            "company_information": "",
            "posted_by": {
                "name": "",
                "title": "",
                "linkedin_url": ""
            },
            "recommended_contacts": [],
            "linkedin_job_url": url,
            "posted_time": header["posted_time"]
        }

    groq_response = extract_job_with_groq(
        filtered_text,
        url
    )

    if not groq_response:
        logger.info("Groq returned no response.")
        return None

    result = parse_groq_response(
        groq_response,
        url,
        header
    )

    if job_id: 
        result['job_url_id'] = job_id
 
    #replace about the job
    if result['job_description']:
        result['job_description'] = about_text

    if not result:
        return None

    result["_raw_file_path"] = raw_file_path

    logger.info(f"Extracted: {result['job_title']} | "
        f"{result['company']}")

    return result

def scrape_linkedin_jobs(
    run_id: str,
    search_keyword: str = SEARCH_KEYWORD,
    search_location: str = "",
    max_jobs: int = None,
    max_pagination_pages: int = MAX_PAGINATION_PAGES,
    linkedin_page_size: int = 25,
    max_scrolls_per_page: int = 20
):
    global SEARCH_KEYWORD
    global MAX_PAGINATION_PAGES

    db = SessionLocal()

    try:
        if not search_keyword:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": "Search keyword is required"
            }

        # if not search_location:
        #     return {
        #         "status_code": status.HTTP_400_BAD_REQUEST,
        #         "message": "Search location is required"
        #     }

        if max_jobs is not None and max_jobs <= 0:
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": "max_jobs must be greater than 0"
            }

        logger.info(
            "Starting LinkedIn scraper: keyword=%s, location=%s, max_jobs=%s",
            search_keyword,
            search_location,
            max_jobs
        )

        SEARCH_KEYWORD = search_keyword
        MAX_PAGINATION_PAGES = max_pagination_pages

        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                slow_mo=300
            )

            context = browser.new_context(
                viewport={
                    "width": 1440,
                    "height": 900
                }
            )

            page = context.new_page()

            try:
                if not linkedin_login(page):
                    logger.error("LinkedIn login failed")
                    return {
                        "status_code": status.HTTP_401_UNAUTHORIZED,
                        "message": "LinkedIn login failed"
                    }

                open_job_search(page, search_location)
                page.wait_for_timeout(5000)

                total_matching_jobs = get_total_result_count(page)
                job_links = collect_all_job_links(page, search_location, max_scrolls_per_page, linkedin_page_size, max_jobs)
                job_ids = get_unmatched_job_ids(db, job_links)
                job_id_to_url = {
                    extract_job_id_from_url(url): url
                    for url in job_links
                }

                # save_search_debug(page)

                if not job_links:
                    logger.info("No jobs found")
                    return {
                        "status_code": status.HTTP_404_NOT_FOUND,
                        "message": "No jobs found for the given search criteria",
                        "data": {
                            "keyword": search_keyword,
                            "location": search_location,
                            "total_matching_jobs": total_matching_jobs,
                            "job_urls_collected": 0,
                            "jobs_processed": 0
                        }
                    }

                logger.info(
                    "LinkedIn reported=%s, collected=%s",
                    total_matching_jobs,
                    len(job_links)
                )

                for index, job_id in enumerate(job_ids, start=1):
                    url = job_id_to_url.get(job_id)
                    try:
                        result = process_job(page, url, run_id, index, job_id)

                        if result:
                            results.append(result)

                    except Exception as e:
                        logger.error(
                            "Error processing job %s: %s",
                            index,
                            e
                        )

                    time.sleep(3)

                output = {
                    "search_summary": {
                        "keyword": search_keyword,
                        "location": search_location,
                        "posted_within": "24 hours",
                        "workplace": "Remote",
                        "total_matching_jobs": total_matching_jobs,
                        "job_urls_collected": len(job_links),
                        "jobs_processed": len(results),
                        "max_jobs": max_jobs,
                        "max_pagination_pages": max_pagination_pages,
                        "linkedin_page_size": linkedin_page_size
                    },
                    "jobs": results
                }

                logger.info(
                    "LinkedIn scraping completed: collected=%s, processed=%s",
                    len(job_links),
                    len(results)
                )
                logger.info('Output Json: %s', output)

                return {
                    "status_code": status.HTTP_200_OK,
                    "message": "LinkedIn jobs scraped successfully",
                    "data": output
                }

            finally:
                browser.close()
                logger.info("LinkedIn browser closed")

    except Exception as e:
        logger.exception("ERROR in scrape_linkedin_jobs function")
        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "Error while scraping LinkedIn jobs",
            "error": str(e)
        }