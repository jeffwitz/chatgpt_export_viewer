import re
import json

def extract_assets_mapping(chat_html_path):
    """
    Extrait le mapping des assets (assetsJson) du fichier chat.html.
    Retourne un dictionnaire associant asset_pointer => URL.
    """
    with open(chat_html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # L'expression régulière cherche la déclaration de la variable assetsJson
    match = re.search(r'var\s+assetsJson\s*=\s*(\{.*?\});', content, re.DOTALL)
    if match:
        assets_json_str = match.group(1)
        try:
            assets_mapping = json.loads(assets_json_str)
            return assets_mapping
        except json.JSONDecodeError as e:
            print("Erreur lors du décodage de assetsJson :", e)
    else:
        print("Mapping assetsJson non trouvé dans chat.html.")
    return {}

# Exemple d'utilisation
assets_mapping = extract_assets_mapping("06042025/chat.html")
print(assets_mapping)
