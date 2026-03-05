# Global Edge Deployment Guide

## Components
1. CDN/WAF: Cloudflare (or equivalent)
2. Reverse proxy: Nginx (`deploy/nginx/researchhub.conf`)
3. Origin services:
   - Frontend: Vite build served by app/web server
   - Backend: FastAPI on private network

## Required Controls
1. TLS enforced end-to-end (minimum TLS 1.2)
2. HSTS enabled (`max-age=31536000; includeSubDomains; preload`)
3. WAF managed rules + custom abuse rules (`deploy/cloudflare/waf-rules.json`)
4. DDoS protection enabled at CDN edge
5. Origin firewall only allows CDN egress IP ranges

## Deployment Steps
1. Deploy origin services and confirm `/health/ready`.
2. Apply Nginx configuration and reload.
3. Configure CDN DNS proxy and SSL mode (`Full (strict)`).
4. Enable WAF, bot management, and rate-limit rules.
5. Validate:
   - TLS grade A
   - HSTS headers present
   - API and app routes function behind edge
