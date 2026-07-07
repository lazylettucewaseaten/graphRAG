# CodeRAG and GraphRAG System

graphRAG is an intelligent Repository Analysis and Query System designed for C++ codebases. It combines Retrieval-Augmented Generation (RAG) with Graph-based knowledge representation to allow developers to semantically query their codebase, identify code dependencies, and evaluate the "impact radius" of potential changes.
## YouTube Link : 
https://youtu.be/IgHSRF05rcA
## Features

* **Semantic Code Search:** Uses `jina-embeddings-v2-base-code` to generate embeddings of code chunks for accurate semantic similarity search.
* **Graph Knowledge Base:** Parses C++ Abstract Syntax Trees (AST) using Tree-sitter to build a knowledge graph of files, classes, and function calls.
* **Impact Radius Analysis:** Integrates with Neo4j to trace forward and reverse dependencies, identifying which functions and structures will be impacted by modifications.
* **Context-Aware Conversational AI:** Utilizes Google's Gemini models to process vector search results and knowledge graph data, providing concise, context-aware answers to user queries.
* **Follow-up Detection:** Automatically detects conversational follow-ups and maintains a persistent context window to carry over relevant context from previous queries.
* **Automated Environment Provisioning:** Uses Docker to seamlessly spin up MongoDB Atlas Local for vector search capabilities without requiring a cloud connection.

## Prerequisites

Ensure you have the following installed on your system before proceeding:
* Python 3.10+
* Docker (must be running for MongoDB Atlas Local)
* Git
* Neo4j

## Installation and Setup

**1. Clone or Enter the Project Directory**
```bash
cd /path/to/graphRAG
```

**2. Configure Environment Variables**
A `.env` file is required at the root of the project to manage API keys and database connections. Create a `.env` file and populate it with the following configuration:

```env
MONGO_URI=mongodb://localhost:27017/?directConnection=true
MONGO_DB=graphrag
MONGO_COLLECTION=graphrag

NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
NEO4J_DATABASE=graphrag

GEMINI_API_KEY=your_google_gemini_api_key
LLM_MODEL=gemini-2.5-flash

EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code
DEVICE=cuda # or cpu
```
*Note: Ensure you have your Neo4j service running with the credentials specified in the `.env` file.*

**3. Setup Virtual Environment and Dependencies**
```bash
python3 -m venv rag
source rag/bin/activate
pip install -r requirements.txt
```

**4. Run the Initialization Script**
The `script.sh` automates the process of cloning a target C++ repository, spinning up the Docker-based MongoDB Atlas Local instance, performing the AST analysis, generating vector embeddings, and loading the graph data into Neo4j.

```bash
bash script.sh
```
When prompted, provide the Git URL of the repository you wish to analyze.

## Usage

Once the initialization script has completed successfully, you can query the repository using the interactive Command Line Interface.

```bash
bash cli.sh
```

**Example Queries:**
* "If I change the encrypt function, what other files will be impacted?"
* "Explain how the stat structure is used here." (Follow-up query)

To exit the CLI, press `Ctrl+C` twice.


## Detailed Pipeline Workflow

The complete end-to-end pipeline operates in the following sequential stages:

1. **Repository Ingestion:** The process begins by taking a target GitHub repository URL and fetching the codebase.
2. **AST Generation:** Tree-sitter runs on the codebase to generate an Abstract Syntax Tree (AST), capturing the structural syntax and code elements.
3. **Graph Construction:** The AST is filtered and processed to extract semantic nodes and relationships, which are then used to construct a knowledge graph stored in a Neo4j database.
4. **Vector Embedding Generation:** In `ingestion.py`, the code chunks are processed to generate vector embeddings using **Jina Embeddings** (`jina-embeddings-v2-base-code`). 
   * *Internally, Jina Embeddings v2 utilizes **JinaBERT**—a modified BERT architecture equipped with ALiBi (Attention with Linear Biases)—which allows it to efficiently handle an extended context window of up to 8,192 tokens for long code comprehension.*
5. **Vector Storage:** The generated vector embeddings are subsequently stored in a local instance of MongoDB Atlas, which is spun up seamlessly via Docker.
6. **Query Pre-processing:** When a user submits a query, the system first evaluates the conversational context to determine whether the query is a follow-up to previous interactions.
7. **Prompt Embedding & Vector Search:** The user's query prompt is then converted into a vector embedding. The system queries the local MongoDB Atlas vector store using the prompt embedding to retrieve the most semantically relevant code chunks.
8. **Graph Traversal (Impact Radius):** The retrieved chunks are used as entry points to traverse the Neo4j knowledge graph. The system finds the affected interconnected nodes up to a maximum depth (`maxdepth`), effectively mapping the codebase "impact radius".
9. **LLM Generation & Display:** The original prompt, the retrieved relevant code snippets, and the graph-based impact radius are sent to an external LLM API to generate an informed response, which is finally displayed to the user.
