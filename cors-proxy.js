#!/usr/bin/env node

/**
 * Simple CORS Proxy Server
 * Run with: node cors-proxy.js
 * Then open index.html in your browser
 */

const http = require('http');
const https = require('https');
const url = require('url');

const PORT = 8080;

const server = http.createServer((req, res) => {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, User-Agent, Accept, Accept-Language');

    if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
    }

    // Parse the target URL from query parameter
    const parsedUrl = url.parse(req.url, true);
    const targetUrl = parsedUrl.query.url;

    if (!targetUrl) {
        res.writeHead(400, { 'Content-Type': 'text/plain' });
        res.end('Missing url parameter');
        return;
    }

    try {
        const target = new URL(targetUrl);
        const protocol = target.protocol === 'https:' ? https : http;

        const options = {
            hostname: target.hostname,
            port: target.port || (target.protocol === 'https:' ? 443 : 80),
            path: target.pathname + target.search,
            method: req.method,
            headers: {
                'User-Agent': req.headers['user-agent'] || 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': req.headers['accept'] || 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': req.headers['accept-language'] || 'en-US,en;q=0.9',
            }
        };

        const proxyReq = protocol.request(options, (proxyRes) => {
            // Copy status code and headers
            res.writeHead(proxyRes.statusCode, {
                'Content-Type': proxyRes.headers['content-type'] || 'text/html',
                'Access-Control-Allow-Origin': '*',
            });

            // Pipe the response
            proxyRes.pipe(res);
        });

        proxyReq.on('error', (err) => {
            console.error('Proxy error:', err);
            res.writeHead(500, { 'Content-Type': 'text/plain' });
            res.end('Proxy error: ' + err.message);
        });

        // Forward request body if present
        req.pipe(proxyReq);
    } catch (err) {
        res.writeHead(400, { 'Content-Type': 'text/plain' });
        res.end('Invalid URL: ' + err.message);
    }
});

server.listen(PORT, () => {
    console.log(`CORS proxy server running on http://localhost:${PORT}`);
    console.log(`Open index.html in your browser to use the search tool.`);
    console.log(`Press Ctrl+C to stop the server.`);
});

