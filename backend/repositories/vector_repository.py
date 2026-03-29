"""
Vector Storage Repository for RAG System

Provides abstract interface for storing and retrieving embeddings.
Supports multiple backends (Firestore MVP, Pinecone production).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import hashlib
import uuid
from enum import Enum

from firebase_admin import firestore
from google.cloud.firestore import FieldValue


class ContentType(str, Enum):
    """Types of content that can be embedded"""
    PAPER = "paper"
    SUMMARY = "summary"
    CHECKER = "checker"
    REPORT = "report"

@dataclass
class VectorDocument:
    """Document containing text, embedding, and metadata"""
    id: str
    workspace_id: int
    source_id: str
    source_type: str  # ContentType enum value
    chunk_index: int
    text: str
    embedding: List[float]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    hash: str  # SHA256 of text for deduplication

class VectorStore(ABC):
    """Abstract base class for vector storage backends"""
    @abstractmethod
    async def store(self, doc: VectorDocument) -> str:
        """
        Store a vector document.
        
        Args:
            doc: VectorDocument to store
            
        Returns:
            Document ID
            
        Raises:
            ValueError: If document invalid or workspace access denied
        """
        pass
    
    @abstractmethod
    async def update(self, doc_id: str, doc: VectorDocument) -> None:
        """
        Update an existing vector document.
        
        Args:
            doc_id: ID of document to update
            doc: Updated VectorDocument
            
        Raises:
            ValueError: If document not found or access denied
        """
        pass
    
    @abstractmethod
    async def delete(self, doc_id: str) -> None:
        """
        Delete a vector document.
        
        Args:
            doc_id: ID of document to delete
            
        Raises:
            ValueError: If document not found
        """
        pass
    
    @abstractmethod
    async def get(self, doc_id: str) -> Optional[VectorDocument]:
        """
        Retrieve a vector document by ID.
        
        Args:
            doc_id: ID of document to retrieve
            
        Returns:
            VectorDocument if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        workspace_id: int,
        top_k: int = 5,
        source_type: Optional[str] = None,
    ) -> List[tuple[VectorDocument, float]]:
        """
        Search for similar vectors in workspace.
        
        Args:
            query_embedding: Query vector (same dimension as stored vectors)
            workspace_id: Workspace to search within
            top_k: Number of top results to return
            source_type: Optional filter by content type
            
        Returns:
            List of (VectorDocument, similarity_score) tuples
        """
        pass
    
    @abstractmethod
    async def list_by_workspace(
        self,
        workspace_id: int,
        source_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[VectorDocument]:
        """
        List all vectors in a workspace.
        
        Args:
            workspace_id: Workspace ID
            source_type: Optional filter by content type
            limit: Max results to return
            offset: Pagination offset
            
        Returns:
            List of VectorDocuments
        """
        pass
    
    @abstractmethod
    async def delete_by_source(
        self,
        workspace_id: int,
        source_id: str,
    ) -> int:
        """
        Delete all vectors for a source (paper, summary, etc).
        
        Args:
            workspace_id: Workspace ID
            source_id: Source document ID
            
        Returns:
            Number of documents deleted
        """
        pass
    
    @abstractmethod
    async def count_by_workspace(self, workspace_id: int) -> int:
        """
        Count total vectors in workspace.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Count of vectors
        """
        pass

class FirestoreVectorStore(VectorStore):
    """Firestore-based vector store implementation (MVP)"""
    
    def __init__(self, db):
        """
        Initialize Firestore vector store.
        
        Args:
            db: Firebase Firestore database instance
        """
        self.db = db
        self.collection = db.collection('workspace_vectors')
    
    @staticmethod
    def _compute_hash(text: str) -> str:
        """Compute SHA256 hash of text for deduplication"""
        return hashlib.sha256(text.encode()).hexdigest()
    
    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Similarity score (0.0-1.0)
        """
        import math
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)
    
    async def store(self, doc: VectorDocument) -> str:
        """Store a vector document in Firestore""" 
        if not doc.id:
            doc.id = str(uuid.uuid4())
        
        # Prepare document for Firestore
        data = {
            'id': doc.id,
            'workspace_id': doc.workspace_id,
            'source_id': doc.source_id,
            'source_type': doc.source_type,
            'chunk_index': doc.chunk_index,
            'text': doc.text,
            'embedding': doc.embedding,
            'metadata': doc.metadata,
            'created_at': doc.created_at,
            'updated_at': doc.updated_at,
            'hash': doc.hash,
        }
        
        # Check for duplicates (same workspace + source + hash)
        existing = self.collection.where(
            'workspace_id', '==', doc.workspace_id
        ).where(
            'source_id', '==', doc.source_id
        ).where(
            'hash', '==', doc.hash
        ).limit(1).stream()
        
        for _ in existing:
            # Duplicate found, skip
            raise ValueError(f"Duplicate vector for source {doc.source_id}")
        
        # Store in Firestore
        self.collection.document(doc.id).set(data)
        return doc.id
    
    async def update(self, doc_id: str, doc: VectorDocument) -> None:
        """Update a vector document"""
        data = {
            'text': doc.text,
            'embedding': doc.embedding,
            'metadata': doc.metadata,
            'updated_at': datetime.now(timezone.utc),
        }
        self.collection.document(doc_id).update(data)
    
    async def delete(self, doc_id: str) -> None:
        """Delete a vector document"""
        self.collection.document(doc_id).delete()
    
    async def get(self, doc_id: str) -> Optional[VectorDocument]:
        """Retrieve a vector document by ID"""
        doc = self.collection.document(doc_id).get()
        if not doc.exists:
            return None
        return self._doc_to_vector(doc.to_dict())
    
    async def search(
        self,
        query_embedding: List[float],
        workspace_id: int,
        top_k: int = 5,
        source_type: Optional[str] = None,
    ) -> List[tuple[VectorDocument, float]]:
        """Search for similar vectors using cosine similarity."""
        # Query all vectors in workspace
        query = self.collection.where('workspace_id', '==', workspace_id)
        
        if source_type:
            query = query.where('source_type', '==', source_type)
        
        results = []
        for doc in query.stream():
            data = doc.to_dict()
            stored_embedding = data.get('embedding', [])
            
            # Compute similarity
            similarity = self._cosine_similarity(query_embedding, stored_embedding)
            if similarity > 0.0:  # Threshold
                vector_doc = self._doc_to_vector(data)
                results.append((vector_doc, similarity))
        
        # Sort by similarity and return top-k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    async def list_by_workspace(
        self,
        workspace_id: int,
        source_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[VectorDocument]:
        """List all vectors in workspace"""
        query = self.collection.where('workspace_id', '==', workspace_id)
        
        if source_type:
            query = query.where('source_type', '==', source_type)
        
        query = query.order_by('created_at', direction=firestore.Query.DESCENDING)
        query = query.offset(offset).limit(limit)
        
        results = []
        for doc in query.stream():
            results.append(self._doc_to_vector(doc.to_dict()))
        
        return results
    
    async def delete_by_source(
        self,
        workspace_id: int,
        source_id: str,
    ) -> int:
        """Delete all vectors for a source"""
        query = self.collection.where(
            'workspace_id', '==', workspace_id
        ).where(
            'source_id', '==', source_id
        )
        
        count = 0
        for doc in query.stream():
            doc.reference.delete()
            count += 1
        
        return count
    
    async def count_by_workspace(self, workspace_id: int) -> int:
        """Count total vectors in workspace"""
        query = self.collection.where('workspace_id', '==', workspace_id)
        count = 0
        for _ in query.stream():
            count += 1
        return count
    
    @staticmethod
    def _doc_to_vector(data: Dict[str, Any]) -> VectorDocument:
        """Convert Firestore document to VectorDocument"""
        return VectorDocument(
            id=data.get('id'),
            workspace_id=data.get('workspace_id'),
            source_id=data.get('source_id'),
            source_type=data.get('source_type'),
            chunk_index=data.get('chunk_index'),
            text=data.get('text'),
            embedding=data.get('embedding', []),
            metadata=data.get('metadata', {}),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            hash=data.get('hash'),
        )
