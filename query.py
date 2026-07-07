import sys
import os
import json
from google import genai
import requests
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

client = MongoClient(os.environ.get("MONGO_URI"))
db = client[os.environ.get("MONGO_DB")]
collection = db[os.environ.get("MONGO_COLLECTION")]

model = SentenceTransformer(os.environ.get("EMBEDDING_MODEL"), trust_remote_code=True)
device = os.environ.get("DEVICE", "cuda")
model.to(device)

llm_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
llm_model = os.environ.get("LLM_MODEL", "gemini-2.5-flash")

neo4j_driver = GraphDatabase.driver(
    os.environ.get("NEO4J_URI"),
    auth=(os.environ.get("NEO4J_USER"), os.environ.get("NEO4J_PASSWORD"))
)

context_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".context_window.json")


def llm_generate(prompt):
    resp = llm_client.models.generate_content(model=llm_model, contents=prompt)
    return resp.text


def load_context():
    if os.path.exists(context_file):
        try:
            with open(context_file, "r") as f:
                return json.load(f)
        except:
            pass
    return {"last_query": "", "last_output": "", "rag_context": ""}

#for one lnegth constext window , check if the new prompt w,r,t to old prompt is it follow up 

def save_context(query, output, rag_context):
    data = {
        "last_query": query,
        "last_output": output,
        "rag_context": rag_context
    }
    with open(context_file, "w") as f:
        json.dump(data, f)


def is_followup(current_query, prev_context):
    if not prev_context["last_query"]:
        return False

    prompt = f"""given these two queries, is the second one a follow-up to the first?
previous query: {prev_context['last_query']}
current query: {current_query}

answer only "yes" or "no"."""

    try:
        resp = llm_generate(prompt)
        return "yes" in resp.strip().lower()
    except:
        return False


def vector_search(query_text):
    query_embedding = model.encode(query_text).tolist()

    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": 150,
                "limit": 5
            }
        },
        {
            "$project": {
                "_id": 1,
                "file_path": 1,
                "start_b": 1,
                "end_b": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        }
    ]

    results = list(collection.aggregate(pipeline))
    return results


def read_code_chunk(file_path, start_b, end_b):
    try:
        with open(file_path, "rb") as f:
            f.seek(start_b)
            chunk = f.read(end_b - start_b)
            return chunk.decode("utf-8", errors="ignore")
    except:
        return ""

maindepth=1
def get_impact_radius(node_id, depth=maindepth):
    query = """
    match (n:CodeNode {id: $node_id})-[r*1..""" + str(depth) + """]->(affected:CodeNode)
    with n, affected
    where size((affected)-[]-()) <= 30
    return distinct affected.id as id, affected.name as name, 
           affected.type as type, affected.file as file
    """
    affected = []
    try:
        with neo4j_driver.session(database=os.environ.get("NEO4J_DATABASE", "neo4j")) as session:
            result = session.run(query, node_id=node_id)
            for record in result:
                affected.append({
                    "id": record["id"],
                    "name": record["name"],
                    "type": record["type"],
                    "file": record["file"]
                })
    except Exception as e:
        print(f"neo4j query failed: {e}")
    #cypher quert for getting the impact nodes to parse with LLM 
    reverse_query = """
    match (caller:CodeNode)-[r*1..""" + str(depth) + """]->(n:CodeNode {id: $node_id})
    with n, caller
    where size((caller)-[]-()) <= 30
    return distinct caller.id as id, caller.name as name,
           caller.type as type, caller.file as file
    """
    try:
        with neo4j_driver.session(database=os.environ.get("NEO4J_DATABASE", "neo4j")) as session:
            result = session.run(reverse_query, node_id=node_id)
            for record in result:
                affected.append({
                    "id": record["id"],
                    "name": record["name"],
                    "type": record["type"],
                    "file": record["file"]
                })
    except:
        pass

    return affected


#incase you want to use the ollama run ur local ollama instance and then just change 
# function name to llm_generate and remve the old llm_generate
def llm_generate_ollama(prompt):
        url = os.environ.get("OLLAMA_API_URL", "http://localhost:11434/api/generate")
        model_name = os.environ.get("OLLAMA_MODEL", "llama3")
        
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False
        }
         
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            print(f"Ollama call failed: {e}")
            return ""
        
def main():
    if len(sys.argv) < 2:
        print("no input provided")
        sys.exit(1)

    user_query = sys.argv[1]
    prev_context = load_context()

    search_results = vector_search(user_query)
    if not search_results:
        print("no matching code found")
        sys.exit(0)

    code_chunks = []
    matched_ids = []
    for res in search_results:
        file_path = res.get("file_path", "")
        start_b = res.get("start_b", 0)
        end_b = res.get("end_b", 0)
        doc_id = res.get("_id", "")

        code = read_code_chunk(file_path, start_b, end_b)
        if code:
            code_chunks.append(f"--- {file_path} ---\n{code}")
            matched_ids.append(doc_id)

    current_rag = "\n\n".join(code_chunks)

    followup = is_followup(user_query, prev_context)
    if followup and prev_context["rag_context"]:
        full_context = prev_context["rag_context"] + "\n\n" + current_rag
    else:
        full_context = current_rag

    all_affected = []
    for node_id in matched_ids:
        affected = get_impact_radius(node_id)
        all_affected.extend(affected)

    seen = set()
    unique_affected = []
    for a in all_affected:
        if a["id"] not in seen:
            seen.add(a["id"])
            unique_affected.append(a)

    impact_info = ""
    if unique_affected:
        impact_lines = []
        for a in unique_affected:
            impact_lines.append(f"- {a['type']}: {a['name']} (in {a['file']})")
        impact_info = "\nimpact radius (dependent/affected code):\n" + "\n".join(impact_lines)

    prompt_parts = []
    if followup:
        prompt_parts.append(f"previous conversation context:\nuser asked: {prev_context['last_query']}\nassistant answered: {prev_context['last_output']}\n")

    prompt_parts.append(f"relevant code:\n{full_context}")

    if impact_info:
        prompt_parts.append(f"this is the info which is directly affected by the user queries\n take these things into consideration when responding\n")
        prompt_parts.append(impact_info)

    prompt_parts.append(f"\nuser question: {user_query}")
    prompt_parts.append("\nanswer the question based on the code above. if there are affected/dependent functions mention them, answer how it is dependednt on it, be concise yet cover all the important aspects.")

    final_prompt = "\n\n".join(prompt_parts)

    try:
        output = llm_generate(final_prompt)
    except:
        output = "llm call failed"

    print(output)

    save_context(user_query, output, current_rag)


if __name__ == "__main__":
    main()