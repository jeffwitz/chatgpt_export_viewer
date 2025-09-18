# ChatGPT Export Viewer (SQLite Edition)

Cette application Flask permet de parcourir localement un export ChatGPT (`conversations.json`, `chat.html` et fichiers associés). Elle s’appuie désormais sur SQLite pour éviter de re-parser les fichiers à chaque requête.

## Fonctionnalités principales
- Interface web Bootstrap pour naviguer dans les conversations, afficher les messages et pièces jointes, copier en Markdown, rendre KaTeX.
- Détection des assets (images, audio, autres fichiers) avec typage MIME automatique.
- Recherche plein texte via l’extension FTS5 de SQLite (Whoosh n’est plus requis).
- Scripts utilitaires pour inspecter et nettoyer les exports (`Analyse_json.py`, `GPT_cleaner.py`, etc.).
- Fonctionnement 100 % hors-ligne (polices et librairies statiques fournies localement).
- Coloration syntaxique basique (Python, JS/C, HTML, CSS) sans dépendance externe.
- Filtres locaux pour repérer les conversations avec médias, audio ou images uniquement.

## Installation rapide
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # ou installer Flask/ijson/python-magic si besoin
```

> Remarque : le projet n’introduit pas de nouvelle dépendance obligatoire en dehors de la bibliothèque standard. Si `python-magic` est disponible, la détection MIME est plus précise.

## Lancement du serveur
```bash
source .venv/bin/activate  # ou activez l'environnement de votre choix
FLASK_APP=app python -m flask run --no-debugger --no-reload --host 0.0.0.0 --port 5001
```

Placez vos dossiers d’export (ceux qui contiennent `conversations.json` et `chat.html`) à la racine du projet : ils sont détectés automatiquement.

## Importer un export ZIP
- Dans l’interface, utilisez le formulaire « Importer un export ZIP » pour téléverser l’archive reçue depuis ChatGPT.
- Indiquez le chemin de destination : il peut pointer vers n’importe quel support monté (SSD externe, NAS, etc.).
- L’application décompresse l’archive, crée le dossier d’export, l’indexe en SQLite et l’ajoute automatiquement à la liste.
- Vous pouvez laisser le champ « Nom du dossier » vide pour qu’il soit déduit du nom du fichier ZIP.

## Documentation Sphinx

Une documentation développeur est disponible dans `docs/`. Pour la construire :

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt  # inclut sphinx-rtd-theme
cd docs
sphinx-build -b html . _build/html
```

Les pages générées décrivent l’architecture serveur, la détection des fichiers,
et le rendu front-end (maths, assets, recherche).

## Persistance SQLite
- Le fichier de base de données est créé dans `app_data.db` à la racine.
- Lors du premier chargement d’un dossier, le parsing complet est effectué puis stocké en base (conversations, assets, types MIME).
- Les requêtes suivantes lisent directement les données en SQLite, ce qui évite le délai initial.
- Une table FTS5 (`conversation_search`) gère la recherche. Si FTS5 n’est pas disponible dans votre SQLite, la route `/search` renvoie une erreur 501.

### Scripts utilitaires
Un script CLI est fourni pour (ré)ingérer un export manuellement :
```bash
source .venv/bin/activate
python scripts/refresh_export.py 06042025
```

## Développement
- Code Python formaté selon PEP 8, annotations de type ajoutées progressivement.
- Modules côté serveur :
  - `app_core/parsing.py` : logique d’extraction (reprend le comportement historique).
  - `app_core/db.py` : connexion SQLite.
  - `app_core/schema.py` : création/mises à jour du schéma.
  - `app_core/ingest.py` : pipeline d’ingestion + recherche.
- Front-end inchangé (`static/script.js`) : la logique de rendu reste côté navigateur.

## Tests rapides
```bash
source .venv/bin/activate
python -m compileall app.py app_core
python -m pytest  # si vous ajoutez des tests
```

## Roadmap
- Ajouter des tests unitaires sur `app_core.parsing`.
- Gérer des exports très volumineux via ingestion incrémentale.
- Exposer un bouton UI pour déclencher une ré-indexation manuelle.
