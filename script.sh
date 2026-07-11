#!/bash
set -e

echo "=========================================================="
echo "          C++ Repository AST Analyzer Setup"
echo "=========================================================="
read -p "Enter Git Repository URL: " repo_url

if [ -z "$repo_url" ]; then
    echo "Error: Repository URL cannot be empty."
    exit 1
fi

repo_name=$(basename -s .git "$repo_url")
if [ -z "$repo_name" ]; then
    repo_name="cloned_repo"
fi

if [ -d "$repo_name" ]; then
    echo "Directory '$repo_name' already exists. Cleaning it up..."
    rm -rf "$repo_name"
fi

git clone "$repo_url" "$repo_name"


echo " Starting local database services (MongoDB & Neo4j)..."
sudo systemctl enable --now mongod
sudo systemctl enable --now neo4j

echo " waiting for services to be ready..."
sleep 5

echo " running c++ ast analysis"
python3 initial.py "$repo_name"
python3 ingestion.py "$repo_name"
python3 load_to_neo4j.py "$repo_name"/repo_analysis.json

