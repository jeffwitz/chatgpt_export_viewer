#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import sys
import os
from collections import Counter
import argparse # Pour une meilleure gestion des arguments

# --- Fonctions d'Analyse et de Description ---

def get_value_type(value):
    """Retourne une description textuelle du type de la valeur."""
    if isinstance(value, dict):
        return "Object (dict)"
    elif isinstance(value, list):
        return "Array (list)"
    elif isinstance(value, str):
        return "String"
    elif isinstance(value, int):
        return "Integer"
    elif isinstance(value, float):
        return "Float"
    elif isinstance(value, bool):
        return "Boolean"
    elif value is None:
        return "Null"
    else:
        return f"Unknown ({type(value).__name__})"

def analyze_structure(data, indent="", level=0, max_depth=10):
    """
    Analyse récursivement la structure des données JSON et retourne une description textuelle.
    """
    if level > max_depth:
        return f"{indent}[...] (Profondeur max atteinte)\n"

    description = ""
    data_type = get_value_type(data)
    description += f"{indent}Type: {data_type}\n"

    if isinstance(data, dict):
        if not data:
            description += f"{indent}  (Objet vide)\n"
        else:
            description += f"{indent}  Clés ({len(data)}):\n"
            for key, value in data.items():
                description += f"{indent}    - \"{key}\":\n"
                # Appel récursif pour la valeur associée à la clé
                description += analyze_structure(value, indent + "      ", level + 1, max_depth)

    elif isinstance(data, list):
        if not data:
            description += f"{indent}  (Liste vide)\n"
        else:
            description += f"{indent}  Éléments ({len(data)}):\n"
            # Analyser les types d'éléments dans la liste
            element_types = Counter(get_value_type(item) for item in data)

            if len(element_types) == 1:
                # Tous les éléments semblent avoir le même type
                first_item_type = next(iter(element_types))
                description += f"{indent}    (Tous les éléments semblent être de type: {first_item_type})\n"

                # Si les éléments sont des objets, vérifier si les clés sont cohérentes
                if first_item_type == "Object (dict)" and len(data) > 0:
                    first_item_keys = set(data[0].keys())
                    all_keys_same = True
                    for item in data[1:]:
                        if not isinstance(item, dict) or set(item.keys()) != first_item_keys:
                            all_keys_same = False
                            break
                    if all_keys_same:
                         description += f"{indent}    (Tous les objets ont les mêmes clés: {sorted(list(first_item_keys))})\n"
                    else:
                         description += f"{indent}    (Les objets ont des clés différentes)\n"

                # Décrire la structure du premier élément comme exemple
                description += f"{indent}    Exemple de structure (basé sur le 1er élément):\n"
                description += analyze_structure(data[0], indent + "      ", level + 1, max_depth)

            else:
                # Types mixtes dans la liste
                description += f"{indent}    Types mixtes détectés:\n"
                for type_name, count in element_types.items():
                     description += f"{indent}      - {type_name}: {count} occurrence(s)\n"
                # Optionnellement, on pourrait analyser la structure du premier élément de chaque type
                # Pour la simplicité, on n'analyse que le premier élément global
                description += f"{indent}    Exemple de structure (basé sur le 1er élément):\n"
                description += analyze_structure(data[0], indent + "      ", level + 1, max_depth)

    # Pour les types primitifs, le type a déjà été affiché au début
    elif isinstance(data, (str, int, float, bool)) or data is None:
        # On pourrait ajouter des détails (ex: longueur de la chaîne), mais restons simple
        pass # Déjà géré par l'affichage initial du type

    return description

# --- Fonction Principale ---

def process_json_file(file_path, max_depth=10):
    """
    Charge un fichier JSON, analyse sa structure et l'affiche.
    """
    if not os.path.exists(file_path):
        print(f"Erreur: Le fichier '{file_path}' n'a pas été trouvé.", file=sys.stderr)
        return 1 # Code d'erreur

    print(f"--- Analyse de la structure de '{file_path}' ---")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Charger le JSON
            # Pour les très gros fichiers, envisagez d'utiliser ijson:
            # import ijson
            # parser = ijson.parse(f)
            # ... (logique d'analyse itérative plus complexe)
            data = json.load(f)

    except json.JSONDecodeError as e:
        print(f"\nErreur: Impossible de décoder le JSON dans '{file_path}'.", file=sys.stderr)
        print(f"Détails: {e}", file=sys.stderr)
        return 1 # Code d'erreur
    except Exception as e:
        print(f"\nErreur inattendue lors de la lecture du fichier '{file_path}':", file=sys.stderr)
        print(f"Détails: {e}", file=sys.stderr)
        return 1 # Code d'erreur

    # Analyser et afficher la structure
    print("\nStructure détectée :")
    structure_description = analyze_structure(data, max_depth=max_depth)
    print(structure_description)

    print(f"--- Fin de l'analyse de '{file_path}' ---")
    return 0 # Succès

# --- Point d'Entrée du Script ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Charge un fichier JSON, analyse sa structure et la décrit.",
        epilog="Exemple: python analyze_json.py mon_fichier.json"
    )
    parser.add_argument(
        "json_file",
        help="Chemin vers le fichier JSON à analyser."
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="Profondeur maximale de l'analyse récursive pour éviter les erreurs sur des structures très profondes. (Défaut: 10)"
    )

    args = parser.parse_args()

    exit_code = process_json_file(args.json_file, args.max_depth)
    sys.exit(exit_code)
