#!/usr/bin/env python3
"""
Complete Flask web app for Competitor Web UI UX Analysis - Step 3
"""

import json
import re
import time
import traceback
from typing import Dict, List, Optional, Generator
from bs4 import BeautifulSoup

from flask import Flask, render_template, request, Response, stream_with_context
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

RATEMYSITE_URL = "https://www.ratemysite.xyz/"
DEFAULT_TIMEOUT = 45

def _find_first(driver, xpaths: List[str]) -> Optional[object]:
    for xp in xpaths:
        try:
            el = driver.find_element(By.XPATH, xp)
            if el and el.is_displayed():
                return el
        except (NoSuchElementException, StaleElementReferenceException):
            continue
    return None

def _click_best_button(driver) -> bool:
    xpaths = [
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'analy')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'rate')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'submit')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'generate')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'get report')]",
        "//button[@type='submit']",
        "//button",
        "//div[@role='button']",
    ]
    btn = _find_first(driver, xpaths)
    if not btn:
        return False
    try:
        if btn.is_enabled():
            try:
                btn.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", btn)
            return True
    except Exception:
        pass
    return False

def _maybe_close_cookie_banner(driver):
    candidates = [
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'accept')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'agree')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'allow')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'ok')]",
        "//*[contains(@class,'cookie')]//button",
        "//*[@id='onetrust-accept-btn-handler']",
    ]
    try:
        btn = _find_first(driver, candidates)
        if btn:
            try:
                btn.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", btn)
            time.sleep(0.3)
    except Exception:
        pass

def _collect_result_html(driver) -> str:
    """Get the full HTML of the page for better parsing"""
    try:
        return driver.page_source
    except Exception:
        return ""

def _collect_result_text(driver) -> str:
    containers = driver.find_elements(
        By.XPATH,
        "//*[contains(@class,'result') or contains(@class,'report') or contains(@class,'output') or @role='article']",
    )
    texts = [c.text.strip() for c in containers if c.text and c.text.strip()]
    if texts:
        return "\n\n".join(texts).strip()
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        return (body.text or "").strip()
    except Exception:
        return ""

def _wait_for_content_growth(driver, wait: WebDriverWait, min_growth: int = 80) -> None:
    try:
        initial_len = len(driver.find_element(By.TAG_NAME, "body").text)
    except Exception:
        initial_len = 0
    try:
        wait.until(lambda d: len(d.find_element(By.TAG_NAME, "body").text) > initial_len + min_growth)
    except TimeoutException:
        pass

def _make_driver(headless: bool = True) -> webdriver.Chrome:
    chrome_opts = Options()
    if headless:
        chrome_opts.add_argument("--headless=new")
        chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--window-size=1920,1080")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_opts)

