# app.py (Version Complète avec Indexation Whoosh - Correction Double SyntaxError)
import os
import json
import sys
import re
from flask import Flask, render_template, jsonify, request, send_from_directory, abort
import mimetypes
import shutil # Pour supprimer un index potentiellement corrompu

# --- Whoosh Imports ---
try:
    from whoosh.index import create_in, open_dir, exists_in, EmptyIndexError
    from whoosh.fields import Schema, TEXT, ID, STORED
    from whoosh.qparser import QueryParser, MultifieldParser, QueryParserError
    from whoosh.writing import AsyncWriter # Optionnel
    import whoosh.query # Pour Variations si utilisé
    WHOOSH_AVAILABLE = True
    print("INFO: Whoosh library found.")
except ImportError:
    WHOOSH_AVAILABLE = False
    print("WARN: Whoosh library not found (pip install Whoosh). Full-text search will be disabled.")
    # Stubs pour éviter NameError si Whoosh n'est pas là
    class Schema: pass
    def create_in(*args, **kwargs): raise ImportError("Whoosh not installed")
    def open_dir(*args, **kwargs): raise ImportError("Whoosh not installed")
    def exists_in(*args, **kwargs): return False
    class QueryParser: pass
    class MultifieldParser: pass
    class QueryParserError(Exception): pass
    class EmptyIndexError(Exception): pass
    class AsyncWriter: pass

# --- Configuration et initialisation ---
app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_BASE_DIR = BASE_DIR
INDEX_DIR_NAME = ".indexdir" # Nom du dossier pour les index Whoosh

# --- Initialisation de python-magic ---
try:
    import magic
    if sys.platform == "win32":
        magic_instance = None; possible_dll_paths = [] # Ajoutez chemins DLL si besoin
        try: magic_instance = magic.Magic(mime=True); print("INFO: magic init OK (Win default).")
        except Exception as e_no_path: print(f"WARN: magic init failed ({e_no_path})."); magic_instance = None
    else: magic_instance = magic.Magic(mime=True); print("INFO: magic init OK (Linux/macOS).")
except ImportError: print("WARN: python-magic not found."); magic_instance = None
except Exception as e: print(f"WARN: magic init FAILED: {e}"); magic_instance = None


# --- Fonctions Utilitaires ---

def get_export_folders():
    """Trouve les dossiers valides (conversations.json ET chat.html), exclut .indexdir."""
    folders = []
    print(f"\nSearching for export folders in: {EXPORT_BASE_DIR}")
    try:
        for item in os.listdir(EXPORT_BASE_DIR):
            item_path = os.path.join(EXPORT_BASE_DIR, item)
            # Exclure les dossiers cachés, de service ET d'index
            if os.path.isdir(item_path) and not item.startswith('.') and item not in ['static', 'templates', '__pycache__', 'venv', INDEX_DIR_NAME]:
                 conversations_json_path = os.path.join(item_path, 'conversations.json')
                 chat_html_path = os.path.join(item_path, 'chat.html')
                 if os.path.exists(conversations_json_path) and os.path.exists(chat_html_path):
                     folders.append(item); print(f"  + Found valid: {item}")
                 else: print(f"  - Skipping '{item}': missing files")
    except Exception as e: print(f"ERROR listing folders: {e}")
    try: folders.sort(key=lambda x: x.replace('-', '').replace('_', ''), reverse=True)
    except Exception: folders.sort()
    print(f"Final list of folders: {folders}")
    return folders

