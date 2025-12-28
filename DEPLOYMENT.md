# Deployment Guide

This guide covers deploying the Rotten Tomatoes API to Render. You can also adapt these instructions for other platforms.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Deploy (Render Blueprint)](#quick-deploy-render-blueprint)
3. [Manual Deploy (Step by Step)](#manual-deploy-step-by-step)
4. [Environment Variables](#environment-variables)
5. [Post-Deployment Setup](#post-deployment-setup)
6. [Local Development](#local-development)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before deploying, ensure you have:

- A [Render](https://render.com) account
- A [GitHub](https://github.com) account
- The repository forked/cloned to your GitHub

---

## Quick Deploy (Render Blueprint)

The easiest way to deploy is using Render's Blueprint feature with the included `render.yaml`.

### Step 1: Fork the Repository

1. Go to https://github.com/SilverCrocus/rotten-tomatoes-api
2. Click **Fork** to create your own copy

### Step 2: Deploy to Render

1. Go to https://dashboard.render.com
2. Click **New** → **Blueprint**
3. Connect your GitHub account if not already connected
4. Select your forked repository
5. Click **Apply**

### Step 3: Configure Secrets

After the Blueprint creates your services:

1. Go to your **Web Service** → **Environment**
2. Find `ADMIN_API_KEY` (it will be empty)
3. Generate a secure key:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
4. Paste the generated key and click **Save Changes**

### Step 4: Verify Deployment

Once deployed, test the health endpoint:

```bash
curl https://your-app-name.onrender.com/api/v1/health
```

---

## Manual Deploy (Step by Step)

If you prefer manual setup or need more control:

### Step 1: Create PostgreSQL Database

1. Go to https://dashboard.render.com
2. Click **New** → **PostgreSQL**
3. Configure:
   - **Name:** `rotten-tomatoes-api-db`
   - **Database:** `rt_api`
   - **User:** `rt_api_user`
   - **Region:** Oregon (or closest to you)
   - **Plan:** Starter ($7/month) or Free (limited)
4. Click **Create Database**
5. Wait for status to show **Available**
6. Copy the **Internal Database URL** (you'll need this later)

### Step 2: Create Web Service

1. Click **New** → **Web Service**
2. Connect your GitHub repository
3. Configure:

   | Setting | Value |
   |---------|-------|
   | **Name** | `rotten-tomatoes-api` |
   | **Region** | Oregon (same as database) |
   | **Branch** | `main` |
   | **Runtime** | Python |
   | **Build Command** | `pip install uv && uv pip install --system -r requirements.txt` |
   | **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | **Plan** | Starter ($7/month) |

4. Click **Create Web Service**

### Step 3: Add Environment Variables

Go to your Web Service → **Environment** and add:

| Key | Value | Notes |
|-----|-------|-------|
| `DATABASE_URL` | `postgres://...` | Internal URL from Step 1 |
| `ADMIN_API_KEY` | `your-secure-key` | Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `CACHE_TTL_DAYS` | `7` | How long to cache data |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `DEFAULT_RATE_LIMIT` | `500` | Requests per hour for users |

Click **Save Changes** to trigger a redeploy.

### Step 4: Verify Deployment

```bash
# Check health
curl https://your-app.onrender.com/api/v1/health

# Test movie endpoint (use your admin key)
curl -X GET "https://your-app.onrender.com/api/v1/movie/tt0468569" \
  -H "X-API-Key: your-admin-api-key"
```

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgres://user:pass@host/db` |
| `ADMIN_API_KEY` | Master admin API key | 64-character hex string |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_TTL_DAYS` | `7` | Days before cache expires |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `DEFAULT_RATE_LIMIT` | `500` | Default requests/hour for users |
| `RT_REQUEST_DELAY` | `1.0` | Seconds between RT requests |

### Generating a Secure Admin Key

```bash
# Python
python -c "import secrets; print(secrets.token_hex(32))"

# OpenSSL
openssl rand -hex 32

# Node.js
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

---

## Post-Deployment Setup

### 1. Test the API

```bash
# Health check (no auth required)
curl https://your-app.onrender.com/api/v1/health

# Movie lookup (requires admin key)
curl -X GET "https://your-app.onrender.com/api/v1/movie/tt0468569" \
  -H "X-API-Key: YOUR_ADMIN_API_KEY"
```

### 2. Create User API Keys

Using your admin key, create keys for other users:

```bash
curl -X POST "https://your-app.onrender.com/api/v1/admin/keys" \
  -H "X-API-Key: YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "My App", "rateLimit": 500}'
```

Save the returned `key` value - it's only shown once!

### 3. View Interactive Docs

Visit `https://your-app.onrender.com/docs` for Swagger UI documentation.

---

## Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL (or use Docker)
- [uv](https://docs.astral.sh/uv/) package manager (recommended)

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/SilverCrocus/rotten-tomatoes-api.git
   cd rotten-tomatoes-api
   ```

2. **Create virtual environment:**
   ```bash
   uv venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   uv pip install -r requirements.txt
   ```

4. **Set up environment:**
   ```bash
   cp .env.example .env
   ```

5. **Edit `.env`:**
   ```env
   DATABASE_URL=postgresql://localhost:5432/rt_api
   ADMIN_API_KEY=dev-key-for-testing-only
   CACHE_TTL_DAYS=7
   LOG_LEVEL=DEBUG
   ```

6. **Create database:**
   ```bash
   createdb rt_api
   ```

7. **Run the server:**
   ```bash
   uvicorn app.main:app --reload
   ```

8. **Test locally:**
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

### Using Docker for PostgreSQL

```bash
docker run -d \
  --name rt-api-postgres \
  -e POSTGRES_DB=rt_api \
  -e POSTGRES_USER=rt_api_user \
  -e POSTGRES_PASSWORD=rt_api_pass \
  -p 5432:5432 \
  postgres:16

# Update .env
DATABASE_URL=postgresql://rt_api_user:rt_api_pass@localhost:5432/rt_api
```

---

## Troubleshooting

### Database Connection Failed

**Symptom:** `RuntimeError: Database not initialized`

**Solutions:**
1. Check `DATABASE_URL` is set correctly
2. Ensure database is in same region as web service
3. Use **Internal** database URL, not External
4. Check database status is "Available"

### 401 Unauthorized

**Symptom:** `{"detail": "Invalid or inactive API key"}`

**Solutions:**
1. Check `X-API-Key` header is included
2. Verify key is correct (no extra spaces)
3. Ensure `ADMIN_API_KEY` env var is set
4. Check key hasn't been revoked

### 429 Rate Limited

**Symptom:** `{"detail": "Rate limit exceeded"}`

**Solutions:**
1. Wait for rate limit to reset (1 hour)
2. Use an admin key (no rate limit)
3. Request higher rate limit for your key

### 502 Bad Gateway

**Symptom:** `{"detail": "Failed to scrape Rotten Tomatoes"}`

**Solutions:**
1. RT may be temporarily blocking requests
2. Check logs for specific error
3. Try again after a few minutes
4. Cached data will be returned if available

### Build Failed

**Symptom:** Deploy fails during build

**Solutions:**
1. Check `requirements.txt` exists and is valid
2. Ensure Python version is 3.11+
3. Check Render build logs for specific error

### Checking Logs

View logs in Render dashboard or use:

```bash
# If you have Render CLI installed
render logs --service rotten-tomatoes-api
```

---

## Costs

### Render Pricing (as of 2024)

| Resource | Plan | Cost |
|----------|------|------|
| Web Service | Starter | $7/month |
| PostgreSQL | Starter | $7/month |
| **Total** | | **$14/month** |

Free tier is available but has limitations:
- Services spin down after inactivity
- Limited database storage
- Slower cold starts

---

## Updating the Deployment

### Automatic Updates

With auto-deploy enabled (default), pushing to `main` triggers a redeploy:

```bash
git push origin main
```

### Manual Deploy

1. Go to Render dashboard
2. Select your web service
3. Click **Manual Deploy** → **Deploy latest commit**

---

## Security Recommendations

1. **Never commit `.env` files** - Use `.gitignore`
2. **Rotate admin keys periodically** - Update `ADMIN_API_KEY` env var
3. **Use strong API keys** - 64+ character random strings
4. **Monitor usage** - Check API key request counts
5. **Revoke unused keys** - Use DELETE `/admin/keys/{id}`

---

## Support

- **Issues:** https://github.com/SilverCrocus/rotten-tomatoes-api/issues
- **Render Docs:** https://render.com/docs
- **FastAPI Docs:** https://fastapi.tiangolo.com
