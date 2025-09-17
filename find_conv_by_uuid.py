#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ijson
import json
import argparse
import sys
import os
from collections.abc import Mapping, Sequence # Pour vérifier les types dict/list

def find_paths_containing_value(data, target_fragment, current_path=None):
    """
    Recherche récursivement un fragment de chaîne dans les valeurs d'un objet (dict/list).
    Retourne une liste de dictionnaires, chacun contenant le chemin et la valeur trouvée.
    """
    if current_path is None:
        current_path = []
    found_locations = []

    if isinstance(data, Mapping): # Si c'est un dictionnaire
        for key, value in data.items():
            new_path = current_path + [key]
            # 1. Vérifie si la valeur directe est une chaîne contenant le fragment
            if isinstance(value, str) and target_fragment in value:
                found_locations.append({"path": new_path, "value": value})
            # 2. Si c'est un dict ou une liste, explore récursivement
            elif isinstance(value, (Mapping, Sequence)) and not isinstance(value, str):
                found_locations.extend(find_paths_containing_value(value, target_fragment, new_path))

    elif isinstance(data, Sequence) and not isinstance(data, str): # Si c'est une liste/tuple (pas une chaîne)
        for index, item in enumerate(data):
            new_path = current_path + [index]
            # 1. Vérifie si l'item direct est une chaîne contenant le fragment
            if isinstance(item, str) and target_fragment in item:
                found_locations.append({"path": new_path, "value": item})
            # 2. Si c'est un dict ou une liste, explore récursivement
            elif isinstance(item, (Mapping, Sequence)) and not isinstance(item, str):
                found_locations.extend(find_paths_containing_value(item, target_fragment, new_path))

    # Ne vérifie pas les types simples (int, float, bool, None)

    return found_locations

def find_id_fragment_locations(json_filepath, target_id_fragment):
    """
    Parcourt conversations.json et trouve tous les emplacements (chemins de clés)
    où un fragment d'ID donné apparaît dans une valeur.
    """
    if not os.path.exists(json_filepath):
        print(f"Erreur: Fichier introuvable - '{json_filepath}'", file=sys.stderr)
        return

    print(f"Recherche des emplacements du fragment '{target_id_fragment}' dans '{json_filepath}'...")
    all_results = []
    total_conversations_checked = 0

    try:
        with open(json_filepath, 'rb') as f:
            conversations = ijson.items(f, 'item')
            for i, conversation in enumerate(conversations):
                total_conversations_checked = i + 1
                if total_conversations_checked % 500 == 0:
                    print(f"  ... Vérifié {total_conversations_checked} conversations", end='\r')

                if not isinstance(conversation, dict): continue

                conv_id = conversation.get("conversation_id") or conversation.get("id", f"index_{i}")
                conv_title = conversation.get("title", "[Sans Titre]")

                # Recherche récursive dans l'objet conversation complet
                locations_in_conv = find_paths_containing_value(conversation, target_id_fragment)

                if locations_in_conv:
                    for loc in locations_in_conv:
                        all_results.append({
                            "conversation_id": conv_id,
                            "conversation_title": conv_title,
                            "path": loc["path"],
                            "found_value": loc["value"]
                        })
                        # Optionnel: Arrêter après la première trouvaille par conversation
                        # break

        print(f"\nScan terminé. {total_conversations_checked} conversations vérifiées.")

        if all_results:
            print(f"\n--- Emplacements trouvés pour '{target_id_fragment}' ---")
            for result in all_results:
                # Formatage du chemin pour lisibilité
                path_str = ""
                for item in result['path']:
                    if isinstance(item, int): # Index de liste
                        path_str += f"[{item}]"
                    else: # Clé de dictionnaire
                        path_str += f".{item}" if path_str else str(item) # Point séparateur sauf pour le premier

                associated_key = result['path'][-1] if result['path'] else "N/A (Racine?)"

                print(f"\nConversation : '{result['conversation_title']}' (ID: {result['conversation_id']})")
                print(f"  Clé/Index associé : '{associated_key}'")
                print(f"  Chemin complet    : {path_str}")
                # Limite la longueur de la valeur affichée
                value_preview = result['found_value']
                if len(value_preview) > 150:
                     value_preview = value_preview[:150] + "..."
                print(f"  Valeur trouvée    : {value_preview}")
        else:
            print(f"\nAucune valeur contenant '{target_id_fragment}' n'a été trouvée.")

    except ijson.JSONError as e:
        print(f"\nErreur de parsing JSON: {e}", file=sys.stderr)
    except Exception as e:
        print(f"\nErreur inattendue: {e}", file=sys.stderr)

# --- Point d'Entrée ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Trouve où un fragment d'ID de fichier est utilisé comme valeur dans conversations.json et retourne la clé associée.",
        epilog="Exemple: python find_key_for_file_id.py chemin/conversations.json T9L9gfa8Ca4QzK9w8dEw82"
    )
    parser.add_argument(
        "json_file",
        help="Chemin vers le fichier conversations.json."
    )
    parser.add_argument(
        "file_id_fragment",
        help="L'ID ou fragment d'ID du fichier à rechercher dans les valeurs (ex: T9L9gfa8Ca4QzK9w8dEw82)."
    )

    args = parser.parse_args()

    # Nettoie le fragment (enlève juste le préfixe 'file-' s'il existe pour chercher l'UUID pur)
    target_fragment = args.file_id_fragment
    if target_fragment.startswith("file-"):
        target_fragment = target_fragment[len("file-"):]
        print(f"(Recherche du fragment UUID : '{target_fragment}')")

    find_id_fragment_locations(args.json_file, target_fragment)

    sys.exit(0)
