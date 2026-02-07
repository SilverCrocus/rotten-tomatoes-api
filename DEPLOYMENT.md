# Deployment Guide

This guide covers deploying the Rotten Tomatoes API using **Render** (web service) and **Supabase** (PostgreSQL database).

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Database Setup (Supabase)](#database-setup-supabase)
3. [Web Service Setup (Render)](#web-service-setup-render)
4. [Environment Variables](#environment-variables)
5. [Post-Deployment Setup](#post-deployment-setup)
6. [Local Development](#local-development)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before deploying, ensure you have:

- A [Supabase](https://supabase.com) account (free tier)
- A [Render](https://render.com) account
- A [GitHub](https://github.com) account
- The repository forked/cloned to your GitHub

---

## Database Setup (Supabase)

The database is hosted on Supabase's free tier PostgreSQL. Tables are created automatically when the API starts.

> **Note:** The RT API tables (`rt_cache`, `api_keys`, `list_cache`) live in the **gitrpg** Supabase project alongside the GitRPG tables. They use distinct names and do not conflict.

### Step 1: Get the Connection String

1. Go to https://supabase.com/dashboard
2. Select your project (e.g. **gitrpg**)
3. Go to **Project Settings** → **Database**
4. Under **Connection string**, select **URI**
5. Copy the connection string — it looks like:
   ```
   postgresql://postgres.cjohlwagftjsihexyzzw:[YOUR-PASSWORD]@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
   ```
6. Replace `[YOUR-PASSWORD]` with your database password

> **Important:** Use the **Session Pooler** method (not Direct connection). Direct connection is not IPv4 compatible and won't work from Render.

---

## Web Service Setup (Render)

### Option A: Blueprint Deploy

1. Go to https://dashboard.render.com
2. Click **New** → **Blueprint**
3. Connect your GitHub repository
4. Click **Apply**
5. After creation, go to **Web Service** → **Environment**
6. Set `DATABASE_URL` to your Supabase connection string (from above)
7. Set `ADMIN_API_KEY` to a secure key:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

### Option B: Manual Setup

1. Click **New** → **Web Service**
2. Connect your GitHub repository
3. Configure:

   | Setting | Value |
   |---------|-------|
   | **Name** | `rotten-tomatoes-api` |
   | **Branch** | `main` |
   | **Runtime** | Python |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | **Plan** | Starter ($7/month) |

4. Add environment variables (see [Environment Variables](#environment-variables))
5. Click **Create Web Service**

### Verify Deployment

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
| `DATABASE_URL` | Supabase PostgreSQL connection string (Session Pooler) | `postgresql://postgres.[ref]:[pass]@aws-1-[region].pooler.supabase.com:5432/postgres` |
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
1. Check `DATABASE_URL` is set correctly in Render env vars
2. Ensure the Supabase project is active (not paused)
3. Verify the database password in the connection string is correct
4. Check that SSL is working (the API auto-enables SSL for non-localhost connections)
5. If using Supabase free tier, the project may have auto-paused after 1 week of inactivity — go to the Supabase dashboard and restore it

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

### Current Setup

| Resource | Platform | Plan | Cost |
|----------|----------|------|------|
| Web Service | Render | Starter | $7/month |
| PostgreSQL | Supabase | Free | $0/month |
| **Total** | | | **$7/month** |

**Supabase free tier limits:**
- 500 MB database storage
- Project auto-pauses after 1 week of inactivity (restore from dashboard)
- 2 active projects max

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
