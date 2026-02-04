import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not key:
            continue
        # Always let .env override these local path/telemetry settings
        if key in {"MEM0_DIR", "QDRANT_PATH", "MEM0_TELEMETRY"}:
            os.environ[key] = val
        elif key not in os.environ:
            os.environ[key] = val

    # Resolve relative paths to the project root for local storage
    mem0_dir = os.getenv("MEM0_DIR")
    if mem0_dir and not os.path.isabs(mem0_dir):
        os.environ["MEM0_DIR"] = str(PROJECT_ROOT / mem0_dir)

    qdrant_path = os.getenv("QDRANT_PATH")
    if qdrant_path and not os.path.isabs(qdrant_path):
        os.environ["QDRANT_PATH"] = str(PROJECT_ROOT / qdrant_path)


load_dotenv()


def get_config() -> dict:

    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    llm_model = os.getenv("SILICONFLOW_LLM_MODEL", "deepseek-ai/DeepSeek-V3.2")
    embed_model = os.getenv("SILICONFLOW_EMBED_MODEL", "Qwen/Qwen3-Embedding-8B")
    embed_dims = int(os.getenv("SILICONFLOW_EMBED_DIMS", "4096"))

    qdrant_path = os.getenv("QDRANT_PATH", "/Users/lvxiaoer/Documents/New project/.qdrant")
    qdrant_host = os.getenv("QDRANT_HOST")
    qdrant_port = os.getenv("QDRANT_PORT")
    collection = os.getenv("MEM0_COLLECTION", "physics_mem")

    qdrant_config = {
        "collection_name": collection,
        "embedding_model_dims": embed_dims,
    }
    if qdrant_path:
        qdrant_config["path"] = qdrant_path
        qdrant_config["on_disk"] = True
    if qdrant_host and qdrant_port:
        qdrant_config["host"] = qdrant_host
        qdrant_config["port"] = int(qdrant_port)

    return {
        "vector_store": {
            "provider": "qdrant",
            "config": qdrant_config,
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": embed_model,
                "openai_base_url": base_url,
                "embedding_dims": embed_dims,
            },
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": llm_model,
                "openai_base_url": base_url,
                "temperature": 0.2,
            },
        },
    }
