#!/usr/bin/env python3
import os
import sys
import json
from tree_sitter import Parser, Language

IGNORE_DIRS = {'.git', 'node_modules', 'venv', '.venv', '__pycache__',
               'build', 'dist', 'target', '.idea', '.vscode'}
CPP_EXTENSIONS = {'.cpp', '.cc', '.cxx', '.c', '.h', '.hpp'}


def get_name(node):
    """Extract identifier name from a tree-sitter node, searching recursively."""
    if node.type in ('identifier', 'field_identifier', 'type_identifier'):
        return node.text.decode('utf-8', errors='ignore')
    for child in node.children:
        result = get_name(child)
        if result:
            return result
    return None


def traverse(node, parent_id, rel_path, nodes, relations, calls, inheritance, code_bytes,
             current_class=None, current_func=None):
    """Walk the AST and collect nodes and relations."""

    node_id = parent_id
    new_class = current_class
    new_func = current_func

    # --- Class / Struct ---
    if node.type in ('class_specifier', 'struct_specifier'):
        name_node = node.child_by_field_name('name')
        name = get_name(name_node) if name_node else None
        if not name:
            for child in node.children:
                if child.type == 'type_identifier':
                    name = child.text.decode('utf-8', errors='ignore')
                    break

        if name:
            node_id = f"{rel_path}_class_{name}"
            new_class = name
            text = code_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
            nodes.append({"id": node_id, "type": "class", "name": name, "file": rel_path, "text": text})
            relations.append({"source": parent_id, "target": node_id, "type": "FILE_CONTAINS"})

            # inheritance
            for child in node.children:
                if child.type == 'base_class_clause':
                    for base_child in child.children:
                        if base_child.type == 'type_identifier':
                            inheritance.append({
                                "class_id": node_id,
                                "base_name": base_child.text.decode('utf-8', errors='ignore'),
                                "file": rel_path
                            })

    #function definition 
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
                node_id = f"{rel_path}_function_{prefix}{name}"
                new_func = node_id
                text = code_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                nodes.append({"id": node_id, "type": "function", "name": name, "file": rel_path, "text": text})
                relations.append({"source": parent_id, "target": node_id, "type": "FILE_CONTAINS"})

    #  call 
    elif node.type == 'call_expression' and current_func:
        callee = node.child_by_field_name('function')
        if not callee and node.children:
            callee = node.children[0]

        if callee:
            called_name = None
            if callee.type in ('identifier', 'field_identifier'):
                called_name = callee.text.decode('utf-8', errors='ignore')
            elif callee.type in ('field_expression', 'member_expression'):
                for child in reversed(callee.children):
                    if child.type in ('identifier', 'field_identifier'):
                        called_name = child.text.decode('utf-8', errors='ignore')
                        break
            if called_name:
                calls.append({"caller": current_func, "called_name": called_name, "file": rel_path})

    # --- Recurse into children ---
    for child in node.children:
        traverse(child, node_id, rel_path, nodes, relations, calls, inheritance, code_bytes,
                 new_class, new_func)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 initial.py <repo_directory>")
        sys.exit(1)

    repo_path = os.path.abspath(sys.argv[1])
    if not os.path.isdir(repo_path):
        print(f"Error: {repo_path} is not a valid directory.")
        sys.exit(1)

    # init parser
    try:
        import tree_sitter_cpp
        parser = Parser(Language(tree_sitter_cpp.language()))
    except ImportError:
        print("Could not import tree-sitter-cpp. Install with: pip install tree-sitter-cpp")
        sys.exit(1)

    nodes = []
    relations = []
    calls = []
    inheritance = []


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
                print(f"[-] Error reading {file_path}: {e}")
                continue

            tree = parser.parse(code)
            file_id = f"{proj_path}_file"
            file_text = code.decode('utf-8', errors='ignore')
            nodes.append({"id": file_id, "type": "file", "name": proj_path, "file": proj_path, "text": file_text})
            traverse(tree.root_node, file_id, proj_path, nodes, relations, calls, inheritance, code)


    defs = {}
    for n in nodes:
        if n["type"] in ("class", "function"):
            defs.setdefault(n["name"], []).append(n)

    def resolve_target(name, caller_file):
        candidates = defs.get(name, [])
        if not candidates:
            return []
        

        same_file = [c for c in candidates if c["file"] == caller_file]
        if same_file:
            return [c["id"] for c in same_file]
            
        caller_dir = os.path.dirname(caller_file)
        same_dir = [c for c in candidates if os.path.dirname(c["file"]) == caller_dir]
        if same_dir:
            return [c["id"] for c in same_dir]
            
        return [c["id"] for c in candidates]

    for call in calls:
        for target_id in resolve_target(call["called_name"], call["file"]):
            relations.append({"source": call["caller"], "target": target_id, "type": "CALLS"})

    for inh in inheritance:
        for target_id in resolve_target(inh["base_name"], inh["file"]):
            relations.append({"source": inh["class_id"], "target": target_id, "type": "INHERITS"})

    seen = set()
    unique_relations = []
    for r in relations:
        key = (r["source"], r["target"], r["type"])
        if key not in seen:
            seen.add(key)
            unique_relations.append(r)

    # Save output
    output = {"nodes": nodes, "relations": unique_relations}
    output_file = os.path.join(repo_path, "repo_analysis.json")
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"[+] Saved to {output_file}")
    print(f"    Nodes: {len(nodes)}, Relations: {len(unique_relations)}")


if __name__ == '__main__':
    main()
