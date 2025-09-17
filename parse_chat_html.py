#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import re
import argparse
import sys
from bs4 import BeautifulSoup # Pour parser le HTML

# --- Configuration ---
# TODO: AJUSTER CES SÉLECTEURS CSS APRÈS INSPECTION DE chat.html !
# Ce sont des suppositions génériques.
CONVERSATION_SELECTOR = "body > div"  # Bloc conversation (souvent une div directe sous body)
MESSAGE_SELECTOR = "div.text-base" # Un exemple basé sur l'UI web, peut être très différent
ROLE_ATTRIBUTE = "data-message-author-role" # Attribut qui pourrait contenir "user" ou "assistant"
CONTENT_SELECTOR = "div.markdown" # Div contenant le contenu rendu (prose-...)
FILE_LINK_CONTAINER_SELECTOR = "div.mt-1" # Conteneur potentiel pour le lien [File]: (à trouver !)

# Regex pour extraire le nom de fichier depuis "[File]: nom_fichier.ext"
FILE_LINK_REGEX = re.compile(r"\[File\]:\s*(\S+)")

# --- Fonctions ---

def extract_role_from_element(message_element):
    """Tente d'extraire le rôle à partir d'un attribut data-* ou de classes."""
    # Priorité à l'attribut data-* s'il existe
    role = message_element.get(ROLE_ATTRIBUTE)
    if role in ["user", "assistant", "tool", "system"]:
        return role

    # Sinon, essaie avec des classes CSS (exemples à adapter)
    classes = message_element.get('class', [])
    if 'message-user' in classes: return 'user' # Exemple
    if 'message-chatgpt' in classes: return 'assistant' # Exemple
    if 'message-tool' in classes: return 'tool' # Exemple

    # Fallback très basique basé sur le texte (peu fiable)
    # text_preview = message_element.get_text(" ", strip=True)[:50]
    # if text_preview.startswith("user"): return "user"
    # if text_preview.startswith("ChatGPT"): return "assistant"

    return "unknown"

