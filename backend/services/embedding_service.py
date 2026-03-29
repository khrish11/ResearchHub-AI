import torch
import numpy as np
from sklearn.preprocessing import normalize

class EmbeddingModel:
    def __init__(self, model_name):
        self.model_name = model_name
        self.model = self.load_model(model_name)

    def load_model(self, model_name):
        # Example loading of a model, e.g., from Hugging Face
        pass

    def embed(self, texts):
        # Process texts using the model
        embeddings = []
        for text in texts:
            # Dummy embedding for example purposes
            embedding = np.random.rand(768)  # Replace this with model inference
            embeddings.append(embedding)
        return np.array(embeddings)

class EmbeddingService:
    def __init__(self, model: EmbeddingModel):
        self.model = model

    def batch_process(self, texts, batch_size=32):
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            embeddings = self.model.embed(batch_texts)
            all_embeddings.append(embeddings)
        return np.vstack(all_embeddings)

if __name__ == '__main__':
    # Example usage
    model = EmbeddingModel('your_model_name')
    service = EmbeddingService(model)
    sample_texts = ['Sample text 1', 'Sample text 2']
    embeddings = service.batch_process(sample_texts)  
    print(embeddings)