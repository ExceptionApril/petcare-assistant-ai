"""
✅ PHASE 2: RAG Database Management Panel
Provides debugging and introspection into the ChromaDB vector store.
"""

import streamlit as st
import chromadb
import logging
from core.config import Config

logger = logging.getLogger(__name__)


def show_rag_stats():
    """Display RAG database statistics and health"""
    try:
        config = Config()
        client = chromadb.PersistentClient(path=config.chroma_persist_dir)
        collection = client.get_collection("pet_knowledge")
        
        # Get basic stats
        doc_count = collection.count()
        
        # Create metrics row
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📚 Documents", doc_count)
        
        with col2:
            st.metric("🗂️ Collection", "pet_knowledge")
        
        with col3:
            st.metric("💾 Storage", config.chroma_persist_dir)
        
        # Show detailed info
        st.divider()
        st.subheader("Collection Info")
        
        with st.expander("📋 Collection Metadata"):
            if hasattr(collection, 'metadata'):
                st.json(collection.metadata if collection.metadata else {"status": "No metadata"})
            else:
                st.info("Metadata not available for this collection")
        
        # Health check
        st.subheader("🏥 Health Check")
        if doc_count > 0:
            st.success("✅ Database has documents indexed")
        else:
            st.warning("⚠️ Database is empty - run data indexing first")
            
    except FileNotFoundError:
        st.error("❌ ChromaDB not found - Run initialization first")
    except Exception as e:
        st.error(f"❌ Error loading RAG stats: {str(e)}")
        logger.exception("RAG stats error")


def rag_debug_search():
    """Manual RAG query interface for debugging"""
    st.subheader("🔍 Debug Search")
    
    search_query = st.text_input(
        "Search the knowledge base:",
        placeholder="e.g., 'signs of fleas in dogs'",
        key="rag_search_input"
    )
    
    if search_query:
        try:
            config = Config()
            client = chromadb.PersistentClient(path=config.chroma_persist_dir)
            collection = client.get_collection("pet_knowledge")
            
            # Query the database
            results = collection.query(
                query_texts=[search_query],
                n_results=min(5, config.rag_top_k + 2)
            )
            
            # Display results
            if results['documents'] and results['documents'][0]:
                st.success(f"Found {len(results['documents'][0])} results")
                
                for i, (doc, distance) in enumerate(zip(results['documents'][0], results['distances'][0])):
                    with st.expander(f"📄 Result {i+1} (Distance: {distance:.3f})"):
                        st.write(doc[:700])  # Show first 700 chars
                        if len(doc) > 700:
                            st.caption(f"... ({len(doc)} total characters)")
                    
                    st.divider()
            else:
                st.info("No results found for this query")
                
        except FileNotFoundError:
            st.error("❌ ChromaDB not found")
        except Exception as e:
            st.error(f"❌ Search failed: {str(e)}")
            logger.exception("RAG search error")


def show_collection_samples():
    """Show sample documents from the collection"""
    st.subheader("📚 Sample Documents")
    
    num_samples = st.slider("Number of samples to show", 1, 10, 3)
    
    try:
        config = Config()
        client = chromadb.PersistentClient(path=config.chroma_persist_dir)
        collection = client.get_collection("pet_knowledge")
        
        # Get all IDs
        all_data = collection.get()
        
        if not all_data['ids']:
            st.info("No documents in collection")
            return
        
        # Show random samples
        import random
        sample_indices = random.sample(range(len(all_data['ids'])), min(num_samples, len(all_data['ids'])))
        
        for idx in sample_indices:
            doc_id = all_data['ids'][idx]
            doc_content = all_data['documents'][idx]
            
            with st.expander(f"📄 {doc_id}"):
                st.write(doc_content[:500])
                if len(doc_content) > 500:
                    st.caption(f"... ({len(doc_content)} total characters)")
        
    except Exception as e:
        st.error(f"❌ Error loading samples: {str(e)}")
        logger.exception("Sample loading error")


def rag_management_panel():
    """Main RAG management panel - call this from app.py sidebar"""
    st.header("⚙️ RAG Management")
    
    # Tab-based interface
    tab1, tab2, tab3 = st.tabs(["📊 Stats", "🔍 Search", "📚 Samples"])
    
    with tab1:
        show_rag_stats()
    
    with tab2:
        rag_debug_search()
    
    with tab3:
        show_collection_samples()
    
    # Advanced section
    with st.expander("🔧 Advanced"):
        st.write("**ChromaDB Configuration:**")
        
        config = Config()
        st.code(f"""
Persist Directory: {config.chroma_persist_dir}
Data Directory: {config.rag_data_dir}
Top-K Results: {config.rag_top_k}
Collection Name: pet_knowledge
        """, language="text")
        
        if st.button("🔄 Refresh Stats"):
            st.rerun()
