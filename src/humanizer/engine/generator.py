"""Gemini client wrapper using official google-genai SDK with offline mock engine & token simulator."""

from __future__ import annotations

import asyncio
import os
from typing import AsyncIterator, Iterator, Optional

from humanizer.engine.deep import DeepParaphraser
from humanizer.engine.guardrails import replace_banned_buzzwords, sanitize_and_verify_grammar
from humanizer.engine.prompt import estimate_prompt_tokens
from humanizer.models import UsageMetadata

try:
    from google import genai
    from google.genai import types
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]
    GOOGLE_GENAI_AVAILABLE = False


class GeminiGenerator:
    """Handles communication with Gemini Flash Lite endpoints or deterministic offline simulation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash-lite",
        fallback_model: str = "gemini-2.0-flash-lite",
        mock_mode: bool = False,
    ) -> None:
        self.model = model
        self.fallback_model = fallback_model
        resolved_key = api_key or os.getenv("GEMINI_API_KEY")

        # Determine if offline mock mode should be active
        self.mock_mode = mock_mode or not resolved_key or not GOOGLE_GENAI_AVAILABLE
        self._paraphraser = DeepParaphraser()

        self._client: Optional[genai.Client] = None
        if not self.mock_mode and GOOGLE_GENAI_AVAILABLE:
            self._client = genai.Client(api_key=resolved_key)

    def _offline_transform(self, prompt: str, system_instruction: str) -> str:
        """Perform genuine rule-based transformation offline when no API key is present."""
        # Detect tone from system instruction
        tone = "neutral"
        if "conversational" in system_instruction.lower():
            tone = "casual"
        elif "analytical" in system_instruction.lower() or "scholarly" in system_instruction.lower():
            tone = "academic"
        elif "executive" in system_instruction.lower() or "business" in system_instruction.lower():
            tone = "professional"

        # Detect reading level from system instruction
        reading_level = "general"
        if "middle school" in system_instruction.lower():
            reading_level = "middle_school"
        elif "college" in system_instruction.lower():
            reading_level = "college"
        elif "high school" in system_instruction.lower():
            reading_level = "high_school"

        transformed, _ = self._paraphraser.transform(prompt, tone=tone, reading_level=reading_level)
        return transformed

    def generate_sync(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.7,
    ) -> tuple[str, UsageMetadata]:
        """Execute synchronous text generation."""
        if self.mock_mode or self._client is None:
            output_text = self._offline_transform(prompt, system_instruction)
            prompt_tokens = estimate_prompt_tokens(prompt)
            system_tokens = estimate_prompt_tokens(system_instruction)
            completion_tokens = estimate_prompt_tokens(output_text)
            usage = UsageMetadata(
                prompt_tokens=prompt_tokens + system_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + system_tokens + completion_tokens,
                prompt_overhead_tokens=system_tokens,
            )
            return output_text, usage

        # Live Gemini API Call
        try:
            return self._call_gemini_sync(self.model, prompt, system_instruction, temperature)
        except Exception:
            # Fallback to secondary model
            return self._call_gemini_sync(self.fallback_model, prompt, system_instruction, temperature)

    def _call_gemini_sync(
        self,
        model_name: str,
        prompt: str,
        system_instruction: str,
        temperature: float,
    ) -> tuple[str, UsageMetadata]:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
        )
        response = self._client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )
        output_text = response.text or ""
        meta = response.usage_metadata
        p_tokens = meta.prompt_token_count if meta else estimate_prompt_tokens(prompt + system_instruction)
        c_tokens = meta.candidates_token_count if meta else estimate_prompt_tokens(output_text)
        raw_prompt_tokens = estimate_prompt_tokens(prompt)
        overhead = max(0, p_tokens - raw_prompt_tokens)

        usage = UsageMetadata(
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            total_tokens=p_tokens + c_tokens,
            prompt_overhead_tokens=overhead,
        )
        return output_text, usage

    async def generate_async(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.7,
    ) -> tuple[str, UsageMetadata]:
        """Execute asynchronous text generation."""
        if self.mock_mode or self._client is None:
            # Run offline transform in executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            output_text = await loop.run_in_executor(None, self._offline_transform, prompt, system_instruction)
            prompt_tokens = estimate_prompt_tokens(prompt)
            system_tokens = estimate_prompt_tokens(system_instruction)
            completion_tokens = estimate_prompt_tokens(output_text)
            usage = UsageMetadata(
                prompt_tokens=prompt_tokens + system_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + system_tokens + completion_tokens,
                prompt_overhead_tokens=system_tokens,
            )
            return output_text, usage

        # Live Gemini API Call (Async)
        try:
            return await self._call_gemini_async(self.model, prompt, system_instruction, temperature)
        except Exception:
            return await self._call_gemini_async(self.fallback_model, prompt, system_instruction, temperature)

    async def _call_gemini_async(
        self,
        model_name: str,
        prompt: str,
        system_instruction: str,
        temperature: float,
    ) -> tuple[str, UsageMetadata]:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
        )
        response = await self._client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )
        output_text = response.text or ""
        meta = response.usage_metadata
        p_tokens = meta.prompt_token_count if meta else estimate_prompt_tokens(prompt + system_instruction)
        c_tokens = meta.candidates_token_count if meta else estimate_prompt_tokens(output_text)
        raw_prompt_tokens = estimate_prompt_tokens(prompt)
        overhead = max(0, p_tokens - raw_prompt_tokens)

        usage = UsageMetadata(
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            total_tokens=p_tokens + c_tokens,
            prompt_overhead_tokens=overhead,
        )
        return output_text, usage

    def generate_stream_sync(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """Stream chunks synchronously with automatic fallback model recovery."""
        if self.mock_mode or self._client is None:
            full_text = self._offline_transform(prompt, system_instruction)
            # Yield in realistic word-group chunks
            words = full_text.split(" ")
            for i in range(0, len(words), 3):
                chunk = " ".join(words[i : i + 3])
                if i + 3 < len(words):
                    chunk += " "
                yield chunk
            return

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
        )

        has_yielded = False
        try:
            stream = self._client.models.generate_content_stream(
                model=self.model,
                contents=prompt,
                config=config,
            )
            for chunk in stream:
                if chunk.text:
                    has_yielded = True
                    yield chunk.text
        except Exception:
            if not has_yielded and self.fallback_model and self.fallback_model != self.model:
                fallback_stream = self._client.models.generate_content_stream(
                    model=self.fallback_model,
                    contents=prompt,
                    config=config,
                )
                for chunk in fallback_stream:
                    if chunk.text:
                        yield chunk.text
            else:
                raise

    async def generate_stream_async(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream chunks asynchronously (for SSE / FastAPI endpoints) with model fallback."""
        if self.mock_mode or self._client is None:
            full_text = self._offline_transform(prompt, system_instruction)
            words = full_text.split(" ")
            for i in range(0, len(words), 3):
                chunk = " ".join(words[i : i + 3])
                if i + 3 < len(words):
                    chunk += " "
                await asyncio.sleep(0.01)
                yield chunk
            return

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
        )

        has_yielded = False
        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=self.model,
                contents=prompt,
                config=config,
            )
            async for chunk in stream:
                if chunk.text:
                    has_yielded = True
                    yield chunk.text
        except Exception:
            if not has_yielded and self.fallback_model and self.fallback_model != self.model:
                fallback_stream = await self._client.aio.models.generate_content_stream(
                    model=self.fallback_model,
                    contents=prompt,
                    config=config,
                )
                async for chunk in fallback_stream:
                    if chunk.text:
                        yield chunk.text
            else:
                raise
