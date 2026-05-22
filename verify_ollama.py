"""Run this FIRST to check Ollama setup: python verify_ollama.py"""
import requests
import subprocess

def verify_ollama():
    print("🔍 Checking Ollama setup...\n")
    
    try:
        # Check Ollama server
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"✅ Ollama running. Available models: {models}")
        
        # Check if nomic-embed-text is pulled
        if any("nomic-embed-text" in m for m in models):
            print("✅ nomic-embed-text embedding model is ready\n")
        else:
            print("⚠️ nomic-embed-text not found. Pulling now...")
            subprocess.run(["ollama", "pull", "nomic-embed-text"], check=True)
            print("✅ nomic-embed-text pulled successfully\n")
        
        return True
    except requests.exceptions.ConnectionError:
        print("❌ Ollama is NOT running!")
        print("   → Open a NEW terminal and run: ollama serve")
        print("   → Then run: ollama pull nomic-embed-text")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = verify_ollama()
    if success:
        print("✅ Ollama is configured. You can now run:")
        print("   python test_rag.py")
        print("   streamlit run app.py")
    exit(0 if success else 1)
