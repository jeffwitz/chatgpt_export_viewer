Contribution
============

Mettre en place l’environnement
------------------------------

1. Créez/activez votre virtualenv.
2. Installez Flask et les dépendances souhaitées (``python-magic`` facultatif).
3. Pour la documentation, installez les dépendances de dev (incluant le thème):
   ``pip install -r requirements-dev.txt``.

Construire la documentation
---------------------------

```bash
cd docs
sphinx-build -b html . _build/html
```

La sortie HTML se trouve dans ``docs/_build/html``. Pour un rafraîchissement
continu, utilisez ``sphinx-autobuild``.

Style de code
-------------

* Python : PEP 8 + annotations de type, fonctions courtes et testables.
* JavaScript : const/let appropriés, commentaires uniquement pour les blocs non
  triviaux.
* CSS/HTML : privilégier la clarté et les classes descriptives.

Tests recommandés
-----------------

* ``python -m compileall app.py app_core`` pour vérifier la syntaxe.
* Ajoutez des tests unitaires ciblant ``app_core.parsing`` et ``app_core.ingest``
  dès que des évolutions logiques sont introduites.
