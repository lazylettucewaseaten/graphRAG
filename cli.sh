#!/bin/bash

SIGINT_COUNT=0

handle_sigint() {
    ((SIGINT_COUNT++))
    if [[ $SIGINT_COUNT -ge 2 ]]; then
        echo -e "\nExiting the CLI..."
        exit 0
    else
        echo -e "\nPress Ctrl+C again to exit."
        echo -n "Enter input > "
    fi
}


trap handle_sigint SIGINT


echo "--- graphRAG/codeRAG ---"
echo "Press Ctrl+C twice to exit."

while true; do

    echo -n "Enter input > "
    read user_input

    
    if [[ $? -ne 0 ]]; then
        continue
    fi

   
    if [[ -z "$user_input" ]]; then
        continue
    fi

    # cltr+c
    SIGINT_COUNT=0


    python3 query.py "$user_input"
    

    echo ""
done