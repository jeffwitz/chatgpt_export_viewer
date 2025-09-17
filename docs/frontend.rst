Front-end et rendu
==================

Rendu des mathématiques
-----------------------

* ``static/katex.min.js`` et ``static/auto-render.min.js`` sont chargés depuis le
  template ``templates/index.html``.
* Après le rendu d’une conversation, ``displayConversation`` appelle
  ``renderMathInElement`` (cf. ``static/script.js``) avec les délimiteurs
  ``$...$``, ``$$...$$`` ainsi que ``\(\)`` / ``\[\]``.
* ``throwOnError`` est désactivé pour afficher les expressions même en cas de
  syntaxe incomplète.

Si KaTeX n’est pas chargé (erreur réseau, chemin incorrect), la fonction est
simplement ignorée et la console affiche un message.

Polices et assets
-----------------

* Les feuilles de style n’incluent plus d’``@import`` distant : tout repose sur
  les polices locales disponibles sur la machine (``system-ui``, ``Segoe UI``,
  etc.), garantissant un usage hors-ligne.
* Les polices KaTeX nécessaires au rendu mathématique sont livrées dans
  ``static/fonts``.

Gestion des assets
------------------

Le front n’effectue pas de détection supplémentaire :

1. ``currentFolderData.asset_mapping`` convertit les ``asset_pointer`` en noms de
   fichiers.
2. ``currentFolderData.file_types`` indique le MIME ou une info textuelle.
3. ``displayConversation`` décide du rendu :

   - ``image/*`` → ``<img>`` responsive,
   - ``audio/*`` → ``<audio controls>``,
   - autres → lien de téléchargement.

Les cases à cocher « Média/Fichiers », « Audio uniquement » et « Images uniquement »
filtrent la liste côté client via ``updateDisplayedConversationList``.

Coloration du code
------------------

Les blocs ``<pre><code>`` sont décorés via un surlignage maison : quelques
regex identifient chaînes, commentaires, nombres et mots-clés pour Python,
JavaScript/C, HTML et CSS. La fonction est volontairement légère (pas de
parsing complet) mais améliore la lisibilité hors-ligne sans dépendance
externe.

Recherche côté client
---------------------

* La recherche par titre utilise un filtrage local (``updateDisplayedConversationList``).
* Le champ global déclenche (après un ``debounce``) un appel ``/search`` ; les
  résultats sont surlignés dans la liste.

Points d’attention UI
---------------------

* XSS : ``markdown-it`` est configuré avec ``html: true``. Prévoir un nettoyage
  (ex. DOMPurify) si des exports non fiables sont chargés.
* Accessibilité : l’icône d’asset est purement décorative ; ajouter un ``sr-only``
  peut aider les lecteurs d’écran.