def extract_asset_pointers(conversations_data):
    """Extrait les asset_pointers depuis la structure conversations.json (liste)."""
    pointers = set(); found_count = 0
    if not isinstance(conversations_data, list): return pointers
    print(f"  Scanning {len(conversations_data)} conversations for asset pointers...")
    for conv in conversations_data: # Boucle principale sur les conversations
        if not isinstance(conv, dict) or 'mapping' not in conv or not isinstance(conv['mapping'], dict): continue
        for node_id, node_data in conv['mapping'].items(): # Boucle sur les noeuds du mapping de la conv
             if not isinstance(node_data, dict) or 'message' not in node_data or not isinstance(node_data['message'], dict): continue
             message = node_data['message']; parts_to_check = [] # Liste pour collecter les parts à vérifier
             # Vérifier contenu principal
             if isinstance(message.get('content'), dict) and isinstance(message['content'].get('parts'), list):
                 parts_to_check.extend(message['content']['parts'])
             # Vérifier metadata des outils (si applicable à vos données)
             if message.get('author', {}).get('role') == 'tool' and isinstance(message.get('metadata'), dict):
                  agg_result = message['metadata'].get('aggregate_result', {}).get('message', {})
                  if isinstance(agg_result.get('content'), dict) and isinstance(agg_result['content'].get('parts'), list):
                       parts_to_check.extend(agg_result['content']['parts'])
             # Parcourir les parts collectées pour cette node
             for part in parts_to_check:
                  if isinstance(part, dict) and 'asset_pointer' in part: # Si c'est un dict avec la clé asset_pointer
                       pointer = part['asset_pointer']
                       if isinstance(pointer, str) and pointer.strip(): # Si la valeur est une chaîne non vide
                            if pointer not in pointers: found_count += 1 # Compter la première fois qu'on le voit
                            pointers.add(pointer.strip()) # Ajouter le pointeur (set gère les doublons)
    print(f"  Scan complete. Found {found_count} new unique pointers (Total: {len(pointers)}).")
    return pointers

def get_file_mime_type(file_path):
    """Tente d'obtenir le type MIME, avec log spécifique pour .dat."""
    mime_type = "application/octet-stream" # Défaut
    filename_for_log = os.path.basename(file_path) # Pour le log

    # Essayer avec python-magic si disponible
    if magic_instance:
        try:
            detected_mime = magic_instance.from_file(file_path)
            if filename_for_log.lower().endswith(".dat"): print(f"\n    [MAGIC DEBUG for .dat] File: '{filename_for_log}' -> Detected: '{detected_mime}'")
            if detected_mime: mime_type = detected_mime.split(';')[0].strip() if ';' in detected_mime else detected_mime; return mime_type
        except Exception as e_magic:
             if magic_instance is not None: print(f"    WARN: magic error for {filename_for_log}: {e_magic}")
    else:
         if filename_for_log.lower().endswith(".dat"): print(f"\n    [MIMETYPES DEBUG for .dat] File: '{filename_for_log}' (magic unavailable)")

    # Fallback: utiliser mimetypes
    try:
        guessed_mime, _ = mimetypes.guess_type(file_path)
        if filename_for_log.lower().endswith(".dat"): print(f"    [MIMETYPES DEBUG for .dat] File: '{filename_for_log}' -> Guessed: '{guessed_mime}'")
        if guessed_mime: mime_type = guessed_mime
    except Exception as e: print(f"    WARN: mimetypes error for {filename_for_log}: {e}")
    return mime_type

def extract_assets_json_only_from_html(html_content):
    """Extrait UNIQUEMENT la variable 'assetsJson' depuis une chaîne HTML."""
    variable_name = "assetsJson"; start_delimiter, end_delimiter = ('{', '}')
    print(f"--- Attempting to extract variable '{variable_name}' from HTML ---")
    pattern_str = f"\\b{variable_name}\\b\\s*=\\s*({start_delimiter}[\\s\\S]*?{end_delimiter})\\s*;?"
    pattern = re.compile(pattern_str, re.IGNORECASE)
    match = pattern.search(html_content)
    log_separator = "-" * (len(variable_name) + 32)
    if match:
        json_string = match.group(1).strip()
        print(f"  SUCCESS: Found pattern. Length: {len(json_string)}")
        try:
            parsed_data = json.loads(json_string)
            if not isinstance(parsed_data, dict): print(f"  ERROR: Parsed data not dict."); print(log_separator); return None
            print(f"  SUCCESS: Parsed '{variable_name}' as dict."); print(log_separator); return parsed_data
        except json.JSONDecodeError as e: print(f"  ERROR: JSON decode failed: {e}"); print(log_separator); return None
        except Exception as e_parse: print(f"  ERROR: Unexpected parsing error: {e_parse}"); print(log_separator); return None
    else: print(f"  ERROR: Pattern '{variable_name} = {{...}}' not found."); print(log_separator); return None

