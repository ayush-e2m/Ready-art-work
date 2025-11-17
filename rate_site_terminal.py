#!/usr/bin/env python3
"""
Usage:
    python rate_site_terminal.py <target-site-url> [--no-headless]

What it does:
 - Opens https://www.ratemysite.xyz/
 - Enters the URL you pass on the command line
 - Submits the analysis
 - Waits for the result UI to render
 - Prints the visible result text to the terminal

Notes:
 - Uses Selenium + Chrome in (default) headless mode
 - Uses webdriver-manager to auto-install the matching ChromeDriver
"""

import sys
import time
import argparse
from typing import Optional, List

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
        except NoSuchElementException:
            continue
        except StaleElementReferenceException:
            continue
    return None


def _click_best_button(driver) -> bool:
    """
    Try a few likely button texts/selectors to start the analysis.
    """
    xpaths = [
        # likely action labels
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'analy')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'rate')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'submit')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'generate')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'get report')]",
        # generic fallbacks
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
    """
    Try to dismiss common cookie/consent banners so clicks aren't blocked.
    Best-effort; safe to ignore failures.
    """
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


def _collect_result_text(driver) -> str:
    """
    Try to extract meaningful result text from typical containers.
    Fallback to the whole body text if needed.
    """
    containers = driver.find_elements(
        By.XPATH,
        "//*[contains(@class,'result') or contains(@class,'report') or contains(@class,'output') or @role='article']",
    )
    texts = [c.text.strip() for c in containers if c.text and c.text.strip()]
    if texts:
        return "\n\n".join(texts).strip()

    # fallback: visible body text
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        return (body.text or "").strip()
    except Exception:
        return ""


def _wait_for_content_growth(driver, wait: WebDriverWait, min_growth: int = 80) -> None:
    """
    Heuristic: wait until the visible body text length grows (JS rendered).
    """
    try:
        initial_len = len(driver.find_element(By.TAG_NAME, "body").text)
    except Exception:
        initial_len = 0

    try:
        wait.until(lambda d: len(d.find_element(By.TAG_NAME, "body").text) > initial_len + min_growth)
    except TimeoutException:
        pass


def run(target_url: str, headless: bool = True, timeout: int = DEFAULT_TIMEOUT):
    # --- Browser setup ---
    chrome_opts = Options()
    if headless:
        chrome_opts.add_argument("--headless=new")
        chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--window-size=1920,1080")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_opts)
    wait = WebDriverWait(driver, timeout)

    try:
        driver.get(RATEMYSITE_URL)

        _maybe_close_cookie_banner(driver)

        # --- Find URL input ---
        input_xpaths = [
            "//input[@type='url']",
            "//input[contains(@placeholder,'https')]",
            "//input[contains(@placeholder,'http')]",
            "//input[contains(@placeholder,'Enter') or contains(@placeholder,'enter')]",
            "//input",
            "//textarea",
        ]
        try:
            input_el = wait.until(EC.presence_of_element_located((By.XPATH, "|".join(input_xpaths))))
        except Exception:
            input_el = _find_first(driver, input_xpaths)

        if not input_el:
            print("[!] Could not locate an input field on the page. Printing current page text:\n")
            print(driver.find_element(By.TAG_NAME, "body").text)
            return

        # --- Enter target URL ---
        try:
            input_el.clear()
        except Exception:
            pass
        input_el.send_keys(target_url)
        time.sleep(0.3)

        # --- Submit (button or Enter) ---
        clicked = _click_best_button(driver)
        if not clicked:
            try:
                input_el.send_keys("\n")
            except Exception:
                pass

        # --- Wait for results to render ---
        # Strategy A: wait for a result-like node
        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(@class,'result') or contains(@class,'report') or @role='article']")
                )
            )
        except TimeoutException:
            # Strategy B: wait for content growth in body text
            _wait_for_content_growth(driver, wait, min_growth=120)

        # Small grace period for late-rendered chunks
        time.sleep(1.0)

        # --- Extract & print ---
        result_text = _collect_result_text(driver)
        print("==== RateMySite result ====\n")
        if result_text:
            print(result_text)
        else:
            print("(No visible result text was found. Here is the full page text for debugging.)\n")
            try:
                print(driver.find_element(By.TAG_NAME, "body").text)
            except Exception:
                print("(Could not read page body.)")
        print("\n==== END ====")

    finally:
        driver.quit()


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch RateMySite analysis and print it to the terminal.")
    p.add_argument("url", help="Target website URL to analyze (e.g., https://example.com)")
    p.add_argument(
        "--no-headless",
        action="store_true",
        help="Run with a visible Chrome window (default is headless).",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Max time (seconds) to wait for elements/results. Default: {DEFAULT_TIMEOUT}",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    target = args.url.strip()
    if not (target.startswith("http://") or target.startswith("https://")):
        print("[!] Please provide a full URL starting with http:// or https://")
        sys.exit(1)
    run(target_url=target, headless=not args.no_headless, timeout=args.timeout)
