"""
Fix ChromaDB conflicts: python reset_chromadb.py
This safely removes and reinitializes the vector store.
"""
import os
import shutil

def reset_chromadb():
    """Reset ChromaDB to a clean state."""
    chroma_path = "./chroma_db"
    
    print(f"🔄 Resetting ChromaDB at {chroma_path}...")
    
    if os.path.exists(chroma_path):
        try:
            shutil.rmtree(chroma_path)
            print(f"✅ Removed {chroma_path}")
        except Exception as e:
            print(f"❌ Error removing {chroma_path}: {e}")
            return False
    
    # Verify removal
    if not os.path.exists(chroma_path):
        print(f"✅ ChromaDB cleaned and ready for fresh initialization")
        return True
    else:
        print(f"❌ Failed to remove {chroma_path}")
        return False

if __name__ == "__main__":
    success = reset_chromadb()
    if success:
        print("\n✅ Ready to use! Start the app with: streamlit run app.py")
    else:
        print("\n❌ Reset failed. Try manually deleting ./chroma_db folder")
    exit(0 if success else 1)
