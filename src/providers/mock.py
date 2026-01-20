"""
Mock Provider for Testing.

Provides deterministic responses for testing the evaluation framework
without incurring API costs. Implements the ModelProvider interface.

Architecture Decision: ADR-009
"""

import hashlib
import time
from typing import Any

from src.providers.base import ModelCapabilities, ModelProvider, ModelResponse


class MockProvider(ModelProvider):
    """Mock provider for testing and development.

    Generates deterministic responses based on input queries.
    Useful for:
    - Testing evaluation harness without API costs
    - CI/CD pipeline validation
    - Development and debugging

    The mock responses are designed to pass quality checks for
    the golden set test cases (keywords, formats).

    Example:
        provider = MockProvider()
        ModelRegistry.register("mock", provider)
        response = await provider.complete(messages)
    """

    # Pre-defined responses for common query patterns
    _RESPONSE_TEMPLATES = {
        "hello": (
            "Hello! I'm an AI assistant here to help you. "
            "How can I assist you today?"
        ),
        "prime": '''def is_prime(n):
    """Check if a number is prime."""
    if n <= 1:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True''',
        "api": (
            "An API (Application Programming Interface) is a way for different "
            "software applications to communicate with each other. "
            "It defines how requests and responses should be structured."
        ),
        "json": '{"name": "Alice Johnson", "age": 32, "city": "San Francisco"}',
        "exercise": """# Benefits of Regular Exercise

1. **Improved cardiovascular health** - Regular exercise strengthens your heart
2. **Better mental health** - Exercise releases endorphins and reduces stress
3. **Increased energy** - Physical activity improves stamina and reduces fatigue
4. **Better sleep quality** - Regular exercise helps regulate sleep patterns
5. **Weight management** - Exercise helps maintain a healthy body weight""",
        "reverse": '''def reverse_string(s):
    """Reverse a string."""
    return s[::-1]''',
        "python": (
            "Python and JavaScript have several key differences: "
            "1) Python uses indentation for code blocks while JavaScript uses braces. "
            "2) Python is strongly typed while JavaScript is weakly typed. "
            "3) Python is often used for backend and data science, "
            "while JavaScript dominates web development."
        ),
        "sandwich": """# How to Make a Peanut Butter and Jelly Sandwich

1. Get two slices of bread
2. Spread peanut butter on one slice of bread
3. Spread jelly on the other slice of bread
4. Press the two slices together
5. Cut diagonally if desired
6. Enjoy your sandwich!""",
        "sql": "SELECT * FROM users WHERE age > 25;",
        "machine learning": (
            "Machine learning is a subset of artificial intelligence where "
            "algorithms learn patterns from data to make predictions or decisions. "
            "The algorithm improves its performance through experience."
        ),
        "programming languages": '[{"name": "Python", "year_created": 1991}, '
        '{"name": "JavaScript", "year_created": 1995}, '
        '{"name": "Rust", "year_created": 2010}]',
        "roses": (
            "Yes, roses need water. This follows from syllogistic reasoning: "
            "All roses are flowers, all flowers need water, "
            "therefore all roses need water."
        ),
        "factorial": '''def factorial(n):
    """Calculate factorial of a number."""
    if n <= 1:
        return 1
    return n * factorial(n - 1)''',
        "version control": (
            "Version control is a system for tracking changes to code over time. "
            "It maintains a complete history of modifications, "
            "allowing developers to revert to previous versions if needed."
        ),
        "web frameworks": (
            "Popular Python web frameworks include: "
            "1) Django - full-featured framework for complex applications, "
            "2) Flask - lightweight microframework for smaller projects, "
            "3) FastAPI - modern, fast framework for building APIs."
        ),
        "palindrome": '''def is_palindrome(s):
    """Check if a string is a palindrome."""
    cleaned = s.lower().replace(" ", "")
    return cleaned == cleaned[::-1]''',
        "rest": (
            "REST (Representational State Transfer) is an architectural style "
            "for designing networked applications. Key principles include: "
            "using HTTP methods for operations, stateless communication, "
            "and treating data as resources with unique URLs."
        ),
        "rectangle": '''class Rectangle:
    """A rectangle with width and height."""

    def __init__(self, width, height):
        self.width = width
        self.height = height

    def area(self):
        """Calculate the area of the rectangle."""
        return self.width * self.height''',
        "multiply": "15 multiplied by 7 equals 105.",
        "divide": "128 divided by 8 equals 16.",
    }

    def __init__(
        self,
        name: str = "mock",
        model_id: str = "mock-v1",
        latency_ms: float = 50.0,
        quality_variance: float = 0.0,
    ) -> None:
        """Initialize mock provider.

        Args:
            name: Provider name for registry.
            model_id: Model identifier.
            latency_ms: Simulated latency in milliseconds.
            quality_variance: Random variance in quality (0-1).
        """
        self._name = name
        self._model_id = model_id
        self._latency_ms = latency_ms
        self._quality_variance = quality_variance

    @property
    def name(self) -> str:
        """Return provider name."""
        return self._name

    @property
    def model_id(self) -> str:
        """Return model identifier."""
        return self._model_id

    def get_capabilities(self) -> ModelCapabilities:
        """Return mock capabilities.

        Returns:
            ModelCapabilities with mock values.
        """
        return ModelCapabilities(
            supports_vision=False,
            supports_function_calling=True,
            supports_streaming=True,
            max_context_tokens=100000,
            max_output_tokens=4096,
            typical_latency_ms=int(self._latency_ms),
            cost_per_1k_input_tokens=0.001,
            cost_per_1k_output_tokens=0.002,
            reasoning_quality=0.9,
            coding_quality=0.9,
            instruction_following=0.9,
        )

    async def complete(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate mock completion.

        Generates deterministic responses based on input content.
        Simulates latency for realistic testing.

        Args:
            messages: Input messages.
            system: System prompt (ignored for mock).
            max_tokens: Max tokens (affects output size estimate).
            temperature: Temperature (affects variance).
            **kwargs: Additional parameters (ignored).

        Returns:
            ModelResponse with mock content.
        """
        # Simulate latency
        start_time = time.time()
        if self._latency_ms > 0:
            time.sleep(self._latency_ms / 1000)

        # Extract query from last user message
        query = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                query = msg.get("content", "").lower()
                break

        # Generate response based on query content
        response_content = self._generate_response(query)

        # Calculate token counts (approximate)
        input_tokens = sum(
            len(msg.get("content", "").split()) * 1.3 for msg in messages
        )
        output_tokens = len(response_content.split()) * 1.3

        latency_ms = (time.time() - start_time) * 1000

        return ModelResponse(
            content=response_content,
            model=self._model_id,
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            latency_ms=latency_ms,
            stop_reason="end_turn",
            metadata={"mock": True},
        )

    def _generate_response(self, query: str) -> str:
        """Generate response based on query content.

        Args:
            query: User query (lowercase).

        Returns:
            Generated response string.
        """
        # Check for known patterns
        for pattern, response in self._RESPONSE_TEMPLATES.items():
            if pattern in query:
                return response

        # Handle math queries
        if "multiply" in query or "multiplied" in query:
            return self._RESPONSE_TEMPLATES["multiply"]
        if "divide" in query or "divided" in query:
            return self._RESPONSE_TEMPLATES["divide"]

        # Default response based on hash of query (sha256 for security)
        hash_val = int(hashlib.sha256(query.encode()).hexdigest()[:8], 16)
        return (
            f"I understand you're asking about: {query[:50]}... "
            f"Here's a helpful response with relevant information. "
            f"The answer involves careful consideration of the context. "
            f"(Mock response #{hash_val % 1000})"
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ):
        """Stream mock completion (simulates streaming).

        Yields response in chunks for streaming interface compatibility.

        Args:
            messages: Input messages.
            system: System prompt.
            max_tokens: Max tokens.
            temperature: Temperature.
            **kwargs: Additional parameters.

        Yields:
            String chunks of the response.
        """
        response = await self.complete(
            messages, system, max_tokens, temperature, **kwargs
        )
        # Simulate streaming by yielding chunks
        words = response.content.split()
        for i in range(0, len(words), 3):
            chunk = " ".join(words[i : i + 3])
            yield chunk + " "
            time.sleep(0.01)  # Small delay between chunks

    async def health_check(self) -> bool:
        """Check provider health.

        Returns:
            Always True for mock provider.
        """
        return True


class MockOpusProvider(MockProvider):
    """Mock provider simulating Claude 4.5 Opus characteristics.

    Higher quality responses with longer latency and higher cost.
    Responses include additional context and keywords for better quality scores.
    """

    # Enhanced responses that include more expected keywords
    _OPUS_RESPONSE_TEMPLATES = {
        "hello": (
            "Hello! I'm an AI assistant here to help you with any questions "
            "or tasks you may have. I can assist with coding, analysis, "
            "writing, research, and much more. How can I help you today?"
        ),
        "prime": '''def is_prime(n):
    """Check if a number is prime.

    A prime number is only divisible by 1 and itself.

    Args:
        n: The number to check.

    Returns:
        True if the number is prime, False otherwise.
    """
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True''',
        "api": (
            "An API (Application Programming Interface) is a standardized way "
            "for different software applications to communicate with each other. "
            "It acts as an interface that defines how requests should be made "
            "and how responses will be returned, enabling seamless integration "
            "between different systems and services."
        ),
        "json": '{"name": "Alice Johnson", "age": 32, "city": "San Francisco", '
        '"occupation": "Software Engineer", "hobbies": ["reading", "hiking"]}',
        "exercise": """# Benefits of Regular Exercise

Regular physical activity is essential for maintaining good health.

1. **Improved cardiovascular health** - Strengthens your heart
2. **Better mental health** - Releases endorphins, reduces stress and anxiety
3. **Increased energy levels** - Improves stamina and reduces fatigue
4. **Better sleep quality** - Helps regulate sleep patterns and improves rest
5. **Weight management** - Helps maintain a healthy body weight

Start with 30 minutes of moderate activity most days for best results.""",
        "reverse": '''def reverse_string(s):
    """Reverse a string efficiently.

    Uses Python slicing for optimal performance.

    Args:
        s: The string to reverse.

    Returns:
        The reversed string.

    Examples:
        >>> reverse_string("hello")
        'olleh'
    """
    return s[::-1]''',
        "machine learning": (
            "Machine learning is a subset of artificial intelligence where "
            "computer algorithms learn patterns from data to make predictions "
            "or decisions without being explicitly programmed. The algorithm "
            "analyzes data patterns and improves its performance through "
            "experience, enabling tasks like image recognition, natural "
            "language processing, and predictive analytics."
        ),
        "programming languages": (
            '[{"name": "Python", "year_created": 1991}, '
            '{"name": "JavaScript", "year_created": 1995}, '
            '{"name": "Rust", "year_created": 2010}]'
        ),
        "roses": (
            "Yes, roses definitely need water. This conclusion follows from "
            "basic syllogistic reasoning: Since all roses are flowers, and all "
            "flowers need water to survive, it logically follows that roses "
            "need water. This is a classic example of deductive reasoning."
        ),
        "rest": (
            "REST (Representational State Transfer) is an architectural style "
            "for designing web APIs. Key principles include: using standard HTTP "
            "methods (GET, POST, PUT, DELETE) for CRUD operations, treating all "
            "data as resources with unique URLs, maintaining stateless communication "
            "between client and server, and using hypermedia as the engine of "
            "application state (HATEOAS)."
        ),
        "version control": (
            "Version control is a system that tracks changes to code and files "
            "over time. It maintains a complete history of all modifications, "
            "allowing developers to review past changes, revert to previous "
            "versions when needed, and collaborate effectively on shared codebases."
        ),
    }

    def __init__(self) -> None:
        """Initialize mock Opus provider."""
        super().__init__(
            name="mock-opus",
            model_id="mock-opus-v1",
            latency_ms=150.0,  # Higher latency like Opus
            quality_variance=0.0,
        )

    def get_capabilities(self) -> ModelCapabilities:
        """Return Opus-like capabilities.

        Returns:
            ModelCapabilities with Opus-like values.
        """
        return ModelCapabilities(
            supports_vision=True,
            supports_function_calling=True,
            supports_streaming=True,
            max_context_tokens=200000,
            max_output_tokens=8192,
            typical_latency_ms=150,
            cost_per_1k_input_tokens=0.015,  # 5x Sonnet
            cost_per_1k_output_tokens=0.075,  # 5x Sonnet
            reasoning_quality=0.98,  # Higher quality
            coding_quality=0.97,
            instruction_following=0.98,
        )

    def _generate_response(self, query: str) -> str:
        """Generate higher quality response for Opus simulation.

        Args:
            query: User query (lowercase).

        Returns:
            Enhanced response string.
        """
        # Check Opus-specific templates first (higher quality)
        for pattern, response in self._OPUS_RESPONSE_TEMPLATES.items():
            if pattern in query:
                return response

        # Fall back to base templates
        return super()._generate_response(query)


def register_mock_providers() -> None:
    """Register mock providers with the registry.

    Convenience function to register all mock providers at once.
    Call this in tests or development environments.

    Example:
        from src.providers.mock import register_mock_providers
        register_mock_providers()
    """
    from src.providers.registry import ModelRegistry

    ModelRegistry.register("mock", MockProvider())
    ModelRegistry.register("mock-opus", MockOpusProvider())
