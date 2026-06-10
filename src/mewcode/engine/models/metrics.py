"""API timing and token metrics models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .message import TokenUsage


def _ms(seconds: float) -> int:
    return max(0, int(round(seconds * 1000)))


@dataclass
class ApiCallMetrics:
    """Metrics for one model API call."""

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    ttft_ms: Optional[int] = None
    latency_ms: Optional[int] = None
    output_tokens_per_second: Optional[float] = None
    had_usage: bool = False
    had_first_token: bool = False

    @classmethod
    def from_timing(
        cls,
        *,
        usage: Optional[TokenUsage],
        started_at: float,
        completed_at: float,
        first_token_at: Optional[float],
    ) -> "ApiCallMetrics":
        latency_ms = _ms(completed_at - started_at)
        ttft_ms: Optional[int] = None
        speed: Optional[float] = None
        had_first_token = first_token_at is not None

        if first_token_at is not None:
            ttft_ms = _ms(first_token_at - started_at)

        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None
        total_tokens: Optional[int] = None
        had_usage = usage is not None

        if usage is not None:
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens
            if (
                first_token_at is not None
                and usage.completion_tokens > 0
                and completed_at > first_token_at
            ):
                speed = usage.completion_tokens / (completed_at - first_token_at)

        return cls(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            ttft_ms=ttft_ms,
            latency_ms=latency_ms,
            output_tokens_per_second=speed,
            had_usage=had_usage,
            had_first_token=had_first_token,
        )


@dataclass
class MetricsAggregate:
    """Session-level API metrics aggregate."""

    api_call_count: int = 0
    usage_call_count: int = 0
    speed_sample_count: int = 0
    output_tokens_per_second_sum: float = 0.0
    ttft_sample_count: int = 0
    ttft_ms_sum: int = 0
    latency_sample_count: int = 0
    latency_ms_sum: int = 0

    def add_call(self, metrics: ApiCallMetrics) -> None:
        self.api_call_count += 1
        if metrics.had_usage:
            self.usage_call_count += 1
        if metrics.output_tokens_per_second is not None:
            self.speed_sample_count += 1
            self.output_tokens_per_second_sum += metrics.output_tokens_per_second
        if metrics.ttft_ms is not None:
            self.ttft_sample_count += 1
            self.ttft_ms_sum += metrics.ttft_ms
        if metrics.latency_ms is not None:
            self.latency_sample_count += 1
            self.latency_ms_sum += metrics.latency_ms

    @property
    def average_output_tokens_per_second(self) -> Optional[float]:
        if self.speed_sample_count == 0:
            return None
        return self.output_tokens_per_second_sum / self.speed_sample_count

    @property
    def average_ttft_ms(self) -> Optional[float]:
        if self.ttft_sample_count == 0:
            return None
        return self.ttft_ms_sum / self.ttft_sample_count

    @property
    def average_latency_ms(self) -> Optional[float]:
        if self.latency_sample_count == 0:
            return None
        return self.latency_ms_sum / self.latency_sample_count

    def to_dict(self) -> dict:
        return {
            "api_call_count": self.api_call_count,
            "usage_call_count": self.usage_call_count,
            "speed_sample_count": self.speed_sample_count,
            "output_tokens_per_second_sum": self.output_tokens_per_second_sum,
            "ttft_sample_count": self.ttft_sample_count,
            "ttft_ms_sum": self.ttft_ms_sum,
            "latency_sample_count": self.latency_sample_count,
            "latency_ms_sum": self.latency_ms_sum,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "MetricsAggregate":
        if not data:
            return cls()
        return cls(
            api_call_count=int(data.get("api_call_count", 0) or 0),
            usage_call_count=int(data.get("usage_call_count", 0) or 0),
            speed_sample_count=int(data.get("speed_sample_count", 0) or 0),
            output_tokens_per_second_sum=float(
                data.get("output_tokens_per_second_sum", 0.0) or 0.0
            ),
            ttft_sample_count=int(data.get("ttft_sample_count", 0) or 0),
            ttft_ms_sum=int(data.get("ttft_ms_sum", 0) or 0),
            latency_sample_count=int(data.get("latency_sample_count", 0) or 0),
            latency_ms_sum=int(data.get("latency_ms_sum", 0) or 0),
        )


@dataclass
class MetricsSnapshot:
    """TUI-facing metrics snapshot."""

    token_usage: Optional[TokenUsage] = None
    api_metrics: MetricsAggregate = field(default_factory=MetricsAggregate)
    last_call: Optional[ApiCallMetrics] = None
