import re
import json

def extract_assets_mapping(chat_html_path):
    """
    Extract the assetsJson mapping from chat.html.
    Return a dictionary mapping asset_pointer => URL.
    """
    with open(chat_html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Regular expression targets the assetsJson variable declaration
    match = re.search(r'var\s+assetsJson\s*=\s*(\{.*?\});', content, re.DOTALL)
    if match:
        assets_json_str = match.group(1)
        try:
            assets_mapping = json.loads(assets_json_str)
            return assets_mapping
        except json.JSONDecodeError as e:
            print("Error decoding assetsJson:", e)
    else:
        print("assetsJson mapping not found in chat.html.")
    return {}

# Exemple d'utilisation
assets_mapping = extract_assets_mapping("06042025/chat.html")
print(assets_mapping)
