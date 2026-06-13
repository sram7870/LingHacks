import os


class Settings:
    app_name: str = "LingHacks Scientific Reasoning Backend"
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")
    model_cache_dir: str = os.getenv("MODEL_CACHE_DIR", "./models")
    grobid_url: str = os.getenv("GROBID_URL", "http://localhost:8070")
    science_parse_url: str = os.getenv("SCIENCE_PARSE_URL", "https://api.semanticscholar.org")
    use_ensemble_llm: bool = os.getenv("USE_ENSEMBLE_LLM", "false").lower() in ("1", "true", "yes")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")


settings = Settings()
