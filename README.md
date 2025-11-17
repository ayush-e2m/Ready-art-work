# RateMySite Analysis Tool

This tool analyzes websites using the RateMySite service and provides a comprehensive comparison interface.

## Project Structure
```
rate-mysite-tool/
├── app.py                    # Main Flask web application
├── rate_site_terminal.py     # Terminal version for single site analysis
├── requirements.txt          # Python dependencies
├── templates/
│   ├── base.html            # Base HTML template
│   └── index.html           # Main page template
└── static/
    ├── styles.css           # CSS styles
    └── app.js              # JavaScript frontend logic
```

## Setup Instructions

1. **Create a virtual environment** (recommended):
```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:
```bash
   pip install -r requirements.txt
```

3. **Run the web application**:
```bash
   python app.py
```

4. **Open your browser** and go to:
```
   http://127.0.0.1:5000
```

## Usage

### Web Interface
- Enter up to 4 URLs to compare
- Click "Analyze Sites" to start the analysis
- Watch real-time progress and debug logs
- View results in a comparison table as each site completes

### Terminal Version
For single site analysis:
```bash
python rate_site_terminal.py https://example.com
```

Optional flags:
- `--no-headless`: Run with visible browser window
- `--timeout 60`: Set custom timeout (default: 45 seconds)

## Features

- **Real-time Analysis**: See progress as each site is analyzed
- **Detailed Debugging**: View step-by-step logs of the analysis process  
- **Responsive Design**: Works on desktop and mobile devices
- **Multiple Site Comparison**: Compare up to 4 websites side-by-side
- **Error Handling**: Graceful handling of failed analyses

## How It Works

1. **Selenium Automation**: Uses Chrome browser automation to interact with RateMySite
2. **Smart Element Detection**: Finds input fields and buttons using multiple fallback strategies
3. **Content Extraction**: Intelligently extracts analysis results from the page
4. **Real-time Streaming**: Uses Server-Sent Events (SSE) for live progress updates
5. **Data Parsing**: Extracts structured data from the analysis results

## Troubleshooting

- **Chrome Driver Issues**: The tool auto-downloads the correct ChromeDriver version
- **Timeout Errors**: Increase the timeout if sites are taking too long to analyze
- **Network Issues**: Ensure you have a stable internet connection
- **Permission Errors**: Run with appropriate permissions if Chrome fails to start

## Requirements

- Python 3.7+
- Chrome browser (installed automatically via webdriver-manager)
- Internet connection for accessing RateMySite and downloading ChromeDriver

## Notes

- The tool works by automating interactions with the RateMySite website
- Analysis results are parsed using pattern matching and may vary based on site updates
- Some sites may take longer to analyze than others
- The debug log provides detailed information about each step of the process