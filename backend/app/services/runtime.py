from app.core.config import Settings
from app.services.pipeline import RAGPipeline
from app.services.providers import Embeddings, HttpTransport, Reranker, ChatModels, LocalModels
from app.services.retrieval import HybridRetriever
from app.services.store import SQLiteDocumentStore
from app.services.vector_index import LocalHybridIndex, MilvusHybridIndex, QdrantHybridIndex

class Runtime:

    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = SQLiteDocumentStore(settings.state_dir / 'ragops.sqlite3', max_active_chunks=settings.max_active_chunks)
        self.store.bind_index_configuration({'embedding': settings.embedding_provider, 'model': settings.embedding_model, 'dimensions': settings.dimensions, 'backend': settings.vector_backend, 'collection': settings.collection, 'destination': settings.milvus_uri if settings.vector_backend == 'milvus' else settings.qdrant_url if settings.vector_backend == 'qdrant' else 'sqlite'})
        self.transport = HttpTransport(settings.timeout_seconds, settings.http_attempts)
        self.embeddings = Embeddings(settings, self.transport)
        self.index = {'local': lambda: LocalHybridIndex(), 'milvus': lambda: MilvusHybridIndex(settings), 'qdrant': lambda: QdrantHybridIndex(settings)}[settings.vector_backend]()
        self.reranker = Reranker(settings, self.transport)
        self.models = LocalModels() if settings.model_provider == 'local' else ChatModels(settings, self.transport)
        self.retriever = HybridRetriever(self.store, self.embeddings, self.index, self.reranker)
        self.pipeline = RAGPipeline(self.store, settings, self.retriever, self.models)
        if settings.graph_engine == 'langgraph':
            # An unavailable selected integration is a startup error, never a silent local substitute.
            from app.services.graph import WorkflowNodes, build_rag_graph
            from app.core.models import Principal
            principal = Principal(user_id='health', name='health', tenant_id='health', department_id='health', role='employee')
            build_rag_graph(WorkflowNodes(self.models, self.retriever, principal, self.store, use_langchain=True), 'langgraph')

    def close(self):
        self.index.close()
        self.transport.close()
