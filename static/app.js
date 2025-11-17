(function () {
  const qs = (s, r = document) => r.querySelector(s);
  const qsa = (s, r = document) => Array.from(r.querySelectorAll(s));

  const btnGo = qs('#go');
  const btnStop = qs('#stop');
  const btnDownload = qs('#download-excel');
  const progressContainer = qs('#progress');
  const progressFill = qs('.progress-fill');
  const statusEl = qs('#status');
  const percentEl = qs('.progress-percent');
  const logEl = qs('#log');
  const logContent = qs('.log-content');
  const thead = qs('#thead');
  const tbody = qs('#tbody');

  let es = null;
  let total = 0;
  let completed = 0;
  let aborted = false;
  let hasResults = false;

  function resetUI() {
    qsa('#thead th:not(:first-child)').forEach(el => el.remove());
    qsa('#tbody tr:not(.section-divider)').forEach(tr => 
      qsa('td:not(:first-child)', tr).forEach(td => td.remove())
    );

    progressContainer.classList.add('hidden');
    progressFill.style.width = '0%';
    statusEl.textContent = '';
    percentEl.textContent = '0%';
    logContent.textContent = '';
    logEl.classList.add('hidden');
    btnDownload.classList.add('hidden');
    completed = 0;
    total = 0;
    aborted = false;
    hasResults = false;
  }

  function showDownloadButton() {
    if (hasResults) {
      btnDownload.classList.remove('hidden');
    }
  }

  function appendColumnHeader(text) {
    const th = document.createElement('th');
    th.textContent = text || '—';
    th.className = 'metric-header';
    thead.appendChild(th);
  }

  function formatTextWithLineBreaks(text) {
    if (!text || text === '-') return text;
    return text.replace(/\. ([A-Z])/g, '.\n$1').trim();
  }

  function fillColumn(data) {
    qsa('#tbody tr:not(.section-divider)').forEach(tr => {
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
      } else if (key && key.includes('Description')) {
        td.className = 'description-cell';
        td.textContent = formatTextWithLineBreaks(val);
      } else if (key && key.includes('Score') && !key.includes('Description') && !isNaN(val) && val !== '-') {
        td.textContent = val;
        td.setAttribute('data-score-only', 'true');
      } else {
        td.textContent = val;
      }
      
      tr.appendChild(td);
    });
    
    hasResults = true;
  }

  function setProgress(pct, text) {
    progressContainer.classList.remove('hidden');
    progressFill.style.width = Math.max(0, Math.min(100, pct)) + '%';
    statusEl.textContent = text || '';
    percentEl.textContent = Math.round(pct) + '%';
  }

  function addLog(line) {
    logEl.classList.remove('hidden');
    logContent.textContent += (logContent.textContent ? '\n' : '') + line;
    logContent.scrollTop = logContent.scrollHeight;
  }

  function stopStream() {
    if (es) { es.close(); es = null; }
    btnGo.disabled = false;
    btnStop.disabled = true;
  }

  function downloadExcel() {
    if (!hasResults) {
      alert('No analysis results available to download.');
      return;
    }

    const originalText = btnDownload.innerHTML;
    btnDownload.innerHTML = '<span class="download-icon">⏳</span> Preparing Download...';
    btnDownload.disabled = true;

    const downloadUrl = '/download-excel';
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    setTimeout(() => {
      btnDownload.innerHTML = originalText;
      btnDownload.disabled = false;
    }, 2000);
  }

  btnGo.addEventListener('click', () => {
    resetUI();
    const urls = [qs('#u1').value, qs('#u2').value, qs('#u3').value, qs('#u4').value]
      .map(s => s.trim())
      .filter(Boolean);

    if (!urls.length) {
      statusEl.textContent = 'Please enter your primary website URL to begin analysis.';
      return;
    }

    btnGo.disabled = true;
    btnStop.disabled = false;
    setProgress(0, 'Initializing competitor UI/UX analysis...');

    const params = new URLSearchParams();
    urls.forEach(u => params.append('u', u));
    es = new EventSource('/stream?' + params.toString());

    es.addEventListener('init', (e) => {
      const payload = JSON.parse(e.data);
      total = payload.total || urls.length;
      addLog('🔍 Step 3: Competitor UI/UX Analysis Starting');
      addLog(`📊 Analyzing ${total} website(s) for competitive insights...`);
      setProgress(1, 'Analysis engine initialized');
    });

    es.addEventListener('start_url', (e) => {
      const { index, url } = JSON.parse(e.data);
      addLog(`\n🎯 [${index}/${total}] Analyzing: ${url}`);
      appendColumnHeader(new URL(url).hostname);
      const pct = ((index - 1) / total) * 100;
      setProgress(pct + 2, `Analyzing ${new URL(url).hostname}...`);
    });

    es.addEventListener('progress', (e) => {
      const { index, phase, p, of } = JSON.parse(e.data);
      const base = ((index - 1) / total) * 100;
      const within = (p / of) * (100 / total);
      setProgress(base + within, `[${index}/${total}] ${phase}`);
    });

    es.addEventListener('debug', (e) => {
      const { index, message } = JSON.parse(e.data);
      if (message) {
        addLog(`   └─ [${index}] ${message}`);
      }
    });

    es.addEventListener('result', (e) => {
      const { index, url, data, error } = JSON.parse(e.data);
      if (error) {
        addLog(`❌ [${index}/${total}] Analysis failed: ${error}`);
        fillColumn({ "Company": "Analysis Failed", "URL": url, "Overall Score": "-" });
      } else {
        addLog(`✅ [${index}/${total}] Analysis complete: ${url}`);
        fillColumn(data);
      }
      completed += 1;
      const pct = (completed / total) * 100;
      setProgress(pct, `Completed ${completed} of ${total} analyses`);
    });

    es.addEventListener('done', () => {
      setProgress(100, aborted ? 'Analysis stopped' : 'Competitive analysis complete!');
      addLog('\n✅ Step 3 completed successfully!');
      addLog('📈 Review results above and proceed to Step 4 when ready.');
      addLog('💾 Click "Download Excel Report" to save your analysis results.');
      showDownloadButton();
      stopStream();
    });

    es.onerror = () => {
      if (!aborted) addLog('❌ Connection error. Please check your network and try again.');
      stopStream();
    };
  });

  btnStop.addEventListener('click', () => {
    aborted = true;
    addLog('\n⏸ Analysis stopped by user');
    stopStream();
    setProgress(100, 'Analysis stopped');
  });

  btnDownload.addEventListener('click', downloadExcel);
})();
