# Browser Automation Service Setup

This service uses Puppeteer (headless Chrome) to automatically browse Booking.com property pages and extract location scores, bypassing anti-bot protection.

## Installation

1. **Install Node.js dependencies:**
   ```bash
   npm install
   ```

   This will install Puppeteer, which includes Chromium.

## Running the Service

1. **Start the browser automation service:**
   ```bash
   node browser-service.js
   ```
   
   Or use npm:
   ```bash
   npm start
   ```

2. **Start the CORS proxy (in a separate terminal):**
   ```bash
   node cors-proxy.js
   ```

3. **Open the web app:**
   Open `index.html` in your browser.

## IP Rotation (Proxy Support)

To avoid HTTP 429 (Too Many Requests) errors, you can configure IP rotation using proxies. The service will automatically rotate IPs when it detects rate limiting.

### Option 1: Environment Variable

Set the `PROXIES` environment variable with a comma-separated list of proxy URLs:

```bash
PROXIES="http://proxy1.com:8080,http://user:pass@proxy2.com:8080,socks5://proxy3.com:1080" node browser-service.js
```

### Option 2: Configuration File

Create a `proxies.json` file in the project root:

```json
{
  "proxies": [
    "http://proxy1.example.com:8080",
    "http://user:pass@proxy2.example.com:8080",
    "socks5://proxy3.example.com:1080"
  ]
}
```

Or as a simple array:

```json
[
  "http://proxy1.example.com:8080",
  "http://proxy2.example.com:8080"
]
```

See `proxies.json.example` for a template.

### Supported Proxy Formats

- **HTTP/HTTPS proxies:** `http://host:port` or `http://user:pass@host:port`
- **SOCKS5 proxies:** `socks5://host:port` or `socks5://user:pass@host:port`

### How It Works

- When a 429 error is detected, the service automatically rotates to the next proxy
- Uses exponential backoff (5s, 10s, 20s) between retries
- Supports up to 3 retries with different IPs
- Proxies are rotated in round-robin fashion

## How It Works

- The browser service runs on `http://localhost:8081`
- It uses Puppeteer to control a real Chrome browser
- When the frontend needs location scores, it calls the browser service
- The service navigates to the property page, waits for content to load, and extracts the location score
- This bypasses anti-bot protection because it's using a real browser

## API Endpoints

- `GET /health` - Check if the service is running
- `GET /fetch-property?url=<property-url>` - Fetch a property page and extract location score

## Troubleshooting

- **Browser fails to launch:** Make sure you have enough disk space (Puppeteer downloads Chromium)
- **Service not responding:** Check that port 8081 is not in use
- **HTTP 429 errors:** 
  - Configure proxies for IP rotation (see IP Rotation section above)
  - Add more proxies to your list for better rotation
  - Increase delays between requests
- **Still getting blocked:** Booking.com may have additional protections. Try:
  - Using IP rotation with proxies
  - Increasing wait times in `browser-service.js`
  - Using a different user agent
  - Adding more realistic browser behavior
  - Using residential proxies instead of datacenter proxies

## Performance

- Each property page fetch takes ~5-10 seconds (browser needs to load the page)
- The service reuses a single browser instance for efficiency
- Multiple requests are handled sequentially to avoid overwhelming Booking.com

