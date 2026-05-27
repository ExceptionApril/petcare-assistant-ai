#!/usr/bin/env python3
"""
Fix RAG system issues — ensures ChromaDB is accessible and working.
Usage: python fix_rag.py
"""
import os
import sys
import logging
import stat
import shutil
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CHROMA_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")


def fix_permissions(path: str) -> bool:
    """Remove read-only attributes and fix permissions recursively."""
    try:
        logger.info(f"Fixing permissions for {path}...")
        for root, dirs, files in os.walk(path):
            for d in dirs:
                dir_path = os.path.join(root, d)
                try:
                    os.chmod(dir_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
                except Exception as e:
                    logger.warning(f"Could not fix dir {dir_path}: {e}")
            for f in files:
                file_path = os.path.join(root, f)
                try:
                    os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                except Exception as e:
                    logger.warning(f"Could not fix file {file_path}: {e}")
        logger.info(f"✅ Permissions fixed for {path}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to fix permissions: {e}")
        return False


def test_write_access(path: str) -> bool:
    """Test if the path is writable."""
    try:
        os.makedirs(path, exist_ok=True)
        test_file = os.path.join(path, ".write_test_12345")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        logger.info(f"✅ Write access confirmed for {path}")
        return True
    except Exception as e:
        logger.error(f"❌ No write access to {path}: {e}")
        return False


def reset_chromadb() -> bool:
    """Reset ChromaDB to a clean state."""
    try:
        if os.path.exists(CHROMA_PATH):
            logger.info(f"Removing {CHROMA_PATH}...")
            # Try to fix permissions first
            fix_permissions(CHROMA_PATH)
            shutil.rmtree(CHROMA_PATH)
            logger.info(f"✅ Removed {CHROMA_PATH}")
        
        # Create fresh directory with proper permissions
        os.makedirs(CHROMA_PATH, exist_ok=True)
        os.chmod(CHROMA_PATH, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        logger.info(f"✅ Created fresh {CHROMA_PATH}")
        return True
    except Exception as e:
        logger.error(f"❌ Reset failed: {e}")
        return False


def test_chromadb_init() -> bool:
    """Test if ChromaDB can be initialized."""
    try:
        logger.info("Testing ChromaDB initialization...")
        import chromadb
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        ef = DefaultEmbeddingFunction()
        collection = client.get_or_create_collection(
            name="test_collection",
            embedding_function=ef,
        )
        logger.info(f"✅ ChromaDB initialized successfully. Collection has {collection.count()} items.")
        return True
    except Exception as e:
        logger.error(f"❌ ChromaDB initialization failed: {e}")
        return False


def main():
    logger.info("🔧 RAG System Diagnostic & Fix Tool")
    logger.info(f"ChromaDB path: {os.path.abspath(CHROMA_PATH)}")
    
    # Step 1: Test current state
    logger.info("\n[1/4] Testing current write access...")
    if not test_write_access(CHROMA_PATH):
        logger.info("Write access failed. Attempting to fix permissions...")
        if not fix_permissions(CHROMA_PATH):
            logger.error("Could not fix permissions. Will attempt reset.")
    
    # Step 2: Try to initialize
    logger.info("\n[2/4] Testing ChromaDB initialization...")
    if test_chromadb_init():
        logger.info("✅ RAG system is working correctly!")
        return 0
    
    # Step 3: Fix permissions more aggressively
    logger.info("\n[3/4] Attempting aggressive permission fix...")
    fix_permissions(CHROMA_PATH)
    if test_chromadb_init():
        logger.info("✅ RAG system is working after permission fix!")
        return 0
    
    # Step 4: Reset everything
    logger.info("\n[4/4] Resetting ChromaDB completely...")
    if not reset_chromadb():
        logger.error("❌ Could not reset ChromaDB")
        return 1
    
    if test_chromadb_init():
        logger.info("✅ RAG system reset successfully!")
        return 0
    else:
        logger.error("❌ RAG system still not working after reset")
        return 1


if __name__ == "__main__":
    exit_code = main()
    if exit_code == 0:
        logger.info("\n✅ All checks passed! You can now run: streamlit run app.py")
    else:
        logger.info("\n❌ There were issues. Check the log above.")
    sys.exit(exit_code)
