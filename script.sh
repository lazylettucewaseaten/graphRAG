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


echo " spinning up mongodb atlas local..."
if sudo docker ps -a --format '{{.Names}}' | grep -q '^mongodb-atlas-local$'; then
    if ! sudo docker ps --format '{{.Names}}' | grep -q '^mongodb-atlas-local$'; then
        sudo docker start mongodb-atlas-local
    fi
    echo " atlas local already exists, reusing"
else
    sudo systemctl stop mongod 2>/dev/null || true
    sudo systemctl stop mongodb 2>/dev/null || true
    sudo docker run -d --name mongodb-atlas-local -v perkify_mongo_data:/data/db -p 27017:27017 mongodb/mongodb-atlas-local:latest
fi

echo " waiting for atlas local to be ready..."
sleep 10

echo " running c++ ast analysis"
python3 initial.py "$repo_name"
python3 ingestion.py "$repo_name"
python3 load_to_neo4j.py "$repo_name"/repo_analysis.json

