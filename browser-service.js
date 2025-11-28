#!/usr/bin/env node

/**
 * Browser Automation Service using Puppeteer
 * This service uses a real browser to fetch Booking.com property pages
 * and extract location scores, bypassing anti-bot protection.
 * 
 * Run with: node browser-service.js
 * Then the frontend can call it at http://localhost:8081/fetch-property?url=...
 */

const http = require('http');
const url = require('url');
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

const PORT = 8081;
let browser = null;
let currentProxyIndex = 0;

// Rate limiting configuration
const MAX_CONCURRENT_REQUESTS = 2; // Limit concurrent requests to avoid rate limiting
const MIN_DELAY_BETWEEN_REQUESTS = 2000; // Minimum 2 seconds between requests
const MAX_RETRIES = 3; // Maximum retries for 429 errors
const RETRY_DELAY_BASE = 5000; // Base delay for exponential backoff (5 seconds)

// Request queue and tracking
let requestQueue = [];
let activeRequests = 0;
let lastRequestTime = 0;

// Proxy configuration
// Supports:
// 1. Environment variable PROXIES (comma-separated list)
// 2. Environment variable PROXY_LIST (comma-separated list)
// 3. Config file: proxies.json (array of proxy URLs)
// Format: http://user:pass@host:port or socks5://user:pass@host:port
// Example: PROXIES="http://proxy1.com:8080,socks5://proxy2.com:1080" node browser-service.js
let proxies = [];

// Load from environment variable
const PROXIES_ENV = process.env.PROXIES || process.env.PROXY_LIST;
if (PROXIES_ENV) {
    proxies = PROXIES_ENV.split(',').map(p => p.trim()).filter(p => p);
    console.log(`Loaded ${proxies.length} proxy(ies) from environment`);
} else {
    // Try to load from config file
    const configPath = path.join(__dirname, 'proxies.json');
    try {
        if (fs.existsSync(configPath)) {
            const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
            if (Array.isArray(config.proxies)) {
                proxies = config.proxies.filter(p => p && typeof p === 'string');
                console.log(`Loaded ${proxies.length} proxy(ies) from ${configPath}`);
            } else if (Array.isArray(config)) {
                proxies = config.filter(p => p && typeof p === 'string');
                console.log(`Loaded ${proxies.length} proxy(ies) from ${configPath}`);
            }
        }
    } catch (e) {
        console.warn(`Could not load proxies from ${configPath}:`, e.message);
    }
}

// Proxy rotation function
function getNextProxy() {
    if (proxies.length === 0) {
        return null;
    }
    const proxy = proxies[currentProxyIndex];
    currentProxyIndex = (currentProxyIndex + 1) % proxies.length;
    return proxy;
}

// Get current proxy
function getCurrentProxy() {
    if (proxies.length === 0) {
        return null;
    }
    return proxies[currentProxyIndex];
}

// Parse proxy URL and return Puppeteer proxy args
function getProxyArgs(proxyUrl) {
    if (!proxyUrl) {
        return { args: [] };
    }
    
    try {
        const url = new URL(proxyUrl);
        const protocol = url.protocol.replace(':', '');
        
        if (protocol === 'http' || protocol === 'https') {
            return {
                args: [`--proxy-server=${protocol}://${url.hostname}:${url.port || 8080}`]
            };
        } else if (protocol === 'socks5' || protocol === 'socks4') {
            // SOCKS proxies require additional setup
            return {
                args: [`--proxy-server=${protocol}://${url.hostname}:${url.port || 1080}`]
            };
        }
    } catch (e) {
        console.warn(`Invalid proxy URL format: ${proxyUrl}`, e.message);
    }
    
    return { args: [] };
}

// Initialize browser on startup
async function initBrowser(proxyUrl = null) {
    console.log('Launching browser...');
    const proxy = proxyUrl || getCurrentProxy();
    const proxyArgs = getProxyArgs(proxy);
    
    if (proxy) {
        console.log(`Using proxy: ${proxy.replace(/\/\/.*@/, '//***:***@')}`); // Hide credentials in logs
    } else {
        console.log('No proxy configured, using direct connection');
    }
    
    const launchOptions = {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--window-size=1920,1080',
            ...proxyArgs.args
        ],
        defaultViewport: {
            width: 1920,
            height: 1080
        }
    };
    
    browser = await puppeteer.launch(launchOptions);
    console.log('Browser launched successfully');
}

