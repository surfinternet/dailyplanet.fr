"""
Cost calculation utilities for OpenRouter API calls.
Prices in USD per 1M tokens — override via .env.
"""
import os


def usage_cost(model: str, usage: dict) -> float:
    """Calculate cost in USD from OpenRouter usage dict."""
    if not usage:
        return 0.0

    if "perplexity" in model:
        price_in  = float(os.getenv("PRICE_PERPLEXITY_IN",  "3.0"))
        price_out = float(os.getenv("PRICE_PERPLEXITY_OUT", "15.0"))
    else:
        price_in  = float(os.getenv("PRICE_CLAUDE_IN",  "3.0"))
        price_out = float(os.getenv("PRICE_CLAUDE_OUT", "15.0"))

    tokens_in  = usage.get("prompt_tokens", 0)
    tokens_out = usage.get("completion_tokens", 0)
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


def image_cost_usd() -> float:
    return float(os.getenv("PRICE_IMAGE_USD", "0.04"))
