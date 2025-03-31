from typing import Dict, Optional, List, Callable, AsyncIterator, Any
import openai
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import settings
from utils.error_handling import APILimitExceeded, AIProviderError, InvalidAPIResponse
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum, auto
import json
import backoff

logger = logging.getLogger(__name__)

class ProviderType(Enum):
    OPENAI = auto()
    ANTHROPIC = auto()
    GOOGLE = auto()
    FALLBACK = auto()

@dataclass
class AnalysisResult:
    content: str
    provider: ProviderType
    metadata: Dict[str, Any]
    language: str
    is_cached: bool = False

class AIService:
    """Advanced AI Service with Fallback, Retry, and Caching Mechanisms"""

    def __init__(
        self,
        providers: Optional[Dict[str, Callable]] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        circuit_breaker_threshold: int = 5
    ):
        """
        Initialize AI Service
        
        Args:
            providers: Dictionary of provider functions
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts per provider
            circuit_breaker_threshold: Number of failures before disabling a provider
        """
        self.providers = providers or {
            'openai': self._call_openai,
            'anthropic': self._call_anthropic,
            'google': self._call_google_ai
        }
        self.timeout = timeout
        self.max_retries = max_retries
        self.clients = {}
        self.provider_status = {name: True for name in self.providers.keys()}
        self.failure_counts = {name: 0 for name in self.providers.keys()}
        self.circuit_breaker_threshold = circuit_breaker_threshold

    async def setup_clients(self):
        """Initialize all API clients with proper configuration"""
        try:
            self.clients['openai'] = openai.AsyncClient(
                api_key=settings.OPENAI_API_KEY,
                timeout=httpx.Timeout(self.timeout),
                max_retries=self.max_retries
            )
            
            self.clients['http'] = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20
                ),
                transport=httpx.AsyncHTTPTransport(retries=self.max_retries)
            )
            
            # Initialize other provider clients here
            logger.info("All API clients initialized successfully")
            
        except Exception as e:
            logger.error(f"Client initialization failed: {str(e)}")
            raise AIProviderError("Failed to initialize API clients")

    async def close(self):
        """Cleanly close all clients and connections"""
        close_errors = []
        
        for name, client in self.clients.items():
            try:
                if hasattr(client, 'aclose'):
                    await client.aclose()
                elif hasattr(client, 'close'):
                    client.close()
            except Exception as e:
                close_errors.append(f"{name}: {str(e)}")
                logger.warning(f"Error closing {name} client: {str(e)}")
        
        if close_errors:
            logger.error(f"Errors during client closure: {', '.join(close_errors)}")

    @backoff.on_exception(
        backoff.expo,
        (APILimitExceeded, httpx.RequestError),
        max_tries=3,
        jitter=backoff.full_jitter(1)
    )
    async def analyze_content(
        self,
        text: str,
        language: str = "fa",
        preferred_providers: Optional[List[str]] = None,
        **kwargs
    ) -> AnalysisResult:
        """
        Analyze content with automatic fallback and retry logic
        
        Args:
            text: Content to analyze
            language: Language code (default: "fa" for Persian)
            preferred_providers: Ordered list of preferred providers
            **kwargs: Additional provider-specific parameters
            
        Returns:
            AnalysisResult containing the analysis
            
        Raises:
            APILimitExceeded: If all providers fail
            InvalidAPIResponse: If response parsing fails
        """
        errors = []
        providers_order = preferred_providers or list(self.providers.keys())
        
        for provider_name in providers_order:
            if not self.provider_status.get(provider_name, True):
                logger.debug(f"Provider {provider_name} is currently disabled")
                continue
                
            try:
                result = await self._call_provider_with_retry(
                    provider_name,
                    text,
                    language,
                    **kwargs
                )
                
                if result:
                    self._reset_provider_failure_count(provider_name)
                    return AnalysisResult(
                        content=result["analysis"],
                        provider=ProviderType[provider_name.upper()],
                        metadata=result.get("metadata", {}),
                        language=language
                    )
                    
            except Exception as e:
                logger.warning(
                    f"AI provider {provider_name} failed: {str(e)}",
                    exc_info=True
                )
                errors.append(f"{provider_name}: {str(e)}")
                self._handle_provider_failure(provider_name)
                continue
        
        logger.error(f"All providers failed. Errors: {', '.join(errors)}")
        raise APILimitExceeded(
            f"All providers failed. Errors: {', '.join(errors)}"
        )

    async def _call_provider_with_retry(
        self,
        provider_name: str,
        text: str,
        language: str,
        **kwargs
    ) -> Optional[Dict]:
        """Call provider with retry logic"""
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=4, max=10),
            retry=retry_if_exception_type((httpx.RequestError, AIProviderError)),
            reraise=True
        )
        async def _wrapped_call():
            return await self.providers[provider_name](text, language, **kwargs)
            
        return await _wrapped_call()

    def _handle_provider_failure(self, provider_name: str):
        """Update provider failure count and disable if threshold reached"""
        self.failure_counts[provider_name] += 1
        
        if self.failure_counts[provider_name] >= self.circuit_breaker_threshold:
            self.provider_status[provider_name] = False
            logger.warning(
                f"Provider {provider_name} disabled due to repeated failures"
            )

    def _reset_provider_failure_count(self, provider_name: str):
        """Reset failure count for a provider"""
        self.failure_counts[provider_name] = 0
        if not self.provider_status[provider_name]:
            self.provider_status[provider_name] = True
            logger.info(f"Provider {provider_name} re-enabled after successful call")

    async def _call_openai(
        self,
        text: str,
        language: str,
        **kwargs
    ) -> Dict:
        """Call OpenAI API with enhanced error handling"""
        try:
            params = {
                "model": kwargs.get("model", "gpt-4-turbo"),
                "messages": self._build_openai_messages(text, language, **kwargs),
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2000),
                "response_format": {"type": "json_object"} if kwargs.get("json_mode", False) else None
            }
            
            response = await self.clients['openai'].chat.completions.create(**params)
            return self._parse_openai_response(response.choices[0].message.content)
            
        except openai.APIError as e:
            raise AIProviderError(f"OpenAI API error: {str(e)}")
        except json.JSONDecodeError as e:
            raise InvalidAPIResponse(f"Failed to parse OpenAI response: {str(e)}")

    def _build_openai_messages(
        self,
        text: str,
        language: str,
        **kwargs
    ) -> List[Dict[str, str]]:
        """Construct OpenAI message payload"""
        system_prompt = kwargs.get("system_prompt") or self._get_system_prompt(language)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
        
        if kwargs.get("examples"):
            messages.extend(kwargs["examples"])
            
        return messages

    def _get_system_prompt(self, language: str) -> str:
        """Get localized system prompt"""
        prompts = {
            "fa": (
                "شما یک متخصص سئو هستید. تحلیل خود را به صورت ساختاریافته و به زبان فارسی ارائه دهید. "
                "تحلیل باید شامل نکات کلیدی، پیشنهادات بهبود و ارزیابی کیفیت محتوا باشد."
            ),
            "en": (
                "You are an SEO expert. Provide a structured analysis in English. "
                "Include key points, improvement suggestions, and content quality assessment."
            )
        }
        return prompts.get(language, prompts["en"])

    def _parse_openai_response(self, text: str) -> Dict:
        """Parse and validate OpenAI response"""
        try:
            result = json.loads(text) if text.startswith("{") else {"analysis": text}
            if not result.get("analysis"):
                raise InvalidAPIResponse("Missing analysis in response")
            return result
        except json.JSONDecodeError:
            return {"analysis": text}

    async def _call_anthropic(self, text: str, language: str, **kwargs) -> Dict:
        """Call Anthropic API (implementation placeholder)"""
        raise NotImplementedError("Anthropic provider not implemented")

    async def _call_google_ai(self, text: str, language: str, **kwargs) -> Dict:
        """Call Google AI API (implementation placeholder)"""
        raise NotImplementedError("Google AI provider not implemented")

@asynccontextmanager
async def get_ai_service(
    timeout: float = 30.0,
    max_retries: int = 3
) -> AsyncIterator[AIService]:
    """
    Context manager for AI service with proper resource management
    
    Example:
        async with get_ai_service() as ai:
            result = await ai.analyze_content("Some text")
    """
    service = AIService(timeout=timeout, max_retries=max_retries)
    try:
        await service.setup_clients()
        yield service
    except Exception as e:
        logger.error(f"AI service error: {str(e)}")
        raise
    finally:
        await service.close()
