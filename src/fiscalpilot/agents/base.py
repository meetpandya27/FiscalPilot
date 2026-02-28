"""
Base agent — shared logic for all FiscalPilot agents.

Each agent is an LLM-powered specialist that can reason about
a specific domain of financial analysis.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import litellm

if TYPE_CHECKING:
    from fiscalpilot.config import FiscalPilotConfig, LLMConfig

logger = logging.getLogger("fiscalpilot.agents")


class BaseAgent(ABC):
    """Abstract base class for all FiscalPilot agents.

    Subclass this to create new specialized agents. Each agent:
    - Has a system prompt defining its expertise.
    - Can call the LLM to reason about financial data.
    - Returns structured findings/recommendations.
    """

    name: str = "base_agent"
    description: str = "Base financial agent"

    def __init__(self, config: FiscalPilotConfig) -> None:
        self.config = config
        self.llm_config: LLMConfig = config.llm
        self._conversation: list[dict[str, str]] = []

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """The system prompt that defines this agent's expertise."""
        ...

    async def _call_llm(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Call the LLM via litellm (supports any provider)."""
        full_messages = [{"role": "system", "content": self.system_prompt}] + messages

        response = await litellm.acompletion(
            model=self.llm_config.model,
            messages=full_messages,
            temperature=temperature or self.llm_config.temperature,
            max_tokens=max_tokens or self.llm_config.max_tokens,
            api_key=self.llm_config.api_key,
            api_base=self.llm_config.api_base,
            timeout=self.llm_config.timeout,
        )

        content = response.choices[0].message.content or ""
        logger.debug("[%s] LLM response: %s...", self.name, content[:200])
        return content

    async def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        """Run this agent's analysis on the given context.

        Args:
            context: Financial data and metadata for analysis.

        Returns:
            Dict with 'findings', 'recommendations', and 'metadata'.
        """
        prompt = self._build_prompt(context)
        messages = [{"role": "user", "content": prompt}]
        raw_response = await self._call_llm(messages)
        return self._parse_response(raw_response, context)

    @abstractmethod
    def _build_prompt(self, context: dict[str, Any]) -> str:
        """Build the user prompt from the financial context."""
        ...

    @abstractmethod
    def _parse_response(self, response: str, context: dict[str, Any]) -> dict[str, Any]:
        """Parse the LLM response into structured findings."""
        ...
