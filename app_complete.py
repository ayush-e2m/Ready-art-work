#!/usr/bin/env python3
"""
Complete Flask web app for RateMySite analysis - single file solution
"""

import json
import re
import time
import traceback
from typing import Dict, List, Optional, Generator

from flask import Flask, Response, stream_with_context, request
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
            "//input[@type='url']",
            "//input[contains(@placeholder,'https')]",
            "//input[contains(@placeholder,'http')]",
            "//input[contains(@placeholder,'Enter') or contains(@placeholder,'enter')]",
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
        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(@class,'result') or contains(@class,'report') or @role='article']")
                )
            )
            debug_log.append("Found result container")
        except TimeoutException:
            debug_log.append("No result container found, waiting for content growth...")
            _wait_for_content_growth(driver, wait, min_growth=120)
            debug_log.append("Finished waiting for content growth")

        time.sleep(1.0)
        debug_log.append("Extracting result text...")
        result_text = _collect_result_text(driver)
        debug_log.append(f"Extracted {len(result_text)} characters of result text")
        
        if not result_text:
            debug_log.append("No result text found! Getting page debug info...")
            try:
                page_text = driver.find_element(By.TAG_NAME, "body").text
                debug_log.append(f"Full page text length: {len(page_text)}")
                debug_log.append(f"Page text preview: {page_text[:800]}")
            except Exception as e:
                debug_log.append(f"Could not get page text: {e}")
        
        return result_text, debug_log

    except Exception as e:
        debug_log.append(f"ERROR in analysis: {e}")
        debug_log.append(f"Traceback: {traceback.format_exc()}")
        return "", debug_log
    finally:
        debug_log.append("Closing driver...")
        driver.quit()

def _grab_block(text: str, labels: List[str], multiline=True) -> str:
    for lab in labels:
        if multiline:
            m = re.search(rf"{lab}\s*[:\-]?\s*(.+?)(?:\n\s*\n|\n[A-Z][^\n]{{0,60}}:\s|$)", text, flags=re.I | re.S)
        else:
            m = re.search(rf"{lab}\s*[:\-]?\s*([^\n]+)", text, flags=re.I)
        if m:
            return m.group(1).strip()
    return "-"

def _grab_score(text: str, labels: List[str]) -> str:
    for lab in labels:
        m = re.search(rf"{lab}\s*[:\-]?\s*(\d{{1,3}})", text, flags=re.I)
        if m:
            return m.group(1)
    return "-"

def _parse_fields(url: str, raw: str) -> Dict[str, str]:
    return {
        "Company": _grab_block(raw, ["Company", "Site Name", "Website Name"], multiline=False),
        "URL": url,
        "Overall Score": _grab_score(raw, ["Overall Score", "Score", "Total Score"]),
        "Description of Website": _grab_block(raw, ["Description of Website", "Description", "Site Description"]),
        "Consumer Score": _grab_score(raw, ["Consumer Score", "Customer Score", "End-user Score"]),
        "Developer Score": _grab_score(raw, ["Developer Score", "Engineer Score", "Dev Score"]),
        "Investor Score": _grab_score(raw, ["Investor Score"]),
        "Clarity Score": _grab_score(raw, ["Clarity Score", "Readability Score"]),
        "Visual Design Score": _grab_score(raw, ["Visual Design Score", "Design Score"]),
        "UX Score": _grab_score(raw, ["UX Score", "Usability Score"]),
        "Trust Score": _grab_score(raw, ["Trust Score", "Credibility Score"]),
        "Value Prop Score": _grab_score(raw, ["Value Prop Score", "Value Proposition Score"]),
        "_raw": raw,
    }

app = Flask(__name__)

