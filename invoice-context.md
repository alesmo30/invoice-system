# Project Specification: AI Invoice Manager & Business Journalist

## 1. Project Overview
An intelligent invoice management system designed for an Apple product retailer. The system transforms raw transactional data (SQL) into structured JSON and subsequently into "Natural Language Journals" (Markdown) to be utilized within a Retrieval-Augmented Generation (RAG) architecture.

**Target User:** Store managers and employees querying sales performance, inventory trends, and specific transaction details using natural language.

---

## 2. Hybrid Database Architecture
The system leverages two distinct storage solutions to balance reliability, scalability, and development speed:

* **Relational Database (Cloud): Supabase (PostgreSQL)**
    * **Purpose:** Serves as the "Source of Truth" for all structured data (Employees, Products, Invoices, and Line Items).
    * **Reasoning:** Provides high availability, data integrity, and seamless cloud access for the transactional core of the application.
* **Vector Store (Local): ChromaDB**
    * **Purpose:** Stores the embeddings of the "Daily Journals" generated during Phase 0.
    * **Reasoning:** Offers low latency, zero cost, and efficient local prototyping for the RAG pipeline.

---

## 3. Phase 0: Data Generation & Seed Pipeline
The current priority is establishing a high-quality 30-day "Seed" dataset and the corresponding transformation pipeline.

### Workflow:
1.  **Seed SQL:** Populate Supabase with 30 days of simulated Apple Store transactions (5 employees, diverse product catalog).
2.  **Extraction:** A Python script queries Supabase to group daily transactions into structured JSON objects.
3.  **Journaling:** An LLM (via Groq/Ollama) converts the JSON data into professional narrative Markdown files (`/data/journals/*.md`).
4.  **Vectorization:** These Markdown files are chunked and ingested into the local ChromaDB instance for semantic search.

---

## 4. Technical Stack
* **Backend:** Python 3.11+
* **Transactional DB:** Supabase (PostgreSQL)
* **Vector DB:** ChromaDB (Local)
* **Orchestration:** LangChain / LangGraph
* **LLMs:** Claude 3.5/3.7 (for Coding and Architecture) and Groq/Llama 3 (for high-speed data processing)
* **Data Contracts:** Pydantic for strict JSON and Metadata schema enforcement

---

## 5. Implementation Roadmap
* **Phase 0 (Current):** Database seeding and automated Journal generation.
* **Phase 1:** RAG Implementation (ChromaDB integration + Retrieval logic).
* **Phase 2:** Multi-Agent System (Extractor Agent & Auditor Agent roles).
* **Phase 3:** Tool Integration (Dynamic Chart Generation & Currency Exchange API).
* **Phase 4:** Evaluation (Quantitative metrics for Faithfulness and Extraction Accuracy).

---

## 6. Instructions for AI Assistant
* **Context Awareness:** Always distinguish between relational queries (Supabase) and semantic/vector searches (ChromaDB).
* **Data Integrity:** When generating journals, ensure the narrative data strictly matches the numerical records stored in Supabase.
* **Modular Design:** Implement separate client classes for Supabase and ChromaDB to ensure the system remains decoupled and maintainable.
* **Domain Expertise:** Use realistic Apple Store product names (e.g., iPhone 15 Pro, MacBook Pro M3, Apple Watch Ultra 2) and accurate pricing in all examples and test data.