# --- Fonctions d'Indexation (Whoosh) ---

def get_index_schema():
    """Définit le schéma de l'index Whoosh."""
    if not WHOOSH_AVAILABLE: return None
    return Schema( conversation_id=ID(stored=True, unique=True), title=TEXT(stored=True, field_boost=2.0), content=TEXT(stored=False) )

def extract_text_from_conversation(conv_data):
    """Extrait et concatène tout le texte pertinent d'une conversation."""
    all_text = [];
    if not isinstance(conv_data, dict): return ""
    if isinstance(conv_data.get('title'), str): all_text.append(conv_data['title'])
    mapping = conv_data.get('mapping')
    if not isinstance(mapping, dict): return " ".join(all_text).strip()
    for node_id, node_data in mapping.items():
         if not isinstance(node_data, dict) or 'message' not in node_data or not isinstance(node_data['message'], dict): continue
         message = node_data['message']; parts_to_extract = []
         if isinstance(message.get('content'), dict) and isinstance(message['content'].get('parts'), list): parts_to_extract.extend(message['content']['parts'])
         if message.get('author', {}).get('role') == 'tool' and isinstance(message.get('metadata'), dict):
              agg_result = message['metadata'].get('aggregate_result', {}).get('message', {})
              if isinstance(agg_result.get('content'), dict) and isinstance(agg_result['content'].get('parts'), list): parts_to_extract.extend(agg_result['content']['parts'])
         for part in parts_to_extract:
              text_content = None
              if isinstance(part, str): text_content = part
              elif isinstance(part, dict):
                   if isinstance(part.get('text'), str): text_content = part['text']
                   elif part.get('content_type') == 'code' and isinstance(part.get('text'), str): text_content = part['text']
              if isinstance(text_content, str): all_text.append(text_content)
    full_content = " ".join(all_text); full_content = re.sub(r'\s+', ' ', full_content).strip()
    return full_content

def ensure_index_exists(export_folder_path, conversations_data):
    """Vérifie si l'index Whoosh existe, sinon le crée et l'indexe."""
    if not WHOOSH_AVAILABLE: print("  INFO: Whoosh not available, skipping index."); return False
    index_dir = os.path.join(export_folder_path, INDEX_DIR_NAME)
    schema = get_index_schema(); print(f"  Index target directory: {index_dir}")
    try: # Vérifier permissions écriture
        os.makedirs(index_dir, exist_ok=True); test_file_path = os.path.join(index_dir, ".perm_test");
        with open(test_file_path, "w") as f: f.write("test"); os.remove(test_file_path)
        print("  Write permissions seem OK.")
    except OSError as e_perm: print(f"  CRITICAL ERROR: Write permission error: {e_perm}"); return False

    if exists_in(index_dir):
        print(f"  Index found.")
        try: # Vérifier si ouvrable
            ix_check = open_dir(index_dir); ix_check.close()
            print("  Existing index opened successfully."); return True
        except (EmptyIndexError, Exception) as e_open:
            print(f"  WARN: Existing index seems corrupted/locked/empty: {e_open}. Recreating...")
            try: shutil.rmtree(index_dir); os.makedirs(index_dir, exist_ok=True)
            except Exception as e_clean: print(f"  CRITICAL ERROR: Failed removing corrupted index: {e_clean}"); return False

    # --- Création de l'index ---
    print(f"  Index not found or recreating. Creating and indexing...")
    writer = None; ix = None
    try:
        ix = create_in(index_dir, schema)
        writer = ix.writer(); print(f"  Index structure created. Adding documents...")
        indexed_count, skipped_count, error_count = 0, 0, 0
        total_convs = len(conversations_data)
        for i, conv in enumerate(conversations_data):
            conv_id = conv.get('conversation_id') or conv.get('id')
            if not conv_id or not isinstance(conv_id, str): print(f"    WARN [Idx {i}]: Skipping, missing ID."); skipped_count += 1; continue
            title = conv.get('title', "[Sans Titre]")
            try: content = extract_text_from_conversation(conv)
            except Exception as e_extract: print(f"    ERROR [ID {conv_id}]: Text extraction failed: {e_extract}."); error_count += 1; continue
            if not content.strip() and not title.strip(): print(f"    WARN [ID {conv_id}]: Skipping, empty."); skipped_count += 1; continue
            try:
                writer.add_document(conversation_id=conv_id, title=title, content=content); indexed_count += 1
                if (indexed_count + skipped_count + error_count) % 100 == 0: print(f"    Processed {indexed_count + skipped_count + error_count}/{total_convs}...")
            except Exception as e_add: print(f"    ERROR [ID {conv_id}]: Failed adding document: {e_add}."); error_count += 1
        print(f"  Finished processing (Added: {indexed_count}, Skipped: {skipped_count}, Errors: {error_count})."); print(f"  Committing index..."); writer.commit(); writer = None
        print("  Index created successfully.")
        return True
    except Exception as e_create:
        print(f"  CRITICAL ERROR during index creation: {e_create}"); import traceback; traceback.print_exc()
        if os.path.exists(index_dir): print(f"  Attempting cleanup: {index_dir}");
        try:
             if writer: writer.cancel()
             shutil.rmtree(index_dir); print("    Cleanup successful.")
        except Exception as e_clean_fail: print(f"    WARN: Cleanup failed: {e_clean_fail}")
        return False
    finally:
        if writer: print("  WARN: Writer not None in finally, cancelling."); writer.cancel()
        if ix: ix.close()

