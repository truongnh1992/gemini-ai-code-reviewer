from typing import List
import os
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

class GuidelinesStore:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings()
        self.store = None
        
    def initialize_from_markdown(self, markdown_path: str):
        """Initialize the vector store from a markdown file."""
        with open(markdown_path, 'r') as f:
            content = f.read()
            
        # Split guidelines into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n## ", "\n### ", "\n- ", "\n\n"]
        )
        chunks = text_splitter.split_text(content)
        
        # Create vector store
        self.store = FAISS.from_texts(
            texts=chunks,
            embedding=self.embeddings
        )
        
    def get_relevant_guidelines(self, code_snippet: str, file_path: str) -> List[str]:
        """Retrieve guidelines relevant to the code being reviewed."""
        if not self.store:
            raise ValueError("Vector store not initialized")
            
        # Create search context based on file type and code
        file_type = os.path.splitext(file_path)[1]
        search_context = f"File type: {file_type}\nCode:\n{code_snippet}"
        
        # Get relevant guidelines
        results = self.store.similarity_search(
            search_context,
            k=5  # Retrieve top 5 most relevant guidelines
        )
        
        return [doc.page_content for doc in results] 