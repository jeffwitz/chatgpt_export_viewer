Gestion des données
===================

Identification des types de fichiers
------------------------------------

Le typage MIME repose sur ``detect_file_types`` (``app_core/parsing``) :

* la liste des fichiers ciblés est déduite du ``asset_mapping`` extrait de
  ``chat.html`` ;
* pour chaque fichier, le cache ``file_type.json`` est relu si présent ;
* si le type est inconnu ou marqué « Error », la fonction tente :

  1. ``python-magic`` (s’il est installé) pour lire l’en-tête binaire ;
  2. ``mimetypes.guess_type`` comme repli pur Python ;
  3. sinon, un message « application/octet-stream ».

Les résultats sont écrits dans ``file_type.json`` afin d’éviter les détections
répétées. Ce fichier est également stocké dans SQLite (colonne
``file_types_json``) pour être renvoyé instantanément.

Détection des assets et de l’audio
---------------------------------

* ``conversation_has_asset`` traverse la structure ``mapping`` des messages et
  renvoie ``True`` dès qu’un ``asset_pointer`` est trouvé.
* ``conversation_has_audio`` utilise le mapping pour récupérer le nom de fichier
  et vérifie :

  - le type MIME stocké (``audio/`` ou mots-clés « wave audio », « ogg data »…)
  - l’extension ``.wav``, ``.mp3``, ``.ogg``, ``.m4a``, ``.aac`` ou ``.flac``.

Le front consomme ces flags pour filtrer et afficher les icônes adéquates.

Conservation de la structure JSON
---------------------------------

Les conversations stockées en base sont le JSON original sérialisé sans
modification. Lorsqu’elles sont réhydratées, ``mapping`` et ``message`` conservent
les champs nécessaires au front (y compris les structures d’outils).