def parse_html_and_extract(html_filepath, output_json_filepath):
    """
    Parse le fichier chat.html, extrait les conversations, messages, et liens d'images,
    et sauvegarde le résultat dans un fichier JSON structuré.
    """
    if not os.path.exists(html_filepath):
        print(f"Erreur: Fichier HTML introuvable - '{html_filepath}'", file=sys.stderr)
        return False

    print(f"Parsing de '{html_filepath}'...")
    # Structure principale: { conv_id_ou_titre: [liste_messages], ... }
    # Chaque message: { role: "...", text: "...", image_filename: "..." ou None }
    structured_conversations = []
    conversation_counter = 0

    try:
        with open(html_filepath, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'lxml') # Utilise lxml si possible
    except ImportError:
        print("Avertissement: lxml non trouvé, utilisation de html.parser.")
        try:
            with open(html_filepath, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
        except Exception as e:
            print(f"Erreur ouverture/parsing initial HTML: {e}", file=sys.stderr); return False
    except Exception as e:
         print(f"Erreur ouverture/parsing initial HTML: {e}", file=sys.stderr); return False

    # --- Logique de Parsing HTML (À ADAPTER FORTEMENT) ---

    # Tente de trouver des blocs de conversation distincts
    # Adapte CONVERSATION_SELECTOR !
    # Si chat.html ne sépare pas les conversations, il faudra une autre logique
    # (ex: détecter les titres H1/H2 comme début de nouvelle conv)
    conversation_blocks = soup.select(CONVERSATION_SELECTOR)
    if not conversation_blocks or len(conversation_blocks) == 1: # Si un seul bloc (body?) ou rien
        print("Avertissement: Pas de blocs de conversation distincts trouvés avec le sélecteur."
              " Tentative de détection par titres H1/H2...")
        # Alternative: trouver tous les H1/H2 et traiter les éléments entre eux
        potential_starts = soup.find_all(['h1', 'h2'])
        if potential_starts:
             # Logique plus complexe ici pour regrouper les messages sous chaque titre
             # Pour l'instant, traitons tout comme une seule conversation si échec
             print("Logique de regroupement par titre non implémentée, traitement global.")
             conversation_blocks = [soup.body] if soup.body else []
        else:
             print("Aucun titre H1/H2 trouvé non plus. Traitement global.")
             conversation_blocks = [soup.body] if soup.body else []


    print(f"Traitement de {len(conversation_blocks)} bloc(s) de conversation trouvé(s).")

    for conv_block in conversation_blocks:
        if not conv_block: continue
        conversation_counter += 1

        # Extrait le titre - Adapte le sélecteur !
        title_element = conv_block.select_one('h1, h2') # Simple supposition
        conv_title = title_element.get_text(strip=True) if title_element else f"Conversation Extraite #{conversation_counter}"

        current_conversation_messages = []
        # Trouve tous les éléments message dans ce bloc
        # Adapte MESSAGE_SELECTOR !
        message_elements = conv_block.select(MESSAGE_SELECTOR)
        print(f"  Conv '{conv_title}': Trouvé {len(message_elements)} éléments message avec sélecteur '{MESSAGE_SELECTOR}'.")

        if not message_elements:
            print(f"  Aucun message trouvé pour cette conversation. Vérifiez MESSAGE_SELECTOR.")
            continue # Passe à la conversation suivante si aucun message

        # Parcours des messages
        for msg_element in message_elements:
            role = extract_role_from_element(msg_element) # Extrait le rôle

            # Extrait le contenu textuel/HTML - Adapte CONTENT_SELECTOR !
            content_element = msg_element.select_one(CONTENT_SELECTOR)
            # Préférer garder le HTML interne pour markdown-it ou autre traitement ultérieur ?
            # content_html = ''.join(str(c) for c in content_element.contents) if content_element else ""
            # Ou juste le texte brut :
            content_text = content_element.get_text(separator="\n", strip=True) if content_element else "" # Garde les sauts de ligne internes

            # --- Recherche du lien [File]: ---
            image_filename = None
            # Hypothèse 1: Le lien est dans un élément spécifique DANS le message actuel
            # Adapte FILE_LINK_CONTAINER_SELECTOR !
            file_link_container = msg_element.select_one(FILE_LINK_CONTAINER_SELECTOR)
            if file_link_container:
                 match = FILE_LINK_REGEX.search(file_link_container.get_text())
                 if match:
                     image_filename = match.group(1).strip()
                     print(f"    [File] trouvé dans conteneur dédié : {image_filename}")

            # Hypothèse 2: Le lien est directement dans le contenu textuel principal
            # (moins probable si le HTML est structuré, mais possible)
            if not image_filename:
                match = FILE_LINK_REGEX.search(content_text)
                if match:
                    image_filename = match.group(1).strip()
                    print(f"    [File] trouvé DANS le contenu : {image_filename}")
                    # Optionnel: Nettoyer le texte du contenu si nécessaire
                    # content_text = FILE_LINK_REGEX.sub('', content_text).strip()


            current_conversation_messages.append({
                "role": role,
                "text": content_text, # Garde le texte brut/HTML extrait
                "image_filename": image_filename # Peut être None
            })

        if current_conversation_messages:
             structured_conversations.append({
                 # Utilise le titre comme ID temporaire (pas idéal mais simple)
                 # Il faudrait idéalement croiser avec conversations.json pour les vrais IDs
                 "id": conv_title.lower().replace(" ", "_") + f"_{conversation_counter}",
                 "title": conv_title,
                 "messages": current_conversation_messages
             })
        else:
             print(f"  Aucun message extrait pour '{conv_title}'.")
        print("-" * 20) # Séparateur visuel

    # --- Fin du Parsing ---

    if not structured_conversations:
         # *** LIGNE CORRIGÉE ***
         print("Erreur: Aucune donnée de conversation n'a pu être extraite. Vérifiez les sélecteurs CSS et la structure du fichier HTML.", file=sys.stderr)
         return False

    # --- Sauvegarde des données structurées ---
    print(f"\nExtraction terminée. {len(structured_conversations)} conversation(s) structurée(s).")
    try:
        print(f"Sauvegarde des données dans '{output_json_filepath}'...")
        with open(output_json_filepath, 'w', encoding='utf-8') as outfile:
            json.dump(structured_conversations, outfile, indent=2, ensure_ascii=False)
        print("Sauvegarde réussie.")
        return True
    except IOError as e:
        print(f"Erreur lors de la sauvegarde dans '{output_json_filepath}': {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Erreur inattendue lors de la sauvegarde JSON: {e}", file=sys.stderr)
        return False


# --- Point d'Entrée du Script ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse chat.html pour extraire les conversations, messages et liens d'images DALL-E.",
        epilog="Exemple: python parse_chat_html.py chemin/vers/chat.html données_extraites.json"
    )
    parser.add_argument(
        "html_file",
        help="Chemin vers le fichier chat.html de l'export ChatGPT."
    )
    parser.add_argument(
        "output_json",
        help="Chemin vers le fichier JSON de sortie où sauvegarder les données structurées."
    )
    # Optionnel: Ajouter un argument pour le fichier conversations.json si on veut croiser les IDs/Titres

    args = parser.parse_args()

    # Vérifie si le fichier de sortie existe déjà (optionnel)
    if os.path.exists(args.output_json):
         overwrite = input(f"Le fichier de sortie '{args.output_json}' existe déjà. Écraser ? (o/N): ").lower()
         if overwrite != 'o':
             print("Opération annulée.")
             sys.exit(0)

    # Lance le parsing et la sauvegarde
    success = parse_html_and_extract(args.html_file, args.output_json)

    if success:
        sys.exit(0) # Succès
    else:
        sys.exit(1) # Erreur
