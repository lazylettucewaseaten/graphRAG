# PERKIFY: CodeRAG and GraphRAG System

PERKIFY is an intelligent Repository Analysis and Query System designed for C++ codebases. It combines Retrieval-Augmented Generation (RAG) with Graph-based knowledge representation to allow developers to semantically query their codebase, identify code dependencies, and evaluate the "blast radius" of potential changes.

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

## Architecture Pipeline

1. **AST Parsing (`initial.py`):** Uses Tree-sitter to parse the C++ codebase. It resolves function calls and inheritances (prioritizing same-file and same-directory scopes to avoid collisions) and outputs the nodes and relationships to a JSON file.
2. **Vector Ingestion (`ingestion.py`):** Reads the parsed code chunks, removes duplicates, generates vector embeddings using SentenceTransformers, and stores them in MongoDB Atlas Local.
3. **Graph Loading (`load_to_neo4j.py`):** Clears any stale data in the Neo4j database, then imports the nodes (files, classes, functions) and relationships (CALLS, INHERITS, FILE_CONTAINS).
4. **Query Resolution (`query.py`):** 
   * Captures the user query and assesses if it is a follow-up.
   * Performs a local cosine similarity search in MongoDB to retrieve relevant code chunks.
   * Queries Neo4j for the dependency graph (blast radius) around the matched code chunks.
   * Prompts the LLM (Gemini) with the code, the impact radius, and conversation history to formulate the final response.
