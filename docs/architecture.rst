Architecture serveur
====================

Vue d’ensemble
--------------

Le serveur Flask (`app.py`) délègue la quasi-totalité de la logique métier à
``app_core`` pour faciliter les tests et la maintenance.

Flux d’une requête ``/conversations``
-------------------------------------

1. **Validation** : le nom de dossier est vérifié via ``_validate_folder_name``
   (nettoyage des ``..`` et contrôle du périmètre).
2. **Connexion SQLite** : ouverture d’une connexion via
   ``app_core.db.connection_scope`` qui configure les PRAGMA (WAL, foreign keys).
3. **Ingestion conditionnelle** : ``app_core.ingest.ensure_export`` compare les
   dates de modification de ``conversations.json`` et ``chat.html`` avec les
   métadonnées stockées dans la table ``exports``.
   - Si les fichiers sont inchangés, les conversations sont retournées depuis la
     base (JSON préservé à l’identique).
   - Sinon le pipeline de parsing est relancé (voir section « Parsing »), les
     résultats sont (ré)insérés en base puis renvoyés au client.
4. **Réponse** : le JSON retourné contient ``conversations``, ``asset_mapping``
   et ``file_types`` exactement comme avant la refactorisation.

Persistence SQLite
------------------

``app_core/schema.py`` crée trois éléments principaux :

- ``exports`` : suivi d’un dossier (mtimes, JSON d’assets, JSON de types MIME).
- ``conversations`` : JSON complet sérialisé, flags ``has_asset`` /
  ``has_audio`` pré-calculés, ordre d’origine (``sort_index``).
- ``conversation_search`` : table virtuelle FTS5 (``title`` + contenu aplati)
  pour la route ``/search``.

L’insertion utilise ``_bulk_insert_conversations`` qui :

- calcule les flags via ``conversation_has_asset`` et ``conversation_has_audio`` ;
- sérialise la conversation en UTF-8 sans perte ;
- alimente FTS si l’extension est disponible.

Parsing et extraction
---------------------

La logique historique est conservée dans ``app_core/parsing`` :

- ``load_conversations_json`` lit la liste brute.
- ``load_asset_mapping`` cherche ``assetsJson`` dans ``chat.html`` via la même
  expression régulière que précédemment.
- ``detect_file_types`` utilise ``python-magic`` si disponible, sinon
  ``mimetypes`` (cf. section dédiée).

Le module renvoie un ``ExportData`` prêt à être stocké ou renvoyé tel quel.

Recherche plein texte
---------------------

La route ``/search`` s’appuie sur ``conversation_search MATCH ?`` (FTS5). Les
variantes Whoosh ont été retirées. Si FTS n’est pas présent dans le SQLite de
l’hôte, un message 501 est renvoyé et l’interface peut désactiver la recherche.

