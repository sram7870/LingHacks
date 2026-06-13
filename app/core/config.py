from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "LingHacks Scientific Reasoning Backend"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    model_cache_dir: str = "./models"
    grobid_url: str = "http://localhost:8070"
    science_parse_url: str = "https://api.semanticscholar.org"
    use_ensemble_llm: bool = False
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
