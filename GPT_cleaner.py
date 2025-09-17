#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import sys
import os
import argparse # Pour gérer les arguments de la ligne de commande
import csv      # Pour écrire correctement le fichier de sortie (gère les virgules dans les titres)

def calculate_conversation_text_length(conversation_data):
    """
    Calcule la longueur totale du texte dans tous les messages d'une conversation.
    """
    total_length = 0
    mapping = conversation_data.get("mapping", {})
    if not isinstance(mapping, dict):
        return 0

    for node_id, node_data in mapping.items():
        if not isinstance(node_data, dict):
            continue

        message = node_data.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, dict):
                parts = content.get("parts")
                if isinstance(parts, list):
                    for part in parts:
                        if isinstance(part, str):
                            total_length += len(part)
    return total_length

def sort_and_output(json_file_path, output_txt_file="analyse.txt"):
    """
    Charge un fichier JSON de conversations ChatGPT, calcule la taille totale
    du texte pour chaque conversation, les trie par taille décroissante,
    affiche les titres/tailles, et crée un fichier texte avec Titre,UUID.
    """
    if not os.path.exists(json_file_path):
        print(f"Erreur: Le fichier JSON '{json_file_path}' n'a pas été trouvé.", file=sys.stderr)
        return 1 # Code d'erreur

    print(f"--- Traitement de '{json_file_path}' (tri par taille de message) ---")

    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            conversations = json.load(f)
    except json.JSONDecodeError as e:
        print(f"\nErreur: Impossible de décoder le JSON dans '{json_file_path}'.", file=sys.stderr)
        print(f"Détails: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nErreur inattendue lors de la lecture du fichier '{json_file_path}':", file=sys.stderr)
        print(f"Détails: {e}", file=sys.stderr)
        return 1

    if not isinstance(conversations, list):
        print(f"Erreur: Le contenu de '{json_file_path}' n'est pas une liste JSON comme attendu.", file=sys.stderr)
        return 1

    # --- Calcul de la taille et stockage temporaire ---
    conversations_with_info = []
    print("Calcul des tailles des conversations...")
    for index, conv in enumerate(conversations):
        if not isinstance(conv, dict):
             print(f"Avertissement: Élément {index} n'est pas un dictionnaire, ignoré.", file=sys.stderr)
             continue

        length = calculate_conversation_text_length(conv)
        title = conv.get("title", "[Titre Manquant]")
        # Récupère l'ID de la conversation (UUID)
        conv_id = conv.get("conversation_id", "[ID Manquant]")

        conversations_with_info.append({
            "title": title,
            "length": length,
            "id": conv_id # Stocke l'UUID ici
        })
        if (index + 1) % 100 == 0:
             print(f"  {index + 1}/{len(conversations)} conversations traitées...")

    print("Calcul des tailles terminé.")

    # --- Tri des conversations par taille décroissante ---
    print("Tri des conversations...")
    sorted_conversations = sorted(
        conversations_with_info,
        key=lambda item: item['length'],
        reverse=True
    )
    print("Tri terminé.")

    # --- Affichage des titres et tailles triés (Console) ---
    print(f"\n--- Conversations triées par taille totale de texte (décroissant) ---")
    if not sorted_conversations:
        print("(Aucune conversation valide trouvée ou traitée)")
    else:
        max_len_digits = 0
        if sorted_conversations:
             max_len_digits = len(str(sorted_conversations[0]['length']))
        max_idx_digits = len(str(len(sorted_conversations)))

        print(f"{'#'.rjust(max_idx_digits)} | {'Taille'.rjust(max_len_digits)} | Titre")
        print(f"{'-'*(max_idx_digits+1)}+{'-'*(max_len_digits+2)}+{'-'*20}")

        for i, conv_info in enumerate(sorted_conversations):
            idx_str = str(i + 1).rjust(max_idx_digits)
            len_str = str(conv_info['length']).rjust(max_len_digits)
            title = conv_info['title']
            print(f"{idx_str} | {len_str} | {title}")

    # --- Écriture du fichier texte de sortie (analyse.txt) ---
    print(f"\nÉcriture du fichier de sortie '{output_txt_file}'...")
    try:
        with open(output_txt_file, 'w', newline='', encoding='utf-8') as outfile:
            # Utiliser csv.writer pour gérer correctement les virgules/quotes dans les titres
            writer = csv.writer(outfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            # N'écrit PAS d'en-tête, juste les données comme demandé
            for conv_info in sorted_conversations:
                title = conv_info['title']
                uuid = conv_info['id']
                writer.writerow([title, uuid])
        print(f"Fichier '{output_txt_file}' créé avec succès.")

    except IOError as e:
         print(f"\nErreur: Impossible d'écrire dans le fichier '{output_txt_file}'.", file=sys.stderr)
         print(f"Détails: {e}", file=sys.stderr)
         return 1 # Code d'erreur différent pour l'écriture
    except Exception as e:
         print(f"\nErreur inattendue lors de l'écriture du fichier '{output_txt_file}':", file=sys.stderr)
         print(f"Détails: {e}", file=sys.stderr)
         return 1


    print(f"\n--- Fin du traitement de '{json_file_path}' ---")
    return 0 # Succès

# --- Point d'Entrée du Script ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Charge conversations.json, trie par taille texte décroissante, affiche les résultats et crée analyse.txt (Titre,UUID).",
        epilog="Exemple: python sort_chatgpt_output.py chemin/vers/conversations.json"
    )
    parser.add_argument(
        "json_file",
        help="Chemin vers le fichier conversations.json à analyser."
    )
    parser.add_argument(
        "-o", "--output",
        default="analyse.txt",
        help="Nom du fichier texte de sortie (défaut: analyse.txt)."
    )

    args = parser.parse_args()

    exit_code = sort_and_output(args.json_file, args.output)
    sys.exit(exit_code)
