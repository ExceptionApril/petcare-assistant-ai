#!/usr/bin/env bash
# 🚀 Petlio Deployment Script for Streamlit Cloud

echo "🔐 Petlio AI Assistant - Secure Deployment Setup"
echo "=================================================="
echo ""

# Check 1: Verify .gitignore exists and has secrets
echo "[1/6] Checking .gitignore for secrets protection..."
if grep -q "\.streamlit/secrets\.toml" .gitignore && grep -q "\.env" .gitignore; then
    echo "✅ .gitignore properly configured"
else
    echo "⚠️  WARNING: Ensure .gitignore includes .streamlit/secrets.toml and .env"
fi

# Check 2: Verify config files exist
echo ""
echo "[2/6] Checking Streamlit config files..."
if [ -f ".streamlit/config.toml" ]; then
    echo "✅ .streamlit/config.toml exists"
else
    echo "⚠️  ERROR: .streamlit/config.toml not found"
fi

if [ -f ".streamlit/secrets.toml" ]; then
    echo "✅ .streamlit/secrets.toml exists (local only)"
else
    echo "⚠️  WARNING: .streamlit/secrets.toml not found - create locally for development"
fi

# Check 3: Verify no secrets in Git
echo ""
echo "[3/6] Checking for accidentally committed secrets..."
if git log -p | grep -i "openrouter.*api.*key\|sk-" > /dev/null; then
    echo "⚠️  ERROR: API keys found in Git history!"
else
    echo "✅ No API keys in Git history"
fi

# Check 4: Verify dependencies
echo ""
echo "[4/6] Checking requirements.txt..."
if grep -q "streamlit" requirements.txt && grep -q "openai" requirements.txt; then
    echo "✅ Required dependencies listed"
else
    echo "⚠️  ERROR: Missing required dependencies"
fi

# Check 5: Verify app.py security features
echo ""
echo "[5/6] Checking app.py for security features..."
if grep -q "_normalize_user_prompt" app.py && \
   grep -q "_looks_like_prompt_injection" app.py && \
   grep -q "_validate_response_safety" app.py; then
    echo "✅ Security features implemented"
else
    echo "⚠️  ERROR: Security features missing from app.py"
fi

# Check 6: Summary
echo ""
echo "[6/6] Pre-deployment summary:"
echo "================================"
echo ""
echo "✅ Files to commit to GitHub:"
for file in app.py design.py requirements.txt README.md .streamlit/config.toml .gitignore DEPLOYMENT_GUIDE.md SECURITY_IMPLEMENTATION.md img/; do
    if [ -e "$file" ]; then
        echo "  • $file"
    fi
done

echo ""
echo "🔒 Files to keep locally (NEVER commit):"
echo "  • .streamlit/secrets.toml"
echo "  • .env"
echo ""

echo "🚀 Deployment Instructions:"
echo "1. Ensure all checks above show ✅"
echo "2. Push to GitHub:"
echo "   git add ."
echo "   git commit -m 'Add secure Streamlit deployment configuration'"
echo "   git push origin main"
echo ""
echo "3. Deploy to Streamlit Cloud:"
echo "   • Go to https://share.streamlit.io"
echo "   • Click 'New app'"
echo "   • Select your repo, branch, and app.py"
echo "   • Add secrets in Advanced settings:"
echo "     OPENROUTER_API_KEY = sk-your-key-here"
echo ""
echo "4. Test your deployment:"
echo "   • Visit your app URL"
echo "   • Ask: 'What should I feed my dog?'"
echo "   • Verify response loads correctly"
echo ""
echo "✨ All done! Your app is ready for secure deployment."
