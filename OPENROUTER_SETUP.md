# OpenRouter Setup Guide

## Security First ⚠️

Your exposed API key has been compromised. **Do these immediately:**

1. Go to https://openrouter.ai → Settings → API Keys
2. Click the trash icon to delete the old key
3. Create a new API key and copy it

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create Your `.env` File
1. Copy the `.env` example:
   ```bash
   copy .env.example .env
   ```
2. Open `.env` and paste your NEW OpenRouter API key:
   ```
   OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx...
   ```
3. **NEVER commit `.env` to git!** (It's in `.gitignore`)

### 3. Run the App
```bash
streamlit run app.py
```

## How to Use OpenRouter in Your App

### Frontend JavaScript
```javascript
async function askOpenRouter(prompt) {
  const response = await fetch("http://127.0.0.1:8767/api/openrouter", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ 
      prompt: prompt,
      // Optional: pass API key here, or set in .env
      // apiKey: "sk-or-v1-..."
    })
  });
  
  const data = await response.json();
  return data.text;
}
```

## Available Models on OpenRouter

- `openrouter/auto` - Auto-selects best available model (recommended)
- `gpt-4o` - OpenAI's latest
- `claude-3-sonnet` - Anthropic's Claude
- `mistral-7b` - Open source
- And many more...

See all models: https://openrouter.ai/docs

## Pricing

- Pay-as-you-go with no subscription required
- Competitive rates compared to direct API providers
- Free credits available for testing

## Best Practices

✅ **DO:**
- Store API keys in `.env` files
- Use environment variables: `os.getenv("OPENROUTER_API_KEY")`
- Rotate keys regularly

❌ **DON'T:**
- Hardcode API keys in source code
- Commit `.env` to version control  
- Share API keys in messages or chat
- Use the same key across multiple projects

## Troubleshooting

**"OpenRouter API key missing"**
- Check your `.env` file exists and has `OPENROUTER_API_KEY` set
- Verify the key is valid at https://openrouter.ai/settings

**"Empty response from OpenRouter"**
- Check your OpenRouter account has available credits
- Try the web interface: https://openrouter.ai

**Rate limiting errors**
- Add delays between requests or paginate results
- Check your plan limits at https://openrouter.ai/account

## Documentation

- OpenRouter Docs: https://openrouter.ai/docs
- OpenRouter Models: https://openrouter.ai/docs/models
