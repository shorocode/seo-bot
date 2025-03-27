import requests
import json
import logging
from typing import Optional, Dict, Any
from functools import lru_cache
from datetime import datetime, timedelta

from config import settings
from services.cache import cache
from utils.logger import logger

class AIService:
    """
    Service for interacting with AI APIs
    Supports multiple AI providers with fallback mechanism
    """
    
    def __init__(self):
        self.providers = settings.AI_PROVIDERS
        self.default_provider = settings.DEFAULT_AI_PROVIDER
        self.timeout = settings.AI_REQUEST_TIMEOUT
        
    @cache.memoize(ttl=3600)  # Cache results for 1 hour
    def analyze_with_ai(self, task: str, text: str, language: str = "fa", **kwargs) -> Optional[Dict[str, Any]]:
        """
        Analyze text using AI APIs with automatic provider fallback
        
        Args:
            task: Type of analysis (e.g., 'readability', 'seo_analysis')
            text: Text to analyze
            language: Language code (default: 'fa' for Persian)
            **kwargs: Additional task-specific parameters
            
        Returns:
            Dict with analysis results or None if failed
        """
        providers_order = [self.default_provider] + [
            p for p in self.providers if p != self.default_provider
        ]
        
        for provider in providers_order:
            try:
                if provider == "openai":
                    result = self._call_openai(task, text, language, **kwargs)
                elif provider == "google_ai":
                    result = self._call_google_ai(task, text, language, **kwargs)
                elif provider == "anthropic":
                    result = self._call_anthropic(task, text, language, **kwargs)
                else:
                    continue
                    
                if result:
                    return result
                    
            except Exception as e:
                logger.warning(f"AI provider {provider} failed for task {task}: {str(e)}")
                continue
                
        logger.error(f"All AI providers failed for task {task}")
        return None
    
    def _call_openai(self, task: str, text: str, language: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Call OpenAI API"""
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Task-specific prompt templates
        prompts = {
            "readability": f"""Analyze this {language} text for readability and provide:
                            1. Readability score (0-100)
                            2. Recommended audience level
                            3. Specific suggestions for improvement
                            Text: {text}""",
            "seo_analysis": f"""Analyze this {language} text for SEO and provide:
                             1. Main keywords
                             2. SEO score (0-100)
                             3. Optimization suggestions
                             Text: {text}"""
        }
        
        payload = {
            "model": kwargs.get("model", "gpt-3.5-turbo"),
            "messages": [{"role": "user", "content": prompts.get(task, text)}],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            return self._parse_ai_response(task, content)
        return None
    
    def _call_google_ai(self, task: str, text: str, language: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Call Google AI API"""
        # Similar implementation for Google AI
        pass
    
    def _call_anthropic(self, task: str, text: str, language: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Call Anthropic Claude API"""
        # Similar implementation for Anthropic
        pass
    
    def _parse_ai_response(self, task: str, response_text: str) -> Dict[str, Any]:
        """Parse raw AI response into structured format"""
        # Implementation varies by task
        if task == "readability":
            return {
                "score": self._extract_value(response_text, "score"),
                "recommended_level": self._extract_value(response_text, "recommended audience level"),
                "suggestions": self._extract_value(response_text, "suggestions for improvement")
            }
        # Other task parsers...
    
    def _extract_value(self, text: str, key: str) -> str:
        """Helper to extract values from AI response"""
        # Implementation depends on AI response format
        return ""

# Singleton instance
ai_service = AIService()