# --- Routes ---

@app.route('/')
def index_route():
    """Sert la page d'accueil."""
    folders = get_export_folders()
    return render_template('index.html', folders=folders)

@app.route('/conversations')
def get_conversations_route():
    """Récupère les données de base et assure l'indexation."""
    folder_name = request.args.get('folder_name')
    print(f"\n{'='*10} Processing request for folder: {folder_name} {'='*10}")
    if not folder_name or '..' in folder_name or folder_name.startswith('/'): return jsonify({"error": "Invalid folder name"}), 400
    export_folder_path = os.path.join(EXPORT_BASE_DIR, folder_name)
    conversations_json_path = os.path.join(export_folder_path, 'conversations.json')
    chat_html_path = os.path.join(export_folder_path, 'chat.html')
    file_types_path = os.path.join(export_folder_path, 'file_type.json')
    index_dir_path = os.path.join(export_folder_path, INDEX_DIR_NAME)
    if not os.path.abspath(export_folder_path).startswith(os.path.abspath(EXPORT_BASE_DIR)): return jsonify({"error": "Access denied"}), 403
    if not os.path.isdir(export_folder_path): return jsonify({"error": "Folder not found"}), 404

    # --- 1. Lire conversations.json ---
    print(f"Step 1: Reading conversations: {conversations_json_path}")
    try:
        with open(conversations_json_path, 'r', encoding='utf-8') as f: conversations_data = json.load(f)
        if not isinstance(conversations_data, list): raise ValueError("Not a list")
        print(f"  Read {len(conversations_data)} items.")
    except Exception as e: print(f"ERROR reading conversations.json: {e}"); return jsonify({"error": f"Failed reading conversations.json: {e}"}), 500
    print("Step 1 OK.")

    # --- 2. Lire chat.html pour assetsJson ---
    print(f"Step 2: Reading HTML for mapping: {chat_html_path}")
    asset_mapping_data = {}
    try:
        if os.path.exists(chat_html_path):
            with open(chat_html_path, 'r', encoding='utf-8') as f: html_content = f.read()
            extracted_mapping = extract_assets_json_only_from_html(html_content)
            if extracted_mapping: asset_mapping_data = extracted_mapping
            else: print("WARN: Failed extraction 'assetsJson'.")
        else: print("WARN: chat.html not found.")
    except Exception as e: print(f"ERROR reading/processing chat.html: {e}")
    print(f"Step 2 OK. Mapping contains {len(asset_mapping_data)} items.")

    # --- 3. Assurer l'existence de l'index ---
    print(f"Step 3: Ensuring search index: {index_dir_path}")
    index_ready = ensure_index_exists(export_folder_path, conversations_data)
    if not index_ready: print("WARN: Index unusable. Search disabled.")
    else: print("Step 3 OK.")

    # --- 4. Extraire pointeurs requis ---
    print("Step 4: Extracting required pointers..."); required_pointers = extract_asset_pointers(conversations_data); print(f"Step 4 OK: Found {len(required_pointers)} pointers.")
    # --- 5. Vérifier mapping ---
    print("Step 5: Verifying mapping..."); mapped_pointers = set(asset_mapping_data.keys()); missing_pointers = required_pointers - mapped_pointers
    if missing_pointers: print(f"  WARN: {len(missing_pointers)} pointers MISSING.")
    else: print("  INFO: Pointers OK."); print("Step 5 OK.")
    # --- 6. Charger/Initialiser file_type.json ---
    print(f"Step 6: Loading/Initializing file types map..."); file_types_data = {};
    try:
        if os.path.exists(file_types_path):
            with open(file_types_path, 'r', encoding='utf-8') as f: loaded_types = json.load(f)
            if isinstance(loaded_types, dict): file_types_data = loaded_types; print(f"  Loaded {len(file_types_data)} types.")
            else: print(f"  WARN: file_type.json not dict.")
        else: print(f"  INFO: file_type.json not found.")
    except Exception as e: print(f"  WARN: Error reading file_type.json: {e}.")
    print("Step 6 OK.")
    # --- 7. Identifier types de fichiers ---
    print("Step 7: Identifying/Updating file types..."); updated_types = False; target_filenames = set(asset_mapping_data.values())
    if not target_filenames: print("  No target files.")
    else:
        print(f"  Checking types for {len(target_filenames)} filenames...")
        for i, filename in enumerate(target_filenames):
            if not isinstance(filename, str) or not filename.strip(): continue
            current_type = file_types_data.get(filename)
            if isinstance(current_type, str) and current_type not in ["File not found", "Is Directory", "Error checking type", "Not a file or directory"]: continue
            file_path = os.path.join(export_folder_path, filename)
            print(f"    ({i+1}/{len(target_filenames)}) Checking: {filename}", end="")
            file_type_result = "Error checking type" # Default value
            # *** CORRECTION ICI ***
            try: # try: sur sa propre ligne
                if os.path.exists(file_path):
                    if os.path.isfile(file_path): file_type_result = get_file_mime_type(file_path); print(f" -> Type: {file_type_result}")
                    elif os.path.isdir(file_path): file_type_result = "Is Directory"; print(" -> Is Directory.")
                    else: file_type_result = "Not a file or directory"; print(" -> Not file/dir.")
                else: file_type_result = "File not found"; print(" -> Not found.")
            except Exception as e_check: print(f" -> ERROR checking file: {e_check}"); file_type_result = "Error checking type"
            # *** FIN CORRECTION ***
            if current_type != file_type_result: file_types_data[filename] = file_type_result; updated_types = True
    print("Step 7 OK.")
    # --- 8. Sauvegarder file_type.json ---
    if updated_types: print(f"Step 8: Saving updated file types...");
    else: print("Step 8: No file type updates.");
    if updated_types:
        try:
            with open(file_types_path, 'w', encoding='utf-8') as f: json.dump(file_types_data, f, indent=2, ensure_ascii=False)
            print("  Successfully saved.")
        except Exception as e: print(f"  ERROR saving: {e}")

    # --- 9. Combiner et retourner les données ---
    response_data = {"conversations": conversations_data, "asset_mapping": asset_mapping_data, "file_types": file_types_data}
    # Log de débogage final
    print(f"DEBUG [Step 9]: Final file_types being sent:")
    log_count = 0; displayed_dat = False
    for fname, ftype in file_types_data.items():
        is_dat = ".dat" in fname.lower()
        if is_dat or log_count < 5: # Prioriser .dat ou les 5 premiers
             print(f"  '{fname}': '{ftype}'")
             if is_dat: displayed_dat = True
        log_count += 1
        if log_count >= 15: # Limiter l'affichage total
             if len(file_types_data) > 15: print("  ...")
             break
    if not displayed_dat and any(".dat" in f.lower() for f in file_types_data): print("  (More types exist, including other .dat files not shown)")
    # Fin log débogage

    print(f"Step 9: Sending response."); print(f"{'='*10} Finished request for {folder_name} {'='*10}\n")
    return jsonify(response_data)


