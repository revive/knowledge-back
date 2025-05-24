from pathlib import Path
import yaml

from openai import AsyncOpenAI

from haystack import Pipeline
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack_integrations.document_stores.chroma import ChromaDocumentStore
from haystack_integrations.components.retrievers.chroma import ChromaEmbeddingRetriever

class AppConfig:
    def __init__(self, args):
        self.config = load_config(args.config_file)
        self.llm_client = AsyncOpenAI(api_key=self.config['api_key'], base_url=self.config['api_base_url'])
        self.query_pipeline = self._init_pipeline(args)

    def _init_pipeline(self, args):
        document_store = ChromaDocumentStore(persist_path=args.store_dir.as_posix())
        retriever = ChromaEmbeddingRetriever(document_store=document_store)
        text_embedder = SentenceTransformersTextEmbedder(
        model=args.model_name, trust_remote_code=True)

        query_pipeline = Pipeline()
        query_pipeline.add_component("text_embedder", text_embedder)
        query_pipeline.add_component("retriever", retriever)
        query_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")

        return query_pipeline

def load_config(config_file: Path):
    config = {
        'api_key': None,
        'api_base_url': None,
        'session_secret_key': "4d4a8434496f9c1041542cb1088c0f5837bc533456c985e1",
        'client_id': None,
        'client_secret': None,
        'redirect_url': None,
        'login_url': 'http://localhost:8833/login',
        'oauth_token_url': "https://account.pandax.sjtu.edu.cn/oauth/token",
        'oauth_authorize_url': "https://account.pandax.sjtu.edu.cn/oauth/authorize",
        'oauth_user_api_url': "https://account.pandax.sjtu.edu.cn/api/v4/user",
        'log_db_path': "./activity_log.db"
    }

    if config_file.exists():
        with open(config_file) as f:
            yaml_data = yaml.safe_load(f)
            config.update(yaml_data)

    if not config['api_key'] or not config['api_base_url']:
        raise ValueError("Please provide api_key or api_base_url for call llm")

    if not config['client_id'] or not config['client_secret'] or not config['redirect_url']:
        raise ValueError(
            "Please provide client_id, client_secret and redirect_uri for authentication")

    return config
