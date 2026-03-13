from config import settings


def get_llm():
    provider = settings.LLM_PROVIDER

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is missing."
            )

        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0,
        )

    if provider == "anthropic":
        if settings.ANTHROPIC_API_KEY:
            try:
                from langchain_anthropic import ChatAnthropic

                return ChatAnthropic(
                    model=settings.CLAUDE_MODEL,
                    api_key=settings.ANTHROPIC_API_KEY,
                    max_tokens=settings.CLAUDE_MAX_TOKENS,
                    temperature=0,
                )
            except Exception as e:
                if settings.OPENAI_API_KEY:
                    print(
                        f"[llm_factory] Anthropic unavailable, falling back to OpenAI. Error: {e}"
                    )
                else:
                    raise

        if settings.OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                temperature=0,
            )

        raise ValueError(
            "Anthropic failed and no OPENAI_API_KEY fallback is available."
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER='{provider}'. Use 'openai' or 'anthropic'."
    )