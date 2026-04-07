# 🚀 Petlio - Secure Deployment Guide

## Overview
This guide walks you through safely deploying **Petlio AI Assistant** to Streamlit Cloud.

---

## ✅ Pre-Deployment Checklist

- [x] Security configuration files created (`.streamlit/config.toml`, `.streamlit/secrets.toml`)
- [x] `.gitignore` protects secrets from being committed
- [x] API key validation implemented
- [x] Input validation (max 5000 chars)
- [x] Rate limiting protections in security rules
- [x] CORS and XSRF protection enabled

---

## 📋 Step 1: Before You Push to GitHub

### 1.1 Verify `.gitignore` is Correct
```bash
# Ensure these lines are in your .gitignore:
.streamlit/secrets.toml
.env
.env.local
```

### 1.2 Verify Secrets are NOT Committed
```bash
# Check what files git would commit
git status

# Should NOT show .streamlit/secrets.toml or .env files
```

### 1.3 Create `.streamlit/secrets.toml` Locally (NOT in repo)
```toml
# .streamlit/secrets.toml - LOCAL ONLY, never commit
OPENROUTER_API_KEY = "sk-your-actual-key-here"
```

### 1.4 Test Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
streamlit run app.py

# Test with your local API key in secrets.toml
```

---

## 🔐 Step 2: Push to GitHub

```bash
# Show remotes
git remote -v

# Add files (excluding secrets)
git add .

# Verify secrets aren't included
git diff --cached --name-only | grep -E "(secrets|\.env)" || echo "✅ No secrets in commit"

# Commit
git commit -m "Add secure deployment configuration"

# Push
git push origin main
```

---

## 🚀 Step 3: Deploy to Streamlit Cloud

### 3.1 Go to Streamlit Cloud
1. Visit **[share.streamlit.io](https://share.streamlit.io)**
2. Click **"New app"**
3. Sign in with GitHub

### 3.2 Select Repository
- **Repository**: `your-username/petcare-assistant-ai`
- **Branch**: `main`
- **Main file path**: `app.py`

### 3.3 Add Secrets via Dashboard

1. Click **"Advanced settings"** in the deployment dialog
2. Scroll down to **"Secrets"**
3. Paste your `.streamlit/secrets.toml` content:

```toml
OPENROUTER_API_KEY = "sk-your-actual-key-here"
```

4. Click **"Deploy"**

---

## 🔍 Step 4: Post-Deployment Verification

### 4.1 Check Deployment Status
- [ ] App appears at `https://share.streamlit.io/your-username/petcare-assistant-ai`
- [ ] No error messages in logs
- [ ] API key is recognized (no "key missing" errors)

### 4.2 View Logs
1. In Streamlit Cloud dashboard, click your app
2. Click **"Settings"** → **"View logs"**
3. Look for any errors or warnings

### 4.3 Test the App
1. Open your deployed app URL
2. Ask a pet care question: *"What should I feed my dog?"*
3. Verify response loads correctly

---

## 🛡️ Security Features Implemented

### ✅ API Key Protection
- Secrets never stored in code
- Environment-specific configuration
- `.gitignore` prevents accidental commits

### ✅ Input Validation
- Max 5000 character limit per message
- Comprehensive prompt injection detection
- Pattern-based threat detection
- Suspicious format detection (base64, hex, XML)

### ✅ Response Safety
- Dangerous phrase filtering
- Policy text never echoed back
- Role-hijacking prevention
- Encoding attack detection

### ✅ Server Hardening
- CSRF protection enabled
- CORS disabled by default
- Error details hidden in production
- Logging set to error-level only

---

## 🔑 API Key Management

### Getting an OpenRouter API Key
1. Visit **[openrouter.ai](https://openrouter.ai)**
2. Sign up / Log in
3. Go to **API Keys** section
4. Create a new key
5. Copy the key starting with `sk-`

### Rotating Your Key (Best Practice)
1. Generate a new API key in OpenRouter dashboard
2. In Streamlit Cloud dashboard, click your app
3. Go to **"Settings"** → **"Secrets"**
4. Update `OPENROUTER_API_KEY` with new value
5. Click **"Save"** (app auto-redeploys)
6. Delete old key from OpenRouter dashboard

---

## 🚨 Troubleshooting

### Issue: "Invalid OpenRouter API key"
- ✅ Verify key in Streamlit Cloud secrets (check for typos, spaces)
- ✅ Ensure key starts with `sk-`
- ✅ Check key is active in OpenRouter dashboard

### Issue: "Connection timeout"
- ✅ Verify internet connection
- ✅ OpenRouter may be down - check [openrouter.ai/status](https://openrouter.ai/status)
- ✅ Try asking a simpler question

### Issue: "Empty response from model"
- ✅ Model may be rate-limited
- ✅ Try again in a few seconds
- ✅ Longer prompts may time out - ask more concisely

### Issue: App not updating after pushing changes
- ✅ Go to Streamlit Cloud dashboard
- ✅ Click your app settings
- ✅ Click **"Reboot app"**
- ✅ Wait 30-60 seconds for redeploy

---

## 📊 Monitoring & Analytics

### View App Usage
- In Streamlit Cloud dashboard, click your app
- Click **"View analytics"** for usage stats

### Monitor Logs
```bash
# SSH into logs (if deployed with specific settings)
# OR check dashboard logs in real-time
```

### Check API Usage
- OpenRouter Dashboard → API Usage section
- Set billing alerts to notify you of high usage

---

## 🔒 Additional Security Best Practices

### 1. Regular Key Rotation
Rotate API keys every **30-90 days**:
```
Month 1: Update secrets.toml
Month 2: Test in staging
Month 3: Update in production
```

### 2. Monitor Failed Requests
Enable error logging to catch injection attempts:
- Check Streamlit Cloud logs regularly
- Set up email alerts for errors

### 3. Rate Limiting (Future Enhancement)
Add rate limiting to prevent abuse:
```python
from datetime import datetime, timedelta

RATE_LIMIT = 10  # requests per minute
user_requests = {}

def check_rate_limit(user_id):
    now = datetime.now()
    if user_id not in user_requests:
        user_requests[user_id] = []
    
    # Remove old requests
    user_requests[user_id] = [
        req for req in user_requests[user_id]
        if now - req < timedelta(minutes=1)
    ]
    
    if len(user_requests[user_id]) >= RATE_LIMIT:
        return False
    
    user_requests[user_id].append(now)
    return True
```

### 4. Disable Error Details in Production
Already enabled in `.streamlit/config.toml`:
```toml
[client]
showErrorDetails = false
```

---

## 📞 Support & Resources

- **Streamlit Docs**: [https://docs.streamlit.io](https://docs.streamlit.io)
- **OpenRouter Docs**: [https://openrouter.ai/docs](https://openrouter.ai/docs)
- **Security Issues**: Report to repo maintainers
- **OpenRouter API Status**: [https://openrouter.ai/status](https://openrouter.ai/status)

---

## ✨ Final Checklist Before Deployment

- [ ] All files pushed to GitHub (except secrets)
- [ ] `.gitignore` prevents secrets from being committed
- [ ] API key added to Streamlit Cloud secrets
- [ ] App deployed successfully
- [ ] Test message sent and responded to
- [ ] No errors in Streamlit Cloud logs
- [ ] Share URL works publicly
- [ ] Security features verified

---

**🎉 Congratulations! Your app is now securely deployed!**
