#!/usr/bin/env python3
import os
import sys
from tree_sitter import Parser, Language
import tree_sitter_cpp
from sentence_transformers import SentenceTransformer
import chromadb
import torch
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

IGNORE_DIRS = {'.git', 'node_modules', 'venv', '.venv', '__pycache__',
                'build', 'dist', 'target', '.idea', '.vscode'}
CPP_EXTENSIONS = {'.cpp', '.cc', '.cxx', '.c', '.h', '.hpp'}



def get_name(node):
    if node.type in ('identifier', 'field_identifier', 'type_identifier'):
        return node.text.decode('utf-8', errors='ignore')
    for child in node.children:
        result = get_name(child)
        if result:
            return result
    return None

def traverse_ast(node, proj_path, chunks_list, current_class=None, code_bytes=None):
    
    new_class = current_class

    #class struct 
    if node.type in ('class_specifier', 'struct_specifier'):
        name_node = node.child_by_field_name('name')
        name = get_name(name_node) if name_node else None
        if not name:
            for child in node.children:
                if child.type == 'type_identifier':
                    name = child.text.decode('utf-8', errors='ignore')
                    break

        if name:
            node_id = f"{proj_path}_class_{name}"
            new_class = name
            try:
                text = code_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                chunks_list.append({
                    "_id": node_id,
                    "text": text,
                    "file_path": proj_path,
                    "start_b": node.start_byte,
                    "end_b": node.end_byte
                })
            except Exception as e:
                print(f"clas error fix it ")

    # functions declarations
    elif node.type == 'function_definition':
        decl = node.child_by_field_name('declarator')
        if not decl:
            for child in node.children:
                if child.type == 'function_declarator':
                    decl = child
                    break

        if decl:
            name = get_name(decl)
            if name:
                prefix = f"{current_class}_" if current_class else ""
                node_id = f"{proj_path}_function_{prefix}{name}"
                try:
                    text = code_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                    chunks_list.append({
                        "_id": node_id,
                        "text": text,
                        "file_path": proj_path,
                        "start_b": node.start_byte,
                        "end_b": node.end_byte
                    })
                except Exception as e:
                    print(f"error fix it ")


    for child in node.children:
        traverse_ast(child, proj_path, chunks_list, new_class, code_bytes)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 ingestion.py <repo_directory>")
        sys.exit(1)

    repo_path = os.path.abspath(sys.argv[1])
    if not os.path.isdir(repo_path):
        print(f"Error: {repo_path} is not a valid directory.")
        sys.exit(1)


    parser = Parser(Language(tree_sitter_cpp.language()))


    model = SentenceTransformer(os.environ.get("EMBEDDING_MODEL"), trust_remote_code=True)
    device = os.environ.get("DEVICE", "cuda") if torch.cuda.is_available() else "cpu"
    model.to(device)


    try:
        chroma_client = chromadb.PersistentClient(path="./chroma_db")
        collection_name = os.environ.get("CHROMA_COLLECTION", "graphrag")
        try:
            chroma_client.delete_collection(name=collection_name)
        except Exception:
            pass
        collection = chroma_client.create_collection(name=collection_name)
    except Exception as e:
        print(f"ChromaDB initialization failed: {e}")
        sys.exit(1)


    chunks_list = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if os.path.splitext(file)[1].lower() not in CPP_EXTENSIONS:
                continue

            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, repo_path)
            repo_name = os.path.basename(repo_path.rstrip(os.sep))
            proj_path = os.path.join(repo_name, rel_path)

            try:
                with open(file_path, 'rb') as f:
                    code = f.read()
            except Exception as e:
                print("cant fuckingread this ")
                continue

            tree=parser.parse(code)
            traverse_ast(tree.root_node, proj_path, chunks_list, code_bytes=code)

    if not chunks_list:
        sys.exit(0)

    # dedupe chunks by _id (same struct can appear multiple times in AST)
    seen_ids = set()
    unique_chunks = []
    for chunk in chunks_list:
        if chunk["_id"] not in seen_ids:
            seen_ids.add(chunk["_id"])
            unique_chunks.append(chunk)
    chunks_list = unique_chunks



    texts = [chunk["text"] for chunk in chunks_list]
    embeddings = model.encode(texts, batch_size=16, show_progress_bar=True)

    documents = []
    for chunk, emb in zip(chunks_list, embeddings):
        doc = {
            "_id": chunk["_id"],
            "embedding": emb.tolist(),
            "file_path": chunk["file_path"],
            "start_b": chunk["start_b"],
            "end_b": chunk["end_b"]
        }
        documents.append(doc)


    try:
        ids = [str(doc["_id"]) for doc in documents]
        embs = [doc["embedding"] for doc in documents]
        metas = [{"file_path": doc["file_path"], "start_b": doc["start_b"], "end_b": doc["end_b"]} for doc in documents]
        
        # Batch insert to ChromaDB
        BATCH_SIZE = 500
        for i in range(0, len(ids), BATCH_SIZE):
            collection.add(
                ids=ids[i:i+BATCH_SIZE],
                embeddings=embs[i:i+BATCH_SIZE],
                metadatas=metas[i:i+BATCH_SIZE]
            )
    except Exception as e:
        print(f" err inserting into ChromaDB: {e}")
        sys.exit(1)
    

if __name__ == '__main__':
    main()