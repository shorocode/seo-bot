import pickle
import numpy as np
from typing import List, Dict, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from pathlib import Path
from config import settings
import logging

logger = logging.getLogger(__name__)

class KeywordClusterer:
    """سیستم خوشه‌بندی کلمات کلیدی با ML"""
    
    def __init__(self):
        self.model_path = Path(settings.MODEL_DIR) / "keyword_cluster.pkl"
        self.vectorizer = TfidfVectorizer(max_features=1000)
        self.model = KMeans(n_clusters=5)
        self._load_model()

    def _load_model(self):
        """بارگذاری مدل از دیسک"""
        if self.model_path.exists():
            with open(self.model_path, 'rb') as f:
                self.vectorizer, self.model = pickle.load(f)

    def train(self, documents: List[str]):
        """آموزش مدل براساس داده‌های جدید"""
        try:
            X = self.vectorizer.fit_transform(documents)
            self.model.fit(X)
            
            with open(self.model_path, 'wb') as f:
                pickle.dump((self.vectorizer, self.model), f)
        except Exception as e:
            logger.error(f"Training failed: {str(e)}")
            raise

    def predict(self, text: str) -> Dict:
        """پیش‌بینی خوشه‌های کلمات کلیدی"""
        try:
            vec = self.vectorizer.transform([text])
            cluster = self.model.predict(vec)[0]
            
            return {
                "cluster": int(cluster),
                "keywords": self._extract_keywords(text)
            }
        except Exception as e:
            logger.error(f"Prediction failed: {str(e)}")
            return {"cluster": -1, "keywords": []}

    def _extract_keywords(self, text: str) -> List[str]:
        """استخراج کلمات کلیدی مهم"""
        # پیاده‌سازی پیشرفته با TF-IDF
        return []

# نمونه Singleton
keyword_clusterer = KeywordClusterer()