# --- Route de Recherche ---
@app.route('/search')
def search_conversations():
    """Effectue une recherche plein texte dans l'index Whoosh."""
    if not WHOOSH_AVAILABLE: return jsonify({"error": "Search unavailable."}), 501

    folder_name = request.args.get('folder_name'); query_string = request.args.get('query')
    print(f"\n{'='*10} Processing SEARCH: Folder={folder_name}, Query='{query_string}' {'='*10}")
    if not folder_name or '..' in folder_name or folder_name.startswith('/'): return jsonify({"error": "Invalid folder name"}), 400
    if not query_string: return jsonify({"error": "Missing query"}), 400

    export_folder_path = os.path.join(EXPORT_BASE_DIR, folder_name); index_dir = os.path.join(export_folder_path, INDEX_DIR_NAME)
    if not os.path.isdir(export_folder_path): return jsonify({"error": "Folder not found"}), 404
    if not exists_in(index_dir): print(f"  Error: Index not found."); return jsonify([])

    ix = None
    try:
        print(f"  Opening index: {index_dir}"); ix = open_dir(index_dir)
        parser_kwargs = {}
        if WHOOSH_AVAILABLE: # Utiliser Variations seulement si Whoosh est bien importé
             parser_kwargs["termclass"] = whoosh.query.Variations
        qp = MultifieldParser(["title", "content"], schema=ix.schema, **parser_kwargs)
        print(f"  Parsing query: '{query_string}'"); parsed_query = qp.parse(query_string)
        results_list = []
        with ix.searcher() as searcher:
            results = searcher.search(parsed_query, limit=100)
            print(f"  Found {len(results)} results.")
            for hit in results: results_list.append({"id": hit['conversation_id'], "title": hit['title']})
        print(f"Search OK. Returning {len(results_list)} results."); print(f"{'='*10} Finished SEARCH {'='*10}\n")
        return jsonify(results_list)
    except QueryParserError as e_parse: print(f"ERROR parsing query: {e_parse}"); return jsonify({"error": f"Invalid search query: {e_parse}"}), 400
    except EmptyIndexError: print("WARN: Search on empty index."); return jsonify([])
    except Exception as e_search: print(f"ERROR during search: {e_search}"); import traceback; traceback.print_exc(); return jsonify({"error": f"Search error: {str(e_search)}"}), 500
    finally:
        if ix: ix.close()

