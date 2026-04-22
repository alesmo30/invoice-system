from dataclasses import dataclass

import chromadb

from rag.embeddings import get_embeddings_batch
from rag.ingestion import Chunk


@dataclass
class SearchResult:
    content: str
    metadata: dict
    score: float
    chunk_id: str


def create_vectorstore(
    collection_name: str, persist_dir: str = "./chroma_db"
) -> chromadb.Collection:
    """Crea o abre una colección en ChromaDB con métrica cosine."""
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def index_chunks(
    collection: chromadb.Collection, chunks: list[Chunk], batch_size: int = 50
) -> int:
    """Indexa chunks en la colección ChromaDB usando upsert. Retorna el número de chunks indexados."""
    total = len(chunks)
    indexed = 0

    for i in range(0, total, batch_size):
        batch = chunks[i : i + batch_size]
        texts = [chunk.content for chunk in batch]
        ids = [chunk.chunk_id for chunk in batch]
        metadatas = [chunk.metadata for chunk in batch]

        embeddings = get_embeddings_batch(texts)

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        indexed += len(batch)
        print(f"  Indexados {indexed}/{total} chunks...")

    return indexed


def load_chunks_from_collection(
    collection: chromadb.Collection, batch_size: int = 500
) -> list[Chunk]:
    """
    Reconstruye la lista de Chunk desde Chroma (ids = chunk_id).
    Necesario para BM25 en HybridRetriever cuando no se vuelve a ejecutar la indexación.
    """
    chunks: list[Chunk] = []
    offset = 0
    while True:
        batch = collection.get(
            include=["documents", "metadatas"],
            limit=batch_size,
            offset=offset,
        )
        ids = batch.get("ids") or []
        if not ids:
            break
        docs = batch.get("documents") or []
        metas = batch.get("metadatas") or []
        for i, cid in enumerate(ids):
            doc = docs[i] if i < len(docs) else None
            meta = metas[i] if i < len(metas) else None
            chunks.append(
                Chunk(
                    content=doc if isinstance(doc, str) else "",
                    metadata=dict(meta) if isinstance(meta, dict) else {},
                    chunk_id=cid,
                )
            )
        offset += len(ids)
    return chunks


def search(
    collection: chromadb.Collection,
    query: str,
    n_results: int = 5,
    where: dict | None = None,
) -> list[SearchResult]:
    """Busca chunks similares a la query. Convierte distancia cosine a similitud."""
    from rag.embeddings import get_embedding

    query_embedding = get_embedding(query)

    kwargs: dict = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    search_results: list[SearchResult] = []
    for i in range(len(results["ids"][0])):
        score = 1 - results["distances"][0][i]  # distancia cosine -> similitud
        search_results.append(
            SearchResult(
                content=results["documents"][0][i],
                metadata=results["metadatas"][0][i],
                score=score,
                chunk_id=results["ids"][0][i],
            )
        )

    return search_results