// Extract location score from property page
function extractLocationScore(html) {
    const htmlLower = html.toLowerCase();
    
    // Find all occurrences of "location" in the HTML
    const locationMatches = [];
    let searchIndex = 0;
    while ((searchIndex = htmlLower.indexOf('location', searchIndex)) !== -1) {
        locationMatches.push(searchIndex);
        searchIndex += 1;
    }
    
    let locationScore = null;
    
    // For each "location" occurrence, check if it's near a review-subscore
    for (const locIndex of locationMatches) {
        // Get context around "location" (500 chars before, 1000 chars after)
        const contextStart = Math.max(0, locIndex - 500);
        const contextEnd = Math.min(html.length, locIndex + 1000);
        const context = html.substring(contextStart, contextEnd);
        const contextLower = context.toLowerCase();
        
        // Check if this context contains "review-subscore" or similar patterns
        const isReviewContext = (
            contextLower.includes('review-subscore') || 
            contextLower.includes('review_subscore') ||
            contextLower.includes('data-testid') ||
            (contextLower.includes('review') && contextLower.includes('score')) ||
            contextLower.includes('rating') ||
            contextLower.includes('subscore')
        );
        
        if (isReviewContext) {
            // Now look for aria-hidden="true" followed by a number in this context
            const locationInContext = contextLower.indexOf('location');
            const afterLocation = context.substring(locationInContext + 8);
            
            // Try multiple patterns for aria-hidden
            const ariaPatterns = [
                /aria-hidden=["']true["'][^>]*>(\d+\.?\d*)/i,
                /aria-hidden\s*=\s*["']true["'][^>]*>(\d+\.?\d*)/i,
                /aria-hidden=["']true["'][^>]*>\s*(\d+\.?\d*)/i
            ];
            
            for (const pattern of ariaPatterns) {
                const scoreMatch = afterLocation.match(pattern);
                if (scoreMatch && scoreMatch[1]) {
                    const score = parseFloat(scoreMatch[1]);
                    if (score >= 1 && score <= 10) {
                        locationScore = score;
                        break;
                    }
                }
            }
            
            // If not found via aria-hidden, look for any number after "location"
            if (locationScore === null) {
                const numbers = afterLocation.match(/(\d+\.?\d*)/g);
                if (numbers) {
                    for (const numStr of numbers) {
                        const score = parseFloat(numStr);
                        if (score >= 1 && score <= 10) {
                            const numIndex = afterLocation.indexOf(numStr);
                            const beforeNum = afterLocation.substring(Math.max(0, numIndex - 50), numIndex);
                            
                            // Look for HTML tags around this number (indicates it's in an element)
                            if (beforeNum.includes('>') || beforeNum.includes('<')) {
                                locationScore = score;
                                break;
                            }
                        }
                    }
                }
            }
            
            if (locationScore !== null) break;
        }
    }
    
    // Final fallback: aggressive search
    if (locationScore === null) {
        for (const locIdx of locationMatches) {
            const searchWindow = html.substring(locIdx, Math.min(html.length, locIdx + 500));
            const ariaMatch = searchWindow.match(/aria-hidden=["']true["'][^>]*>(\d+\.?\d*)/i);
            if (ariaMatch && ariaMatch[1]) {
                const score = parseFloat(ariaMatch[1]);
                if (score >= 1 && score <= 10) {
                    locationScore = score;
                    break;
                }
            }
        }
    }
    
    // Additional method: Find all review-subscore divs and search within them
    if (locationScore === null) {
        const reviewSubscoreRegex = /<div[^>]*data-testid=["']review-subscore["'][^>]*>([\s\S]*?)<\/div>/gi;
        let match;
        while ((match = reviewSubscoreRegex.exec(html)) !== null && locationScore === null) {
            const blockHtml = match[0];
            const blockLower = blockHtml.toLowerCase();
            
            if (blockLower.includes('location')) {
                // Found location block, extract score
                const ariaPatterns = [
                    /aria-hidden=["']true["'][^>]*>(\d+\.?\d*)/i,
                    /aria-hidden\s*=\s*["']true["'][^>]*>(\d+\.?\d*)/i
                ];
                
                for (const pattern of ariaPatterns) {
                    const scoreMatch = blockHtml.match(pattern);
                    if (scoreMatch && scoreMatch[1]) {
                        const score = parseFloat(scoreMatch[1]);
                        if (score >= 1 && score <= 10) {
                            locationScore = score;
                            console.log(`Extracted location score from review-subscore block: ${locationScore}`);
                            break;
                        }
                    }
                }
                
                // If still not found, look for any number in the block
                if (locationScore === null) {
                    const numbers = blockHtml.match(/(\d+\.?\d*)/g);
                    if (numbers) {
                        for (const numStr of numbers) {
                            const score = parseFloat(numStr);
                            if (score >= 1 && score <= 10) {
                                // Make sure it's not part of a date or other number
                                const numIndex = blockHtml.indexOf(numStr);
                                const context = blockHtml.substring(Math.max(0, numIndex - 20), Math.min(blockHtml.length, numIndex + numStr.length + 20));
                                // Check if it's likely a score (not a year, not part of a larger number)
                                if (!context.match(/\d{4}/) && !context.match(/\d{5,}/)) {
                                    locationScore = score;
                                    console.log(`Extracted location score from block (fallback): ${locationScore}`);
                                    break;
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    return locationScore;
}

// Helper function to wait/delay (replaces deprecated waitForTimeout)
function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Fetch property page using browser automation with retry and IP rotation
async function fetchPropertyPage(propertyUrl, retryCount = 0, useProxy = null) {
    // Check if we need to rotate IP due to rate limiting
    if (retryCount > 0 && proxies.length > 0) {
        console.log(`Rotating IP for retry attempt ${retryCount + 1}...`);
        useProxy = getNextProxy();
        console.log(`Using new proxy: ${useProxy ? useProxy.replace(/\/\/.*@/, '//***:***@') : 'none'}`);
        
        // Close current browser and create new one with different proxy
        if (browser) {
            try {
                await browser.close();
            } catch (e) {
                console.warn('Error closing browser:', e.message);
            }
        }
        
        // Reinitialize browser with new proxy
        await initBrowser(useProxy);
    } else if (!browser) {
        // Initialize browser if not already initialized
        await initBrowser(useProxy);
    }
    
    const page = await browser.newPage();
    
    try {
        // Set realistic browser headers and extra headers to appear more human-like
        await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
        await page.setViewport({ width: 1920, height: 1080 });
        
        // Set extra headers to appear more human-like
        await page.setExtraHTTPHeaders({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        });
        
        // Navigate to the property page
        console.log(`Fetching: ${propertyUrl}${useProxy ? ` (via proxy)` : ''}`);
        const fetchStartTime = Date.now();
        
        let navigationError = null;
        let response = null;
        let is429Error = false;
        let pageLoaded = false;
        
        try {
            const navStartTime = Date.now();
            // Navigate and wait for DOM to be ready
            response = await page.goto(propertyUrl, {
                waitUntil: 'domcontentloaded',
                timeout: 30000
            });
            const navEndTime = Date.now();
            console.log(`[TIMING] Page navigation took ${navEndTime - navStartTime}ms`);
            
            pageLoaded = true;
            
            // Check response status for 429
            if (response && response.status() === 429) {
                is429Error = true;
            }
            
            // Wait for page to be interactive and content to load
            console.log('Waiting for page content to load...');
            try {
                await page.waitForFunction(() => {
                    return document.readyState === 'complete' && 
                           document.body && 
                           document.body.textContent && 
                           document.body.textContent.length > 100;
                }, { timeout: 15000 });
                console.log('✓ Page content loaded');
            } catch (e) {
                console.log('Page readyState check timed out, checking if content exists...');
                // Check if we have any content at all
                const hasContent = await page.evaluate(() => {
                    return document.body && document.body.textContent && document.body.textContent.length > 50;
                }).catch(() => false);
                if (!hasContent) {
                    console.log('⚠ Warning: Page appears to have very little content');
                }
            }
            
            // Wait a bit more for JavaScript to execute and render content
            await delay(2000);
            
        } catch (e) {
            navigationError = e;
            
            // Check if it's a 429 error from error message
            is429Error = (
                e.message.includes('429') ||
                e.message.includes('Too Many Requests') ||
                (e.message.includes('net::ERR_') && e.message.includes('429'))
            );
            
            // If it's a timeout (not a 429), check if page has content
            if (!is429Error) {
                try {
                    const url = await page.url();
                    if (url && url !== 'about:blank') {
                        const hasContent = await page.evaluate(() => {
                            return document.body && document.body.textContent && document.body.textContent.length > 100;
                        }).catch(() => false);
                        
                        if (hasContent) {
                            pageLoaded = true;
                            console.log('Page has content, continuing...');
                            // Still wait for content to be more complete
                            await delay(3000);
                        }
                    }
                } catch (urlError) {
                    // Can't check
                }
            }
            
            // Check response status for 429 (only if response exists)
            if (response) {
                try {
                    if (response.status() === 429) {
                        is429Error = true;
                    }
                } catch (e) {
                    // Response might not have status method, ignore
                }
            }
        }
        
        // Handle 429 errors with IP rotation
        if (is429Error) {
            await page.close();
            
            if (retryCount < MAX_RETRIES && proxies.length > 0) {
                console.log(`429 error detected, will rotate IP and retry...`);
                
                // Calculate exponential backoff delay
                const delayMs = RETRY_DELAY_BASE * Math.pow(2, retryCount);
                console.log(`Waiting ${delayMs}ms before retry with new IP...`);
                await delay(delayMs);
                
                // Retry with IP rotation
                return await fetchPropertyPage(propertyUrl, retryCount + 1, null);
            } else {
                throw new Error(`HTTP 429: Too Many Requests. ${proxies.length > 0 ? 'All proxies exhausted or max retries reached.' : 'Consider using proxies to rotate IPs. Set PROXIES environment variable.'}`);
            }
        }
        
        // If page didn't load, throw error
        if (!pageLoaded) {
            await page.close();
            throw new Error('Failed to load page: ' + (navigationError ? navigationError.message : 'Unknown error'));
        }
        
        // Wait a bit for dynamic content if we had navigation issues
        if (navigationError && !is429Error) {
            console.log('Navigation had issues, waiting for dynamic content...');
            await delay(3000); // Wait for dynamic content
        }
        
        // Ensure page is ready before proceeding
        try {
            await page.waitForSelector('body', { timeout: 5000 });
        } catch (e) {
            console.warn('Body selector not found, but continuing...');
        }
        
        // Wait for key elements that indicate the page is loaded
        console.log('Waiting for page elements to appear...');
        try {
            // Wait for property header or main content to appear (more lenient)
            await page.waitForFunction(() => {
                // Check for various indicators that page is loaded
                const hasHeader = document.querySelector('[data-testid="PropertyHeaderDesktop-wrapper"]') ||
                                 document.querySelector('h1') ||
                                 document.querySelector('.property-header') ||
                                 document.querySelector('title');
                const hasContent = document.body && document.body.textContent && document.body.textContent.length > 200;
                return hasHeader && hasContent;
            }, { timeout: 10000, polling: 500 }).catch(() => {
                console.log('Key elements check timed out, checking basic content...');
            });
            
            // Verify we have basic content
            const hasBasicContent = await page.evaluate(() => {
                return document.body && document.body.textContent && document.body.textContent.length > 200;
            }).catch(() => false);
            
            if (!hasBasicContent) {
                console.log('⚠ Warning: Page has very little content, but continuing...');
            } else {
                console.log('✓ Page elements found');
            }
        } catch (e) {
            console.log('Waiting for elements failed, but continuing...');
        }
        
        // Scroll the page gradually to trigger lazy loading
        console.log('Scrolling page to trigger lazy loading...');
        const scrollSteps = [0.25, 0.5, 0.75, 1.0];
        for (const step of scrollSteps) {
            await page.evaluate((s) => {
                window.scrollTo(0, document.body.scrollHeight * s);
            }, step);
            await delay(2000); // Wait for content to load after each scroll
        }
        
        // Scroll back to top
        await page.evaluate(() => {
            window.scrollTo(0, 0);
        });
        await delay(2000);
        
        // Try to navigate to reviews tab if it exists
        try {
            // Try multiple selectors for the reviews tab
            const reviewsTabSelectors = [
                'a[href*="#tab-reviews"]',
                'button[data-tab="reviews"]',
                'a[href*="tab-reviews"]',
                '[data-tab-id="reviews"]',
                'a:has-text("Reviews")'
            ];
            
            let reviewsTab = null;
            for (const selector of reviewsTabSelectors) {
                try {
                    reviewsTab = await page.$(selector);
                    if (reviewsTab) break;
                } catch (e) {
                    // Continue to next selector
                }
            }
            
            if (reviewsTab) {
                await reviewsTab.click();
                await delay(2000);
                console.log('Clicked reviews tab');
            } else {
                // Try navigating directly to the reviews URL
                const reviewsUrl = propertyUrl.split('#')[0] + '#tab-reviews';
                try {
                    await page.goto(reviewsUrl, {
                        waitUntil: 'networkidle0',
                        timeout: 30000
                    });
                } catch (e) {
                    await page.goto(reviewsUrl, {
                        waitUntil: 'domcontentloaded',
                        timeout: 30000
                    });
                    await delay(3000);
                }
                await delay(2000);
                console.log('Navigated directly to reviews tab');
            }
        } catch (e) {
            // Reviews tab might not exist or might be loaded differently
            console.log('Could not navigate to reviews tab, continuing with main page...');
        }
        
        // Get the HTML content
        const html = await page.content();
        
        // Debug: Check what we got
        console.log(`HTML length: ${html.length}`);
        const htmlLower = html.toLowerCase();
        const hasReviewSubscore = html.includes('review-subscore') || htmlLower.includes('review-subscore');
        const hasLocation = htmlLower.includes('location');
        console.log(`Has review-subscore: ${hasReviewSubscore}`);
        console.log(`Has location: ${hasLocation}`);
        
        // If we have review-subscore, show a sample
        if (hasReviewSubscore) {
            const subscoreIndex = htmlLower.indexOf('review-subscore');
            if (subscoreIndex !== -1) {
                const sample = html.substring(Math.max(0, subscoreIndex - 100), Math.min(html.length, subscoreIndex + 500));
                console.log(`Sample HTML around review-subscore: ${sample.substring(0, 300)}...`);
            }
        }
        
        // Count review-subscore occurrences
        const subscoreMatches = html.match(/review-subscore/gi);
        console.log(`Found ${subscoreMatches ? subscoreMatches.length : 0} occurrences of "review-subscore"`);
        
        // If we have review-subscore, try to find it in the DOM and wait for it
        if (hasReviewSubscore) {
            try {
                await page.waitForSelector('div[data-testid="review-subscore"]', { timeout: 5000 });
                console.log('Found review-subscore elements in DOM');
            } catch (e) {
                console.log('review-subscore elements not found in DOM (might be in HTML but not rendered)');
            }
        }
        
        // Extract from the DOM directly (more reliable than HTML parsing)
        let domLocationScore = null;
        const locationScoreStartTime = Date.now();
        try {
            console.log('Extracting location score from DOM...');
            const reviewSubscores = await page.$$('div[data-testid="review-subscore"]');
            console.log(`Found ${reviewSubscores.length} review-subscore divs in DOM`);
            
            for (const subscoreDiv of reviewSubscores) {
                const text = await subscoreDiv.evaluate(el => el.textContent || '');
                const textLower = text.toLowerCase();
                
                if (textLower.includes('location')) {
                    console.log('Found location in review-subscore div');
                    console.log(`Div text content: ${text.substring(0, 200)}`);
                    
                    // Method 1: Try to find aria-hidden elements with scores
                    const ariaHiddenEls = await subscoreDiv.$$('[aria-hidden="true"]');
                    console.log(`Found ${ariaHiddenEls.length} aria-hidden elements in location div`);
                    
                    for (const el of ariaHiddenEls) {
                        const elText = await el.evaluate(e => e.textContent || '');
                        const trimmed = elText.trim();
                        console.log(`aria-hidden element text: "${trimmed}"`);
                        
                        const scoreMatch = trimmed.match(/^(\d+\.?\d*)$/);
                        if (scoreMatch) {
                            const score = parseFloat(scoreMatch[1]);
                            if (score >= 1 && score <= 10) {
                                domLocationScore = score;
                                console.log(`✓ Found location score in aria-hidden element: ${domLocationScore}`);
                                break;
                            }
                        }
                    }
                    
                    // Method 2: If not found, look for any child element that contains only a number
                    if (domLocationScore === null) {
                        const allElements = await subscoreDiv.$$('*');
                        for (const el of allElements) {
                            const elText = await el.evaluate(e => {
                                const text = e.textContent || '';
                                // Check if this element contains only the score (no other text)
                                return text.trim();
                            });
                            
                            // Skip if it contains "location"
                            if (elText.toLowerCase().includes('location')) continue;
                            
                            const scoreMatch = elText.match(/^(\d+\.?\d*)$/);
                            if (scoreMatch) {
                                const score = parseFloat(scoreMatch[1]);
                                if (score >= 1 && score <= 10) {
                                    domLocationScore = score;
                                    console.log(`✓ Found location score in child element: ${domLocationScore} (text: "${elText}")`);
                                    break;
                                }
                            }
                        }
                    }
                    
                    // Method 3: Extract number from the div's text content
                    if (domLocationScore === null) {
                        const numbers = text.match(/(\d+\.?\d*)/g);
                        if (numbers) {
                            for (const numStr of numbers) {
                                const score = parseFloat(numStr);
                                if (score >= 1 && score <= 10) {
                                    // Make sure this number isn't part of "location" or other text
                                    const numIndex = text.indexOf(numStr);
                                    const beforeNum = text.substring(Math.max(0, numIndex - 10), numIndex).toLowerCase();
                                    const afterNum = text.substring(numIndex + numStr.length, Math.min(text.length, numIndex + numStr.length + 10)).toLowerCase();
                                    
                                    // Check if it's a standalone number
                                    if (!beforeNum.match(/[a-z]$/) && !afterNum.match(/^[a-z]/) && !beforeNum.includes('location')) {
                                        domLocationScore = score;
                                        console.log(`✓ Found location score in text content: ${domLocationScore}`);
                                        break;
                                    }
                                }
                            }
                        }
                    }
                    
                    if (domLocationScore !== null) break;
                }
            }
        } catch (e) {
            console.log('Error extracting from DOM:', e.message);
            console.error(e);
        }
        const domLocationScoreEndTime = Date.now();
        console.log(`[TIMING] DOM location score extraction took ${domLocationScoreEndTime - locationScoreStartTime}ms`);
        
        // Try HTML extraction as fallback if DOM extraction failed
        let htmlLocationScore = null;
        if (domLocationScore === null) {
            const htmlLocationScoreStartTime = Date.now();
            console.log('DOM extraction failed, trying HTML parsing...');
            htmlLocationScore = extractLocationScore(html);
            const htmlLocationScoreEndTime = Date.now();
            console.log(`[TIMING] HTML location score extraction took ${htmlLocationScoreEndTime - htmlLocationScoreStartTime}ms`);
            if (htmlLocationScore !== null) {
                console.log(`✓ Found location score from HTML parsing: ${htmlLocationScore}`);
            } else {
                console.log('HTML parsing also failed to find location score');
            }
        }
        const locationScoreEndTime = Date.now();
        console.log(`[TIMING] Total location score extraction took ${locationScoreEndTime - locationScoreStartTime}ms`);
        
        const finalScore = domLocationScore !== null ? domLocationScore : htmlLocationScore;
        
        // Extract "Top-rated beach nearby" rating
        let beachRating = null;
        let beachRatingText = null;
        const beachRatingStartTime = Date.now();
        try {
            // Method 1: Search HTML directly (fastest)
            // Find the text first, then extract the number BEFORE it (number comes before text in HTML)
            console.log('Searching for "Top-rated beach nearby" in HTML...');
            const htmlLower = html.toLowerCase();
            let textIndex = htmlLower.indexOf('top-rated beach nearby');
            if (textIndex === -1) {
                textIndex = htmlLower.indexOf('top rated beach nearby');
            }
            
            if (textIndex !== -1) {
                // Get a window BEFORE the text (look backwards up to 200 chars)
                const beforeText = html.substring(Math.max(0, textIndex - 200), textIndex);
                const afterText = html.substring(textIndex, Math.min(html.length, textIndex + 50));
                console.log(`Context before "Top-rated beach nearby": ${beforeText.substring(Math.max(0, beforeText.length - 80))}`);
                console.log(`Context after "Top-rated beach nearby": ${afterText.substring(0, 50)}`);
                
                // Search backwards in the beforeText for the rating number
                // Look for the last number (with optional decimal) that's a valid rating
                // This is more reliable than trying to match patterns with the text
                const numberMatches = [];
                const numberPattern = /(\d+\.?\d*)/g;
                let match;
                while ((match = numberPattern.exec(beforeText)) !== null) {
                    const num = parseFloat(match[1]);
                    if (!isNaN(num) && num >= 4.0 && num <= 10.0) {
                        numberMatches.push({
                            value: num,
                            index: match.index,
                            text: match[1]
                        });
                    }
                }
                
                // Use the last (closest to text) valid number found
                if (numberMatches.length > 0) {
                    const lastMatch = numberMatches[numberMatches.length - 1];
                    beachRating = lastMatch.value;
                    beachRatingText = `Top-rated beach nearby ${beachRating}`;
                    console.log(`✓ Found beach rating: ${beachRating} (from "${lastMatch.text}")`);
                }
            } else {
                console.log('"Top-rated beach nearby" text not found in HTML');
            }
            
            // Method 2: Search DOM if HTML search failed
            if (beachRating === null) {
                console.log('Trying DOM search for "Top-rated beach nearby"...');
                
                // Use evaluate to find elements containing the text and extract number from DOM structure
                const beachRatingFromDOM = await page.evaluate(() => {
                    // Search for text nodes containing the beach text
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        null
                    );
                    let node;
                    while (node = walker.nextNode()) {
                        const text = node.textContent || '';
                        const textLower = text.toLowerCase();
                        if (textLower.includes('top-rated beach nearby') || 
                            textLower.includes('top rated beach nearby')) {
                            
                            // Get the parent element containing this text
                            let element = node.parentElement;
                            while (element && element !== document.body) {
                                // Look for sibling divs or parent that might contain the number
                                const container = element.parentElement || element;
                                const containerText = container.textContent || '';
                                
                                // Find "Top-rated beach nearby" in the container text
                                const textLower = containerText.toLowerCase();
                                let beachIndex = textLower.indexOf('top-rated beach nearby');
                                if (beachIndex === -1) {
                                    beachIndex = textLower.indexOf('top rated beach nearby');
                                }
                                
                                if (beachIndex !== -1) {
                                    // Get text before "Top-rated beach nearby"
                                    const beforeText = containerText.substring(
                                        Math.max(0, beachIndex - 50),
                                        beachIndex
                                    );
                                    
                                    // Find the last number with 1 decimal before the text
                                    const numberMatch = beforeText.match(/(\d+\.\d)(?![0-9])/);
                                    if (numberMatch && numberMatch[1]) {
                                        const num = parseFloat(numberMatch[1]);
                                        if (!isNaN(num) && num >= 4.0 && num <= 10.0) {
                                            return {
                                                rating: num,
                                                matchedText: numberMatch[1],
                                                context: beforeText.substring(Math.max(0, beforeText.length - 30))
                                            };
                                        }
                                    }
                                }
                                
                                element = element.parentElement;
                            }
                        }
                    }
                    return null;
                });
                
                if (beachRatingFromDOM) {
                    console.log(`Found beach rating from DOM: ${beachRatingFromDOM.rating}`);
                    console.log(`Matched text: "${beachRatingFromDOM.matchedText}"`);
                    console.log(`Context: "${beachRatingFromDOM.context}"`);
                    beachRating = beachRatingFromDOM.rating;
                    beachRatingText = `Top-rated beach nearby ${beachRating}`;
                } else {
                    console.log('"Top-rated beach nearby" not found in DOM or number not found');
                }
            }
        } catch (e) {
            console.log('Error extracting beach rating:', e.message);
            console.error(e);
        }
        
        // Validate beachRating - ensure it's a valid number or null
        // "Top-rated beach nearby" should have a reasonable rating (at least 4.0)
        if (beachRating !== null) {
            if (isNaN(beachRating) || beachRating < 4.0 || beachRating > 10) {
                console.log(`Invalid beachRating value: ${beachRating}, setting to null (must be between 4.0 and 10.0)`);
                beachRating = null;
                beachRatingText = null;
            } else {
                // Ensure it's properly formatted (1 decimal place max) - no rounding needed since we only match 1 decimal
                beachRating = parseFloat(beachRating.toFixed(1));
            }
        }
        const beachRatingEndTime = Date.now();
        console.log(`[TIMING] Beach rating extraction took ${beachRatingEndTime - beachRatingStartTime}ms`);
        
        // Extract distance to closest beach - SIMPLE: Wait for content, then extract
        let closestBeachDistance = null;
        let closestBeachName = null;
        const beachExtractionStartTime = Date.now();
        try {
            console.log('Extracting beach distance...');
            
            // Scroll to trigger lazy loading
            await page.evaluate(() => {
                window.scrollTo(0, document.body.scrollHeight);
            });
            await delay(1500);
            
            // Wait for poi-blocks with actual content (like a real browser would)
            try {
                await page.waitForFunction(() => {
                    const blocks = document.querySelectorAll('[data-testid="poi-block"]');
                    for (const block of blocks) {
                        const h3s = block.querySelectorAll('h3');
                        for (const h3 of h3s) {
                            const h3Text = h3.textContent.trim().toLowerCase();
                            if (h3Text.includes('beaches') && 
                                (h3Text.includes('neighbourhood') || h3Text.includes('neighborhood'))) {
                                const list = block.querySelector('ul');
                                if (list) {
                                    const items = list.querySelectorAll('li');
                                    // Check if items have actual text with distances
                                    for (const item of items) {
                                        const text = item.textContent || '';
                                        if (text.trim().length > 5 && text.match(/\d+(?:\.\d+)?\s*(m|km)\b/i)) {
                                            return true; // Content is ready
                                        }
                                    }
                                }
                            }
                        }
                    }
                    return false;
                }, { timeout: 15000, polling: 300 });
            } catch (e) {
                console.log('Wait for beach content timed out, trying anyway...');
            }
            
            // Now extract - content should be ready
            console.log('[TIMING] Extracting beach data from DOM...');
            const extractStartTime = Date.now();
            
            const beachData = await page.evaluate(() => {
                const results = [];
                
                // Find poi-blocks
                const poiBlocks = document.querySelectorAll('[data-testid="poi-block"]');
                
                // Find the one with h3 containing "Beaches in the neighbourhood"
                let beachBlock = null;
                for (const block of poiBlocks) {
                    const h3Elements = block.querySelectorAll('h3');
                    for (const h3 of h3Elements) {
                        const h3Text = h3.textContent.trim().toLowerCase();
                        if (h3Text.includes('beaches') && 
                            (h3Text.includes('neighbourhood') || h3Text.includes('neighborhood'))) {
                            beachBlock = block;
                            break;
                        }
                    }
                    if (beachBlock) break;
                }
                
                if (!beachBlock) {
                    return results;
                }
                
                // Find the ul list within this block
                const beachList = beachBlock.querySelector('ul');
                if (!beachList) {
                    return results;
                }
                
                // Extract from list items
                const items = beachList.querySelectorAll('li');
                for (const item of items) {
                    const itemText = item.textContent || '';
                    const distMatch = itemText.match(/(\d+(?:\.\d+)?)\s*(m|km)\b/i);
                    if (distMatch) {
                        const dist = parseFloat(distMatch[1]);
                        const unit = distMatch[2].toLowerCase();
                        const distIndex = itemText.indexOf(distMatch[0]);
                        let name = itemText.substring(0, distIndex).trim();
                        name = name.replace(/^[:\-•]\s*/, '').trim();
                        
                        if (name.length > 2 && dist > 0 && dist < 1000) {
                            const distMeters = unit === 'km' ? dist * 1000 : dist;
                            results.push({ name, distance: `${dist} ${unit}`, distanceInMeters: distMeters });
                        }
                    }
                }
                
                return results;
            });
            
            const extractEndTime = Date.now();
            console.log(`[TIMING] Beach extraction took ${extractEndTime - extractStartTime}ms`);
            
            if (beachData && beachData.length > 0) {
                beachData.sort((a, b) => a.distanceInMeters - b.distanceInMeters);
                const closest = beachData[0];
                closestBeachDistance = closest.distance;
                closestBeachName = closest.name;
                console.log(`✓ Found closest beach: ${closestBeachName} at ${closestBeachDistance}`);
            } else {
                console.log('No beach matches found');
            }
            
            const beachExtractionTotalTime = Date.now() - beachExtractionStartTime;
            console.log(`[TIMING] Total beach extraction took ${beachExtractionTotalTime}ms`);
        } catch (e) {
            console.log('Error extracting closest beach distance:', e.message);
            console.error(e);
        }
        
        // Extract distance to closest airport - OPTIMIZED: TARGETED DOM TRAVERSAL
        let closestAirportDistance = null;
        let closestAirportName = null;
        const airportExtractionStartTime = Date.now();
        try {
            console.log('Extracting airport distance...');
            
            // Page already scrolled from beach extraction
            
            // Wait for airport block with actual content (like a real browser would)
            try {
                await page.waitForFunction(() => {
                    const blocks = document.querySelectorAll('[data-testid="poi-block"]');
                    for (const block of blocks) {
                        const h3s = block.querySelectorAll('h3');
                        for (const h3 of h3s) {
                            const h3Text = h3.textContent.trim().toLowerCase();
                            if (h3Text.includes('airport') && 
                                (h3Text.includes('closest') || h3Text.includes('nearest'))) {
                                const list = block.querySelector('ul');
                                if (list) {
                                    const items = list.querySelectorAll('li');
                                    // Check if items have actual text with distances
                                    for (const item of items) {
                                        const text = item.textContent || '';
                                        if (text.trim().length > 5 && text.match(/\d+(?:\.\d+)?\s*(km|m)\b/i)) {
                                            return true; // Content is ready
                                        }
                                    }
                                }
                            }
                        }
                    }
                    return false;
                }, { timeout: 10000, polling: 300 });
            } catch (e) {
                console.log('Wait for airport content timed out, trying anyway...');
            }
            
            // Now extract - content should be ready
            console.log('[TIMING] Extracting airport data from DOM...');
            const extractStartTime = Date.now();
            
            const airportData = await page.evaluate(() => {
                const results = [];
                
                // Find poi-blocks
                const poiBlocks = document.querySelectorAll('[data-testid="poi-block"]');
                
                // Find the one with h3 containing "Closest airports"
                let airportBlock = null;
                for (const block of poiBlocks) {
                    const h3Elements = block.querySelectorAll('h3');
                    for (const h3 of h3Elements) {
                        const h3Text = h3.textContent.trim().toLowerCase();
                        if (h3Text.includes('airport') && 
                            (h3Text.includes('closest') || h3Text.includes('nearest'))) {
                            airportBlock = block;
                            break;
                        }
                    }
                    if (airportBlock) break;
                }
                
                if (!airportBlock) {
                    return results;
                }
                
                // Find the ul list within this block
                const airportList = airportBlock.querySelector('ul');
                if (!airportList) {
                    return results;
                }
                
                // Extract from list items
                const items = airportList.querySelectorAll('li');
                for (const item of items) {
                    const itemText = item.textContent || '';
                    const distMatch = itemText.match(/(\d+(?:\.\d+)?)\s*(km|m)\b/i);
                    if (distMatch) {
                        const dist = parseFloat(distMatch[1]);
                        const unit = distMatch[2].toLowerCase();
                        const distIndex = itemText.indexOf(distMatch[0]);
                        let name = itemText.substring(0, distIndex).trim();
                        name = name.replace(/^[:\-•]\s*/, '').trim();
                        
                        if (name.length > 2 && dist > 0 && dist < 500) {
                            const distMeters = unit === 'km' ? dist * 1000 : dist;
                            results.push({ name, distance: `${dist} ${unit}`, distanceInMeters: distMeters });
                        }
                    }
                }
                
                return results;
            });
            
            const extractEndTime = Date.now();
            console.log(`[TIMING] Airport extraction took ${extractEndTime - extractStartTime}ms`);
            
            if (airportData && airportData.length > 0) {
                airportData.sort((a, b) => a.distanceInMeters - b.distanceInMeters);
                const closest = airportData[0];
                closestAirportDistance = closest.distance;
                closestAirportName = closest.name;
                console.log(`✓ Found closest airport: ${closestAirportName} at ${closestAirportDistance}`);
            } else {
                console.log('No airport matches found');
            }
            
            const airportTotalTime = Date.now() - airportExtractionStartTime;
            console.log(`[TIMING] Total airport extraction took ${airportTotalTime}ms`);
        } catch (e) {
            console.log('Error extracting closest airport distance:', e.message);
            console.error(e);
        }
        
        const fetchEndTime = Date.now();
        const totalFetchTime = fetchEndTime - fetchStartTime;
        console.log(`[TIMING] Total fetchPropertyPage time: ${totalFetchTime}ms`);
        
        // Build summary with both location score and beach rating
        let summaryParts = [];
        if (finalScore !== null && !isNaN(finalScore)) {
            summaryParts.push(`Location: ${finalScore}/10`);
        }
        if (beachRating !== null && !isNaN(beachRating)) {
            summaryParts.push(`Beach: ${beachRating}/10`);
        }
        const summary = summaryParts.length > 0 ? summaryParts.join(', ') : 'No beach info found';
        
        console.log(`Returning beach info - locationScore: ${finalScore}, beachRating: ${beachRating}, beachRatingText: ${beachRatingText}, closestBeachDistance: ${closestBeachDistance}, closestAirportDistance: ${closestAirportDistance}`);
        
        return {
            locationScore: finalScore !== null && !isNaN(finalScore) ? finalScore : null,
            beachRating: beachRating !== null && !isNaN(beachRating) ? beachRating : null,
            beachRatingText: beachRatingText,
            closestBeachDistance: closestBeachDistance,
            closestBeachName: closestBeachName,
            closestAirportDistance: closestAirportDistance,
            closestAirportName: closestAirportName,
            summary: summary,
            htmlLength: html.length,
            hasReviewSubscore: hasReviewSubscore,
            debug: {
                htmlLength: html.length,
                hasReviewSubscore: hasReviewSubscore,
                hasLocation: hasLocation,
                extractedFromDom: domLocationScore !== null,
                extractedFromHtml: htmlLocationScore !== null,
                beachRatingFound: beachRating !== null && !isNaN(beachRating),
                closestBeachDistanceFound: closestBeachDistance !== null,
                closestAirportDistanceFound: closestAirportDistance !== null
            }
        };
    } finally {
        await page.close();
    }
}

// Fetch search results page using browser automation
async function fetchSearchResultsPage(searchUrl) {
    // Check if we need to rotate IP due to rate limiting
    if (!browser) {
        await initBrowser();
    }
    
    const page = await browser.newPage();
    
    try {
        // Set realistic browser headers
        await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
        await page.setViewport({ width: 1920, height: 1080 });
        
        // Set extra headers to appear more human-like
        await page.setExtraHTTPHeaders({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        });
        
        console.log(`Fetching search results: ${searchUrl}`);
        const fetchStartTime = Date.now();
        
        // Navigate to the search results page
        let response = null;
        try {
            response = await page.goto(searchUrl, {
                waitUntil: 'domcontentloaded',
                timeout: 30000
            });
            
            // Wait for page to be interactive and content to load
            await page.waitForFunction(() => {
                return document.readyState === 'complete' && 
                       document.body && 
                       document.body.textContent && 
                       document.body.textContent.length > 100;
            }, { timeout: 15000 }).catch(() => {
                console.log('Page readyState check timed out, continuing...');
            });
            
            // Wait a bit more for JavaScript to execute and render content
            await delay(2000);
            
            // Wait for property cards to appear (they're loaded via JavaScript)
            try {
                await page.waitForSelector('div[data-testid="property-card"], div[data-testid="property-card-container"], div.c-sr_property-card, div.sr_item', { 
                    timeout: 15000 
                });
                console.log('Property cards found, waiting for content to load...');
                await delay(2000); // Additional wait for content to fully render
            } catch (e) {
                console.log('Property cards not found, but continuing...');
            }
            
            // Scroll to trigger lazy loading
            await page.evaluate(() => {
                window.scrollTo(0, document.body.scrollHeight / 2);
            });
            await delay(1000);
            await page.evaluate(() => {
                window.scrollTo(0, document.body.scrollHeight);
            });
            await delay(1000);
            await page.evaluate(() => {
                window.scrollTo(0, 0);
            });
            await delay(1000);
            
            // Get the fully rendered HTML
            const html = await page.content();
            
            const fetchEndTime = Date.now();
            console.log(`[TIMING] Search results fetch took ${fetchEndTime - fetchStartTime}ms, HTML length: ${html.length}`);
            
            return html;
        } catch (error) {
            console.error('Error fetching search results page:', error);
            throw error;
        }
    } finally {
        await page.close();
    }
}

// Create HTTP server
const server = http.createServer(async (req, res) => {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    
    if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
    }
    
    const parsedUrl = url.parse(req.url, true);
    
    if (parsedUrl.pathname === '/fetch-property' && req.method === 'GET') {
        const propertyUrl = parsedUrl.query.url;
        
        if (!propertyUrl) {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Missing url parameter' }));
            return;
        }
        
        try {
            const result = await fetchPropertyPage(propertyUrl);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(result));
        } catch (error) {
            console.error('Error fetching property page:', error);
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ 
                error: error.message,
                locationScore: null,
                summary: 'Error fetching page'
            }));
        }
    } else if (parsedUrl.pathname === '/fetch-search-results' && req.method === 'GET') {
        const searchUrl = parsedUrl.query.url;
        
        if (!searchUrl) {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Missing url parameter' }));
            return;
        }
        
        try {
            const html = await fetchSearchResultsPage(searchUrl);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ html: html }));
        } catch (error) {
            console.error('Error fetching search results page:', error);
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ 
                error: error.message,
                html: null
            }));
        }
    } else if (parsedUrl.pathname === '/health' && req.method === 'GET') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ 
            status: 'ok',
            browserInitialized: browser !== null,
            proxiesConfigured: proxies.length,
            currentProxy: getCurrentProxy() ? 'configured' : 'none'
        }));
    } else {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Not found' }));
    }
});

// Initialize browser and start server
initBrowser().then(() => {
    server.listen(PORT, () => {
        console.log(`Browser automation service running on http://localhost:${PORT}`);
        console.log(`Health check: http://localhost:${PORT}/health`);
        console.log(`Fetch property: http://localhost:${PORT}/fetch-property?url=...`);
        console.log(`Fetch search results: http://localhost:${PORT}/fetch-search-results?url=...`);
        if (proxies.length > 0) {
            console.log(`IP rotation enabled with ${proxies.length} proxy(ies)`);
            console.log(`Proxies will rotate automatically on 429 errors`);
        } else {
            console.log(`No proxies configured. Set PROXIES environment variable to enable IP rotation.`);
            console.log(`Example: PROXIES="http://proxy1.com:8080,socks5://proxy2.com:1080" node browser-service.js`);
        }
    });
}).catch((error) => {
    console.error('Failed to initialize browser:', error);
    process.exit(1);
});

// Graceful shutdown
process.on('SIGINT', async () => {
    console.log('\nShutting down...');
    if (browser) {
        await browser.close();
    }
    process.exit(0);
});