# --- Routes /export_files et /static ---
@app.route('/export_files/<path:folder_name>/<path:filepath>')
def serve_export_file(folder_name, filepath):
    """Sert les fichiers des exports."""
    print(f"Request for export file: folder='{folder_name}', filepath='{filepath}'")
    if not folder_name or '..' in folder_name or folder_name.startswith('/'): abort(400)
    if not filepath or '..' in filepath or filepath.startswith('/'): abort(400)
    safe_directory = os.path.abspath(os.path.join(EXPORT_BASE_DIR, folder_name))
    if not safe_directory.startswith(os.path.abspath(EXPORT_BASE_DIR)): abort(403)
    if not os.path.isdir(safe_directory): abort(404)
    requested_path = os.path.abspath(os.path.join(safe_directory, filepath))
    if not requested_path.startswith(safe_directory): abort(403)
    print(f"Attempting to serve '{filepath}' from '{safe_directory}'")
    try: return send_from_directory(safe_directory, filepath, as_attachment=False)
    except FileNotFoundError:
        print(f"Error: File not found.")
        try: actual_filename = next((e for e in os.listdir(safe_directory) if e.lower() == filepath.lower()), None)
        except OSError: actual_filename = None
        if actual_filename: print(f"  Found case-insensitive: '{actual_filename}'."); return send_from_directory(safe_directory, actual_filename)
        else: abort(404)
    except Exception as e: print(f"Error serving file: {e}"); abort(500)

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Sert les fichiers statiques."""
    static_dir = os.path.join(BASE_DIR, 'static')
    return send_from_directory(static_dir, filename)

# --- Exécution principale ---
if __name__ == '__main__':
    print("Starting Flask server...")
    use_reloader = True
    print(f"Whoosh available: {WHOOSH_AVAILABLE}")
    print(f"Reloader enabled: {use_reloader}")
    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=use_reloader)