def _analyze_one_with_debugging(target_url: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[str, List[str]]:
    debug_log = []
    driver = _make_driver(headless=True)
    wait = WebDriverWait(driver, timeout)
    
    try:
        debug_log.append("Creating fresh Chrome driver...")
        debug_log.append(f"Navigating to {RATEMYSITE_URL}")
        driver.get(RATEMYSITE_URL)
        
        debug_log.append("Checking for cookie banners...")
        _maybe_close_cookie_banner(driver)

        input_xpaths = [
            "//input[@type='text']",
            "//input[@placeholder]",
            "//input",
            "//textarea",
        ]
        
        debug_log.append("Looking for input field...")
        try:
            input_el = wait.until(EC.presence_of_element_located((By.XPATH, "|".join(input_xpaths))))
            debug_log.append("Found input field using wait condition")
        except Exception as e:
            debug_log.append(f"Wait condition failed: {e}")
            input_el = _find_first(driver, input_xpaths)
            if input_el:
                debug_log.append("Found input field using fallback method")
            
        if not input_el:
            debug_log.append("ERROR: Could not locate input field!")
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text[:500]
                debug_log.append(f"Body text: {body_text}")
            except Exception as e:
                debug_log.append(f"Could not get body text: {e}")
            return "", debug_log

        debug_log.append(f"Entering URL: {target_url}")
        try:
            input_el.clear()
        except Exception:
            pass
        input_el.send_keys(target_url)
        time.sleep(0.3)

        debug_log.append("Attempting to submit...")
        clicked = _click_best_button(driver)
        if clicked:
            debug_log.append("Successfully clicked submit button")
        else:
            debug_log.append("Button click failed, trying Enter key...")
            try:
                input_el.send_keys("\n")
                debug_log.append("Sent Enter key")
            except Exception as e:
                debug_log.append(f"Enter key failed: {e}")

        debug_log.append("Waiting for results to load...")
        # Wait for the overall score to appear
        try:
            wait.until(
                EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Overall Score')]"))
            )
            debug_log.append("Found Overall Score element")
        except TimeoutException:
            debug_log.append("Overall Score not found, waiting for general content...")
            time.sleep(5)

        # Wait a bit more for all content to load
        time.sleep(3)
        debug_log.append("Extracting result HTML...")
        result_html = _collect_result_html(driver)
        debug_log.append(f"Extracted {len(result_html)} characters of HTML")
        
        return result_html, debug_log

    except Exception as e:
        debug_log.append(f"ERROR in analysis: {e}")
        debug_log.append(f"Traceback: {traceback.format_exc()}")
        return "", debug_log
    finally:
        debug_log.append("Closing driver...")
        driver.quit()

def _clean_text(text: str) -> str:
    """Clean text while preserving meaningful structure"""
    if not text or text == "-":
        return "-"
    
    # Remove extra whitespace but preserve line structure
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove unwanted characters but keep punctuation
    text = re.sub(r'[^\w\s\.,;:()!?\-\'\"\/&]', '', text)
    
    return text.strip()

def _parse_ratemysite_html(html: str, url: str) -> Dict[str, str]:
    """Parse RateMySite HTML structure to extract scores and descriptions"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract domain for company name  
    company_name = url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    
    result = {
        "Company": company_name,
        "URL": url,
        "Overall Score": "-",
        "Description of Website": "-",
        
        # Audience Perspective
        "Consumer Score": "-",
        "Consumer Score Description": "-",
        "Developer Score": "-",
        "Developer Score Description": "-",
        "Investor Score": "-",
        "Investor Score Description": "-",
        
        # Technical Criteria
        "Clarity Score": "-",
        "Clarity Score Description": "-",
        "Visual Design Score": "-",
        "Visual Design Score Description": "-",
        "UX Score": "-",
        "UX Score Description": "-",
        "Trust Score": "-",
        "Trust Score Description": "-",
        "Value Prop Score": "-",
        "Value Prop Score Description": "-",
    }
    
    try:
        # Extract Overall Score
        overall_score_elem = soup.find('span', class_='text-5xl')
        if overall_score_elem:
            score_text = overall_score_elem.get_text(strip=True)
            if re.match(r'^\d+\.?\d*$', score_text):
                result["Overall Score"] = score_text
        
        # Extract main description
        desc_elem = soup.find('p', class_='text-xl text-white')
        if desc_elem:
            result["Description of Website"] = _clean_text(desc_elem.get_text(strip=True))
        
        # Extract Audience Perspective scores and descriptions
        audience_section = soup.find('h2', string='Audience Perspective')
        if audience_section:
            audience_container = audience_section.find_next('div', class_='grid')
            if audience_container:
                audience_cards = audience_container.find_all('div', recursive=False)
                
                for card in audience_cards:
                    # Find the title (Consumer, Developer, Investor)
                    title_elem = card.find('h3')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # Find the score
                    score_elem = card.find('span', class_='text-2xl')
                    score = score_elem.get_text(strip=True) if score_elem else "-"
                    
                    # Find the description
                    desc_elem = card.find('p', class_='text-gray-300')
                    description = _clean_text(desc_elem.get_text(strip=True)) if desc_elem else "-"
                    
                    if title == "Consumer":
                        result["Consumer Score"] = score
                        result["Consumer Score Description"] = description
                    elif title == "Developer":
                        result["Developer Score"] = score
                        result["Developer Score Description"] = description
                    elif title == "Investor":
                        result["Investor Score"] = score
                        result["Investor Score Description"] = description
        
        # Extract Technical Criteria scores and descriptions
        tech_section = soup.find('h2', string='Technical Criteria Scores')
        if tech_section:
            # Find the grid container after the radar chart
            tech_container = tech_section.find_next('div', class_='grid')
            if tech_container:
                tech_cards = tech_container.find_all('div', class_='p-6')
                
                for card in tech_cards:
                    # Find the title
                    title_elem = card.find('h3')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # Find the score
                    score_elem = card.find('span', class_='text-2xl')
                    score = score_elem.get_text(strip=True) if score_elem else "-"
                    
                    # Find the description
                    desc_elem = card.find('p', class_='text-gray-300')
                    description = _clean_text(desc_elem.get_text(strip=True)) if desc_elem else "-"
                    
                    if title == "Clarity":
                        result["Clarity Score"] = score
                        result["Clarity Score Description"] = description
                    elif title == "Visual Design":
                        result["Visual Design Score"] = score
                        result["Visual Design Score Description"] = description
                    elif title == "UX":
                        result["UX Score"] = score
                        result["UX Score Description"] = description
                    elif title == "Trust":
                        result["Trust Score"] = score
                        result["Trust Score Description"] = description
                    elif title == "Value Proposition":
                        result["Value Prop Score"] = score
                        result["Value Prop Score Description"] = description
        
    except Exception as e:
        print(f"Error parsing HTML: {e}")
    
    return result

app = Flask(__name__)

TABLE_ROWS = [
    ("Company", "Company"),
    ("URL", "URL"),
    ("Overall Score", "Overall Score"),
    ("Description of Website", "Description of Website"),
    
    # Audience Perspective
    ("Consumer Score", "Consumer Score"),
    ("Consumer Score Description", "Consumer Score Description"),
    ("Developer Score", "Developer Score"),
    ("Developer Score Description", "Developer Score Description"),
    ("Investor Score", "Investor Score"),
    ("Investor Score Description", "Investor Score Description"),
    
    # Technical Criteria
    ("Clarity Score", "Clarity Score"),
    ("Clarity Score Description", "Clarity Score Description"),
    ("Visual Design Score", "Visual Design Score"),
    ("Visual Design Score Description", "Visual Design Score Description"),
    ("UX Score", "UX Score"),
    ("UX Score Description", "UX Score Description"),
    ("Trust Score", "Trust Score"),
    ("Trust Score Description", "Trust Score Description"),
    ("Value Prop Score", "Value Prop Score"),
    ("Value Prop Score Description", "Value Prop Score Description"),
]

def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

def stream_analysis(urls: List[str]) -> Generator[str, None, None]:
    total = len(urls)
    yield sse("init", {"total": total, "rows": TABLE_ROWS})

    for idx, raw in enumerate(urls, start=1):
        url = raw if raw.startswith(("http://", "https://")) else "https://" + raw
        step_total = 5
        cur = 0

        print(f"[{idx}/{total}] Start {url}")
        yield sse("start_url", {"index": idx, "url": url})

        cur += 1
        yield sse("progress", {"index": idx, "phase": "Creating fresh browser", "p": cur, "of": step_total})

        cur += 1
        yield sse("progress", {"index": idx, "phase": "Submitting to RateMySite", "p": cur, "of": step_total})
        
        raw_html, debug_messages = _analyze_one_with_debugging(url, timeout=DEFAULT_TIMEOUT)
        
        for msg in debug_messages:
            yield sse("debug", {"index": idx, "message": msg})

        cur += 1
        yield sse("progress", {"index": idx, "phase": "Parsing output", "p": cur, "of": step_total})
        
        if raw_html:
            data = _parse_ratemysite_html(raw_html, url)
            yield sse("result", {"index": idx, "url": url, "data": data})
        else:
            yield sse("result", {"index": idx, "url": url, "error": "No results found - check debug log"})

        cur += 1
        yield sse("progress", {"index": idx, "phase": "Done", "p": cur, "of": step_total})
        print(f"[{idx}/{total}] Done {url}")

    yield sse("done", {"ok": True})

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/stream")
def stream():
    urls = [u.strip() for u in request.args.getlist("u") if u.strip()]
    if not urls:
        return Response("Need at least one ?u=", status=400)
    return Response(stream_with_context(stream_analysis(urls)), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000, threaded=True)