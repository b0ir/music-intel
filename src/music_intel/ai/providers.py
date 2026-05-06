PROVIDERS: dict[str, dict] = {
    "anthropic": {
        "models": ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
        "base_url": None,
        "env_key": "ANTHROPIC_API_KEY",
    },
    "openai": {
        "models": ["gpt-4o", "gpt-4o-mini", "o4-mini"],
        "base_url": None,
        "env_key": "OPENAI_API_KEY",
    },
    "deepseek": {
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "base_url": "https://api.deepseek.com",
        "env_key": "DEEPSEEK_API_KEY",
    },
    "openrouter": {
        "models": ["openai/gpt-4o", "anthropic/claude-sonnet-4-6", "google/gemini-2.0-flash-001"],
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
    },
    "nvidia_nim": {
        "models": [
            "meta/llama-3.3-70b-instruct",
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "mistralai/mistral-large-2-instruct",
        ],
        "base_url": "https://integrate.api.nvidia.com/v1",
        "env_key": "NVIDIA_NIM_API_KEY",
    },
    "xai": {
        "models": ["grok-3", "grok-3-mini"],
        "base_url": "https://api.x.ai/v1",
        "env_key": "XAI_API_KEY",
    },
}


def get_models_for_provider(provider: str) -> list[str]:
    return PROVIDERS.get(provider, {}).get("models", [])