TABLE_ROWS = [
    ("Company", "Company"),
    ("URL", "URL"),
    ("Overall Score", "Overall Score"),
    ("Description of Website", "Description of Website"),
    ("Consumer Score", "Audience Perspective → Consumer"),
    ("Developer Score", "Audience Perspective → Developer"),
    ("Investor Score", "Audience Perspective → Investor"),
    ("Clarity Score", "Technical Criteria → Clarity"),
    ("Visual Design Score", "Technical Criteria → Visual Design"),
    ("UX Score", "Technical Criteria → UX"),
    ("Trust Score", "Technical Criteria → Trust"),
    ("Value Prop Score", "Value Proposition"),
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
        
        raw_text, debug_messages = _analyze_one_with_debugging(url, timeout=DEFAULT_TIMEOUT)
        
        for msg in debug_messages:
            yield sse("debug", {"index": idx, "message": msg})

        cur += 1
        yield sse("progress", {"index": idx, "phase": "Parsing output", "p": cur, "of": step_total})
        
        if raw_text:
            data = _parse_fields(url, raw_text)
            yield sse("result", {"index": idx, "url": url, "data": data})
        else:
            yield sse("result", {"index": idx, "url": url, "error": "No results found - check debug log"})

        cur += 1
        yield sse("progress", {"index": idx, "phase": "Done", "p": cur, "of": step_total})
        print(f"[{idx}/{total}] Done {url}")

    yield sse("done", {"ok": True})

@app.route("/")
def index():
    return '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RateMySite – Live Compare</title>
  <style>
    :root { 
      --bg:#0b0d12; 
      --fg:#e7ecf3; 
      --muted:#9aa7b2; 
      --card:#121623; 
      --line:#202434; 
      --accent:#3b82f6; 
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, 'Segoe UI', Roboto, Ubuntu, sans-serif;
      background: var(--bg);
      color: var(--fg);
      line-height: 1.5;
    }
    .container {
      max-width: 1200px;
      margin: 24px auto;
      padding: 0 16px;
    }
    h1 {
      margin: 0 0 6px;
      font-size: 28px;
      font-weight: 700;
    }
    .sub {
      color: var(--muted);
      margin-top: 0;
      margin-bottom: 24px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 16px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }
    label {
      display: flex;
      flex-direction: column;
      gap: 6px;
      font-weight: 600;
    }
    input[type="url"] {
      background: #0e1320;
      border: 1px solid var(--line);
      color: var(--fg);
      padding: 10px 12px;
      border-radius: 8px;
      font-size: 14px;
    }
    input[type="url"]:focus {
      outline: none;
      border-color: var(--accent);
    }
    .actions {
      display: flex;
      gap: 8px;
      margin-top: 12px;
    }
    button {
      padding: 10px 16px;
      background: var(--accent);
      color: white;
      border: 0;
      border-radius: 8px;
      cursor: pointer;
      font-weight: 600;
      font-size: 14px;
    }
    button:hover:not(:disabled) {
      filter: brightness(1.1);
    }
    button.muted {
      background: #2b2f3f;
      color: #cbd5e1;
    }
    button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
    .progress {
      height: 12px;
      background: #0f1423;
      border: 1px solid var(--line);
      border-radius: 999px;
      overflow: hidden;
      margin-top: 12px;
    }
    .progress .bar {
      height: 100%;
      background: linear-gradient(90deg, var(--accent), #60a5fa);
      transition: width 0.3s ease;
    }
    .hidden { display: none; }
    .status {
      color: var(--muted);
      margin: 8px 0 0;
      font-size: 14px;
    }
    .table-wrap {
      margin-top: 24px;
      overflow: auto;
      border-radius: 12px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      overflow: hidden;
    }
    th, td {
      padding: 12px 16px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
      text-align: left;
    }
    thead th {
      background: #0f1423;
      position: sticky;
      top: 0;
      font-weight: 600;
      color: var(--fg);
    }
    .row-head {
      white-space: nowrap;
      font-weight: 600;
      color: var(--muted);
      background: #0f1220;
    }
    tbody tr:hover {
      background: #151824;
    }
    tbody tr:nth-child(odd) td:not(.row-head) {
      background: #0f1220;
    }
    .log {
      margin-top: 16px;
      white-space: pre-wrap;
      font-family: 'SF Mono', Monaco, Consolas, monospace;
      font-size: 13px;
      line-height: 1.4;
      max-height: 400px;
      overflow-y: auto;
      background: #0a0c11;
      border: 1px solid var(--line);
      padding: 16px;
      border-radius: 8px;
    }
    .log::-webkit-scrollbar {
      width: 6px;
    }
    .log::-webkit-scrollbar-track {
      background: #0f1423;
    }
    .log::-webkit-scrollbar-thumb {
      background: #2b2f3f;
      border-radius: 3px;
    }
    .foot {
      color: var(--muted);
      margin: 40px 0;
      text-align: center;
      font-size: 13px;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>RateMySite – Live Compare</h1>
      <p class="sub">Enter up to four URLs. You'll see progress and each site's column appear as it finishes.</p>
    </header>

    <main>
      <form id="form" class="card" onsubmit="return false;">
        <div class="grid">
          <label>Link 1
            <input type="url" id="u1" placeholder="https://example.com">
          </label>
          <label>Link 2
            <input type="url" id="u2" placeholder="https://google.com">
          </label>
          <label>Link 3
            <input type="url" id="u3" placeholder="https://github.com">
          </label>
          <label>Link 4
            <input type="url" id="u4" placeholder="https://stackoverflow.com">
          </label>
        </div>
        <div class="actions">
          <button id="go">Analyze Sites</button>
          <button id="stop" type="button" class="muted" disabled>Stop</button>
        </div>

        <div id="progress" class="progress hidden">
          <div class="bar" style="width:0%"></div>
        </div>
        <p id="status" class="status"></p>
      </form>

      <div class="table-wrap">
        <table id="compare">
          <thead>
            <tr id="thead">
              <th>Category</th>
            </tr>
          </thead>
          <tbody id="tbody">
            <tr data-key="Company"><td class="row-head">Company</td></tr>
            <tr data-key="URL"><td class="row-head">URL</td></tr>
            <tr data-key="Overall Score"><td class="row-head">Overall Score</td></tr>
            <tr data-key="Description of Website"><td class="row-head">Description of Website</td></tr>
            <tr data-key="Consumer Score"><td class="row-head">Audience Perspective → Consumer</td></tr>
            <tr data-key="Developer Score"><td class="row-head">Audience Perspective → Developer</td></tr>
            <tr data-key="Investor Score"><td class="row-head">Audience Perspective → Investor</td></tr>
            <tr data-key="Clarity Score"><td class="row-head">Technical Criteria → Clarity</td></tr>
            <tr data-key="Visual Design Score"><td class="row-head">Technical Criteria → Visual Design</td></tr>
            <tr data-key="UX Score"><td class="row-head">Technical Criteria → UX</td></tr>
            <tr data-key="Trust Score"><td class="row-head">Technical Criteria → Trust</td></tr>
            <tr data-key="Value Prop Score"><td class="row-head">Value Proposition</td></tr>
          </tbody>
        </table>
      </div>

      <div id="log" class="log card hidden"></div>
    </main>

    <footer class="foot">
      <small>Demo app. Output is parsed best-effort from RateMySite with real-time debugging.</small>
    </footer>
  </div>

  <script>
    (function () {
      const qs = (s, r = document) => r.querySelector(s);
      const qsa = (s, r = document) => Array.from(r.querySelectorAll(s));

      const btnGo = qs('#go');
      const btnStop = qs('#stop');
      const bar = qs('#progress');
      const barInner = qs('#progress .bar');
      const statusEl = qs('#status');
      const logEl = qs('#log');
      const thead = qs('#thead');
      const tbody = qs('#tbody');

      let es = null;
      let total = 0;
      let completed = 0;
      let aborted = false;

      function resetUI() {
        qsa('#thead th:not(:first-child)').forEach(el => el.remove());
        qsa('#tbody tr').forEach(tr => qsa('td:not(:first-child)', tr).forEach(td => td.remove()));

        bar.classList.add('hidden');
        barInner.style.width = '0%';
        statusEl.textContent = '';
        logEl.textContent = '';
        logEl.classList.add('hidden');
        completed = 0;
        total = 0;
        aborted = false;
      }

      function appendColumnHeader(text) {
        const th = document.createElement('th');
        th.textContent = text || '—';
        thead.appendChild(th);
      }

      function fillColumn(data) {
        qsa('#tbody tr').forEach(tr => {
          const key = tr.getAttribute('data-key');
          const td = document.createElement('td');
          let val = (data && data[key]) || '-';
          if (key === 'URL' && val && typeof val === 'string' && val !== '-') {
            const a = document.createElement('a');
            a.href = val;
            a.target = '_blank';
            a.rel = 'noopener';
            a.textContent = val;
            td.appendChild(a);
          } else {
            td.textContent = val;
          }
          tr.appendChild(td);
        });
      }

      function setProgress(pct, text) {
        bar.classList.remove('hidden');
        barInner.style.width = Math.max(0, Math.min(100, pct)) + '%';
        statusEl.textContent = text || '';
      }

      function addLog(line) {
        logEl.classList.remove('hidden');
        logEl.textContent += (logEl.textContent ? '\\n' : '') + line;
        logEl.scrollTop = logEl.scrollHeight;
      }

      function stopStream() {
        if (es) { es.close(); es = null; }
        btnGo.disabled = false;
        btnStop.disabled = true;
      }

      btnGo.addEventListener('click', () => {
        resetUI();
        const urls = [qs('#u1').value, qs('#u2').value, qs('#u3').value, qs('#u4').value]
          .map(s => s.trim())
          .filter(Boolean);

        if (!urls.length) {
          statusEl.textContent = 'Please enter at least one URL.';
          return;
        }

        btnGo.disabled = true;
        btnStop.disabled = false;
        setProgress(0, 'Starting analysis...');

        const params = new URLSearchParams();
        urls.forEach(u => params.append('u', u));
        es = new EventSource('/stream?' + params.toString());

        es.addEventListener('init', (e) => {
          const payload = JSON.parse(e.data);
          total = payload.total || urls.length;
          addLog('Starting analysis of ' + total + ' site(s)...');
          setProgress(1, 'Initializing...');
        });

        es.addEventListener('start_url', (e) => {
          const data = JSON.parse(e.data);
          const index = data.index;
          const url = data.url;
          addLog('\\n--- [' + index + '/' + total + '] Starting: ' + url + ' ---');
          appendColumnHeader(new URL(url).hostname);
          const pct = ((index - 1) / total) * 100;
          setProgress(pct + 2, 'Analyzing ' + url + '...');
        });

        es.addEventListener('progress', (e) => {
          const data = JSON.parse(e.data);
          const index = data.index;
          const phase = data.phase;
          const p = data.p;
          const of = data.of;
          const base = ((index - 1) / total) * 100;
          const within = (p / of) * (100 / total);
          setProgress(base + within, '[' + index + '/' + total + '] ' + phase);
        });

        es.addEventListener('debug', (e) => {
          const data = JSON.parse(e.data);
          const index = data.index;
          const message = data.message;
          if (message) {
            addLog('  [' + index + '] ' + message);
          }
        });

        es.addEventListener('result', (e) => {
          const data = JSON.parse(e.data);
          const index = data.index;
          const url = data.url;
          const resultData = data.data;
          const error = data.error;
          if (error) {
            addLog('ERROR [' + index + '/' + total + ']: ' + error);
            fillColumn({ "Company": "Error", "URL": url, "Overall Score": "-" });
          } else {
            addLog('SUCCESS [' + index + '/' + total + ']: ' + url);
            fillColumn(resultData);
          }
          completed += 1;
          const pct = (completed / total) * 100;
          setProgress(pct, 'Completed ' + completed + ' of ' + total);
        });

        es.addEventListener('done', () => {
          setProgress(100, aborted ? 'Stopped' : 'Analysis complete!');
          addLog('\\nAll analyses completed!');
          stopStream();
        });

        es.onerror = () => {
          if (!aborted) addLog('ERROR: Stream connection failed. Check server console.');
          stopStream();
        };
      });

      btnStop.addEventListener('click', () => {
        aborted = true;
        addLog('\\nStopping analysis...');
        stopStream();
        setProgress(100, 'Stopped');
      });
    })();
  </script>
</body>
</html>'''

@app.route("/stream")
def stream():
    urls = [u.strip() for u in request.args.getlist("u") if u.strip()]
    if not urls:
        return Response("Need at least one ?u=", status=400)
    return Response(stream_with_context(stream_analysis(urls)), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000, threaded=True)