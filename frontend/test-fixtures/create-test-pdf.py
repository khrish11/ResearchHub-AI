"""
Create a simple test PDF for RAG validation.
This creates a PDF with research content about semantic retrieval.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch

def create_test_pdf(filename):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    content = """
    Semantic Retrieval with Sentence-Transformers and Firestore Vector Storage
    
    Abstract
    This paper presents a novel approach to semantic retrieval using sentence-transformers embeddings and Firestore vector storage. We demonstrate that a 384-dimensional embedding model combined with persistent vector storage can achieve effective semantic search for research papers.
    
    Introduction
    Research in natural language processing has made significant advances in document understanding and retrieval. Traditional keyword-based approaches are limited in their ability to capture semantic meaning. This paper proposes a hybrid approach that combines modern embedding techniques with persistent vector storage.
    
    Methodology
    Our approach uses the all-MiniLM-L6-v2 sentence-transformers model to generate 384-dimensional embeddings for document chunks. These embeddings are stored in Firestore as vector documents with metadata including workspace_id, paper_id, and chunk_id.
    
    Embedding Generation
    We use the sentence-transformers library to generate embeddings for each document chunk. The embedding model is configured to output 384-dimensional vectors that capture semantic meaning of the text.
    
    Vector Storage
    Vectors are stored in Firestore's workspace_vectors collection with the following structure: embedding (384-dimensional float array), workspace_id (string identifying the workspace), paper_id (string identifying the paper), chunk_id (string identifying the specific chunk), and text (the original text content).
    
    Similarity Calculation
    We use cosine similarity to measure the semantic similarity between query embeddings and stored document vectors. A similarity threshold of 0.2 is used to filter relevant results.
    
    Results
    Our experiments show that the proposed approach achieves effective semantic retrieval with high precision in retrieving relevant document chunks, low false positive rate, good performance on multi-chunk queries, and persistent storage enabling retrieval after system restarts.
    
    Conclusion
    The combination of sentence-transformers embeddings and Firestore vector storage provides an effective solution for semantic document retrieval. The 384-dimensional embeddings capture sufficient semantic information while maintaining computational efficiency.
    
    Future Work
    Future research directions include exploring larger embedding models, optimizing similarity thresholds, implementing multi-modal retrieval, and adding citation verification.
    """
    
    for line in content.split('\n'):
        if line.strip():
            if line.strip().endswith(':'):
                style = styles['Heading2']
            elif line.strip() == line.strip().upper():
                style = styles['Heading1']
            else:
                style = styles['Normal']
            story.append(Paragraph(line.strip(), style))
            story.append(Spacer(1, 0.1 * inch))
    
    doc.build(story)
    print(f"Created test PDF: {filename}")

if __name__ == "__main__":
    create_test_pdf("test-research-paper.pdf")