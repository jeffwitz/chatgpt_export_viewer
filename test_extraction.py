# test_extraction.py
import os
import re
import json
import argparse # Pour passer le chemin du fichier en argument

def extract_assets_json_only(html_content):
    """
    Extrait UNIQUEMENT la variable 'assetsJson' (un dictionnaire) depuis une chaîne HTML.
    """
    variable_name = "assetsJson"
    print(f"--- Attempting to extract variable '{variable_name}' ---")
    start_delimiter, end_delimiter = ('{', '}') # On sait que assetsJson est un dict

    # Regex pour trouver 'assetsJson = { ... } ;' (point-virgule optionnel)
    pattern_str = f"\\b{variable_name}\\b\\s*=\\s*({start_delimiter}[\\s\\S]*?{end_delimiter})\\s*;?"
    print(f"  DEBUG: Regex pattern: {pattern_str}")

    pattern = re.compile(pattern_str, re.IGNORECASE)
    match = pattern.search(html_content)

    log_separator = "-" * (len(variable_name) + 32)

    if match:
        json_string = match.group(1).strip()
        print(f"  SUCCESS: Found potential pattern. Extracted string length: {len(json_string)}")
        print(f"  Attempting to parse extracted string as JSON dictionary...")
        try:
            parsed_data = json.loads(json_string)

            if not isinstance(parsed_data, dict):
                 print(f"  ERROR: Parsed data for '{variable_name}' is not a dictionary. Got: {type(parsed_data)}.")
                 print(log_separator)
                 return None

            print(f"  SUCCESS: Successfully parsed '{variable_name}' as dict.")
            print(log_separator)
            return parsed_data
        except json.JSONDecodeError as e:
            print(f"  ERROR: Failed to decode JSON for '{variable_name}': {e}")
            snippet_length = 200
            start_index = max(0, e.pos - snippet_length // 2)
            end_index = min(len(json_string), e.pos + snippet_length // 2)
            snippet = json_string[start_index:end_index]
            pointer_str = " " * (e.pos - start_index) + "^"
            print(f"  Context near error (position {e.pos}):\n  {snippet}\n  {pointer_str}")
            print(log_separator)
            return None
        except Exception as e_parse:
             print(f"  ERROR: Unexpected error during JSON parsing for '{variable_name}': {e_parse}")
             print(log_separator)
             return None
    else:
        print(f"  ERROR: Could not find the pattern '{variable_name} = {start_delimiter}...{end_delimiter}' in the HTML content.")
        print(log_separator)
        return None

# --- Exécution Principale du Script ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test extraction of assetsJson from a chat.html file.")
    parser.add_argument("html_filepath", help="Path to the chat.html file to test.")
    args = parser.parse_args()

    html_filepath = args.html_filepath

    if not os.path.exists(html_filepath):
        print(f"ERROR: File not found: {html_filepath}")
        sys.exit(1) # Quitter avec un code d'erreur

    print(f"Reading HTML file: {html_filepath}")
    try:
        with open(html_filepath, 'r', encoding='utf-8') as f:
            html_content_main = f.read()
        print("Successfully read HTML content.")
    except Exception as e:
        print(f"ERROR: Failed to read file: {e}")
        sys.exit(1) # Quitter avec un code d'erreur

    # Appeler la fonction d'extraction
    extracted_mapping = extract_assets_json_only(html_content_main)

    # Afficher le résultat
    if extracted_mapping is not None:
        print("\n--- EXTRACTION RESULT ---")
        print(f"Successfully extracted assetsJson! Found {len(extracted_mapping)} items.")
        # Afficher quelques éléments pour vérification
        count = 0
        print("First few items:")
        for key, value in extracted_mapping.items():
            print(f"  '{key}': '{value}'")
            count += 1
            if count >= 5:
                break
        if len(extracted_mapping) > 5:
             print("  ...")
    else:
        print("\n--- EXTRACTION RESULT ---")
        print("Extraction of assetsJson failed. Check logs above for details.")
