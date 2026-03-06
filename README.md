# 🐾 PetCare Assistant AI

An intelligent AI-powered chatbot that provides pet owners with expert advice on health, nutrition, behavior, and medication for their beloved pets.

## 🌟 Features

- **🏥 Health Advice** - Get expert guidance on pet health symptoms and concerns
- **🍔 Nutrition Guidance** - Learn what to feed your pet based on age and type
- **🎾 Behavior Training** - Receive training tips and behavior management strategies
- **💊 Medication Information** - Understand vaccinations and medication schedules
- **🤖 AI-Powered** - Uses Google Gemini (free tier) for intelligent responses
- **📱 Responsive UI** - Clean, modern interface built with Streamlit

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Google Gemini API key (free) - Get one at [Google AI Studio](https://makersuite.google.com/app/apikey)

### Installation

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run the application:**
```bash
streamlit run app.py
```

3. **Configure API:**
   - Open http://localhost:8501 in your browser
   - Enter your Google Gemini API key in the sidebar
   - Select your pet type and age
   - Start chatting!

## 📁 Project Structure

```
petcare-assistant-ai/
├── app.py                  # Main Streamlit application
├── requirements.txt        # Python dependencies
├── PROGRESS_REPORT.md      # Midterm progress report
├── SAMPLE_TESTS.md         # Test cases and results
├── .env.example           # API key configuration example
└── README.md              # This file
```

## 🧪 Testing

Sample test cases are documented in [SAMPLE_TESTS.md](SAMPLE_TESTS.md) with real API responses for:
- Health advice queries
- Nutrition recommendations
- Behavior training tips
- Medication information
- General pet care

## 📊 Project Status

✅ **Completed:**
- Functional Streamlit UI
- Google Gemini API integration
- Chat interface with history
- Pet context selection
- Quick prompt buttons
- Sample test cases

🔄 **Planned:**
- User authentication
- Persistent database storage
- Multi-language support
- Image upload capabilities


Getting a Free API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the key and paste it in the app's sidebar


