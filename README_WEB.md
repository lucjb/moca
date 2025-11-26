# MOCA Web Interface

A fully local, JavaScript-only web interface for searching accommodations on Booking.com.

## Quick Start

1. **Start the CORS proxy server:**
   ```bash
   node cors-proxy.js
   ```
   Keep this terminal window open.

2. **Open the web interface:**
   - Open `index.html` in your web browser
   - Or use a local server: `python -m http.server 8000` then visit `http://localhost:8000`

3. **Search for accommodations:**
   - Fill in the search form
   - Click "Search Accommodations"
   - Results will appear below

## Requirements

- Node.js (for the CORS proxy server)
- A modern web browser (Chrome, Firefox, Safari, Edge)

## How It Works

The web interface uses pure JavaScript to:
- Make requests to Booking.com through a local CORS proxy
- Parse the HTML response using the browser's built-in DOM parser
- Extract property information (title, price, rating, URL)
- Filter results by property type
- Display results in a beautiful, responsive interface

## Features

- ✅ Fully local (no external dependencies except Booking.com)
- ✅ Pure JavaScript (no Python required)
- ✅ Beautiful, modern UI
- ✅ Property type filtering
- ✅ Free cancellation filter
- ✅ Responsive design
- ✅ Real-time search results

## Troubleshooting

**CORS errors:**
- Make sure the CORS proxy server is running (`node cors-proxy.js`)
- Check that the proxy is accessible at `http://localhost:8080`

**No results:**
- Try different destinations or dates
- Check that Booking.com is accessible from your network
- Some searches may be blocked by Booking.com's anti-bot measures

**Browser console errors:**
- Open browser developer tools (F12) to see detailed error messages
- Check the Network tab to see if requests are being made

