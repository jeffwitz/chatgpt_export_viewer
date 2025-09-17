// static/script.js (Version Complète avec Correction Détection MIME Assouplie)

// --- Global Variables ---
let currentFolderData = {
    conversations: [],
    asset_mapping: {},
    file_types: {}
};
let md; // Instance Markdown-it
const badCharsRegex = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F\uE000-\uF8FF]/gu; // Regex pour caractères invalides

// --- DOM Elements ---
const folderSelector = document.getElementById('folder-selector');
const conversationList = document.getElementById('conversation-list');
const conversationView = document.getElementById('conversation-view');
const mainContent = document.getElementById('main-content');
const loadingIndicator = document.getElementById('loading-indicator');
const searchBox = document.getElementById('search-box');
const filterAssetsCheckbox = document.getElementById('filter-images-checkbox');
const filterAudioCheckbox = document.getElementById('filter-audio-checkbox');
const searchStatus = document.getElementById('search-status'); // Pour afficher statut/résultats recherche

// --- Variable globale pour le délai de recherche ---
let searchDebounceTimeout = null;
const DEBOUNCE_DELAY = 400; // Délai en ms avant de lancer la recherche après la saisie

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM Loaded. Initializing.");
    // Initialise Markdown-it
    md = window.markdownit({ html: true, linkify: true, typographer: true });

    // --- Event Listeners ---
    if (folderSelector) { folderSelector.addEventListener('change', loadConversationsForFolder); }
    else { console.error("Folder selector element not found."); }
    if (conversationList) { conversationList.addEventListener('click', handleConversationClick); }
    else { console.error("Conversation list element not found."); }
    if (searchBox) { searchBox.addEventListener('input', handleSearchInput); } // Utilise debounce
    else { console.error("Search box element not found."); }
    // Les filtres appellent updateDisplayedConversationList directement
    if (filterAssetsCheckbox) { filterAssetsCheckbox.addEventListener('change', updateDisplayedConversationList); }
    else { console.error("Assets filter checkbox not found."); }
    if (filterAudioCheckbox) { filterAudioCheckbox.addEventListener('change', updateDisplayedConversationList); }
    else { console.error("Audio filter checkbox not found."); }
    document.addEventListener('keydown', handleKeyboardNavigation);
    // Listener pour "Copier Tout" attaché dynamiquement dans displayConversation

    // Initial Load Logic
    if (folderSelector && folderSelector.options.length > 1) {
        folderSelector.selectedIndex = 1; // Sélectionne le premier vrai dossier
        console.log(`Initial load: Selecting first folder '${folderSelector.value}'`);
        folderSelector.dispatchEvent(new Event('change')); // Déclenche chargement
    } else { console.log("Initial load: No folders found or only default option."); }
});

// --- Utility Functions ---

/** Nettoie les caractères indésirables d'une chaîne. */
function cleanString(inputText) {
    if (typeof inputText !== 'string') return inputText;
    return inputText.replace(badCharsRegex, '');
}

/** Copie du texte dans le presse-papiers et affiche un retour visuel sur un bouton. */
async function copyTextToClipboard(text, buttonElement) {
    // Fallback si navigator.clipboard non dispo
    const doFeedback = () => {
        if (buttonElement) {
            const originalHtml = buttonElement.innerHTML;
            const originalTitle = buttonElement.title;
            buttonElement.innerHTML = '<i class="fas fa-check"></i> Copié!';
            buttonElement.classList.add('copied');
            buttonElement.disabled = true;
            buttonElement.title = 'Copié !';
            setTimeout(() => {
                buttonElement.innerHTML = originalHtml;
                buttonElement.classList.remove('copied');
                buttonElement.disabled = false;
                buttonElement.title = originalTitle;
            }, 1500);
        }
    };
    if (navigator.clipboard && window.isSecureContext) {
        try {
            await navigator.clipboard.writeText(text);
            doFeedback();
        } catch (err) {
            console.error('Failed to copy: ', err);
            alert('Erreur copie.');
            if (buttonElement) buttonElement.disabled = false;
        }
    } else {
        // Fallback ancien navigateur ou contexte non sécurisé
        try {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.left = '-9999px';
            document.body.appendChild(textarea);
            textarea.focus();
            textarea.select();
            const successful = document.execCommand('copy');
            document.body.removeChild(textarea);
            if (successful) {
                doFeedback();
            } else {
                alert('Copie non supportée.');
            }
        } catch (err) {
            alert('Copie non supportée.');
        }
    }
}


// --- Core Application Logic ---

/** Charge les données de base (conversions, mapping, types) pour un dossier. */
async function loadConversationsForFolder() {
    const selectedFolder = folderSelector.value;
    console.log(`Folder selected: ${selectedFolder}`);
    resetUI(); // Réinitialise l'interface
    if (!selectedFolder) { setLoading(false); return; }
    setLoading(true);
    try {
        // Appel API qui récupère les données ET assure l'indexation côté serveur
        const response = await fetch(`/conversations?folder_name=${encodeURIComponent(selectedFolder)}`);
        if (!response.ok) { const errData = await response.json().catch(()=>({})); throw new Error(errData.error || `HTTP ${response.status}`); }
        const data = await response.json();
        console.log("Base data received:", data);
        currentFolderData = data; // Stocker les données
        preprocessConversationData(); // Ajouter infos calculées (has_asset, id...)
        updateDisplayedConversationList(); // Afficher la liste initiale
    } catch (error) {
        console.error('Error loading folder data:', error);
        conversationView.innerHTML = `<p style="color:red;padding:20px;">Erreur chargement: ${error.message}</p>`;
        conversationList.innerHTML = '<li class="empty-list">Erreur chargement.</li>';
        setSearchStatus('');
    } finally {
        setLoading(false);
    }
}

/** Réinitialise l'interface utilisateur à son état par défaut. */
function resetUI() {
    conversationList.innerHTML = '';
    conversationView.innerHTML = '<h2>Sélectionnez une conversation</h2><p>Cliquez sur un titre.</p><div id="conversation-content"></div>';
    searchBox.value = ''; filterAssetsCheckbox.checked = false; filterAudioCheckbox.checked = false;
    currentFolderData = { conversations: [], asset_mapping: {}, file_types: {} };
    document.querySelectorAll('#conversation-list li.selected').forEach(i => i.classList.remove('selected'));
    setSearchStatus('');
    clearTimeout(searchDebounceTimeout);
    setLoading(false);
}

/** Affiche/cache l'indicateur de chargement global. */
function setLoading(isLoading) {
    loadingIndicator.style.display = isLoading ? 'block' : 'none';
}

/** Met à jour le message sous la barre de recherche. */
function setSearchStatus(message) {
    if (!searchStatus) return;
    searchStatus.textContent = message || '';
    searchStatus.style.display = message ? 'block' : 'none';
}

/** Ajoute les informations calculées (has_asset, has_audio, id) aux conversations. */
function preprocessConversationData() {
    if (!currentFolderData.conversations?.length) { console.warn("preprocess: No convos."); currentFolderData.conversations = []; return; }
    currentFolderData.conversations.forEach((conv, index) => {
        if (typeof conv !== 'object' || conv === null) { console.warn(`preprocess: Invalid item @ ${index}.`); conv = { id: `invalid_${index}`, title: '[Inv]', mapping: {} }; currentFolderData.conversations[index] = conv; return; }
        conv.has_asset = conversationHasAsset(conv); conv.has_audio = conversationHasAudio(conv);
        let id = conv.conversation_id || conv.id;
        if (!id || typeof id !== 'string' || id.startsWith('invalid_')) { id = `genid_${index}`; }
        conv.id = id;
        if (!conv.id) { console.error(`preprocess: FATAL ID fail @ ${index}`); conv.id = `errid_${index}`; }
    });
    console.log("preprocess: Complete.");
}

/** Vérifie si une conversation contient une référence à un asset. */
function conversationHasAsset(conversation) {
    if (!conversation?.mapping || typeof conversation.mapping !== 'object') return false;
    for (const nodeId in conversation.mapping) {
        const node = conversation.mapping[nodeId]; if (!node) continue;
        if (node.message?.content?.parts?.some(p => p?.asset_pointer)) return true;
        if (node.message?.author?.role === 'tool' && node.message?.metadata?.aggregate_result?.message?.content?.parts?.some(p => p?.asset_pointer)) return true;
    } return false;
}

/** Vérifie spécifiquement les assets audio. */
function conversationHasAudio(conversation) {
     if (!conversation?.mapping || typeof conversation.mapping !== 'object') return false;
     const am = currentFolderData.asset_mapping||{}; const tm = currentFolderData.file_types||{};
     for (const id in conversation.mapping) {
         const n = conversation.mapping[id]; if (!n?.message?.content?.parts || !Array.isArray(n.message.content.parts)) continue;
         for (const p of n.message.content.parts) {
             if (p?.asset_pointer && am[p.asset_pointer]) {
                 const f = am[p.asset_pointer]; const et = tm[f];
                 // Vérification assouplie basée sur le type MIME explicite ou l'extension
                 if (et) {
                     const l = et.toLowerCase();
                     if (l.startsWith('audio/') || ['mpeg layer 3', 'wave audio', 'ogg data', 'flac audio', 'aac audio'].some(keyword => l.includes(keyword))) return true;
                 }
                 if (/\.(wav|mp3|ogg|m4a|aac|flac)$/i.test(f)) return true; // Fallback extension
             }
         }
     } return false;
}

/** Met à jour la liste affichée basée sur FILTRE TITRE et CHECKBOXES. */
function updateDisplayedConversationList() {
    console.log("updateDisplayedConversationList: Based on title search and filters.");
    const searchTerm = searchBox.value.toLowerCase().trim(); // Recherche TITRE
    const filterAssets = filterAssetsCheckbox.checked;
    const filterAudio = filterAudioCheckbox.checked;
    conversationList.innerHTML = '';
    if (!searchTerm) setSearchStatus('');

    if (!currentFolderData.conversations?.length) { conversationList.innerHTML = '<li class="empty-list">Aucune conversation.</li>'; return; }

    const filtered = currentFolderData.conversations.filter(c => {
        if (typeof c !== 'object' || !c?.id) return false;
        const titleMatch = !searchTerm || (c.title && typeof c.title === 'string' && c.title.toLowerCase().includes(searchTerm));
        const assetMatch = !filterAssets || c.has_asset;
        const audioMatch = !filterAudio || c.has_audio;
        return titleMatch && assetMatch && audioMatch;
    });

    if (filtered.length > 0) {
        filtered.forEach(c => {
            const l = document.createElement('li'); l.textContent = c.title || '[Sans Titre]';
            if (c.id) l.dataset.conversationId = c.id; else { l.style.opacity="0.5"; l.title="Err ID"; }
            if (c.has_asset) l.innerHTML+=' <i class="fas fa-photo-video" style="opacity:0.6;font-size:0.8em;" title="Média/Fichier"></i>';
            conversationList.appendChild(l);
        });
        if (searchTerm || filterAssets || filterAudio) setSearchStatus(`${filtered.length} résultat(s) pour filtres/titre.`);
    } else {
        if (searchTerm) conversationList.innerHTML = '<li class="empty-list">Aucun titre ne correspond.</li>';
        else if (filterAssets || filterAudio) conversationList.innerHTML = '<li class="empty-list">Aucun résultat avec ces filtres.</li>';
        else conversationList.innerHTML = '<li class="empty-list">Aucune conversation valide.</li>';
    }
}


/** Gère la saisie dans searchBox : lance recherche Whoosh ou restaure liste standard. */
function handleSearchInput() {
    clearTimeout(searchDebounceTimeout);
    const query = searchBox.value.trim();
    const folderName = folderSelector.value;
    if (!folderName) return;

    if (!query) { // Si recherche vidée
        console.log("Search cleared, running updateDisplayedConversationList.");
        updateDisplayedConversationList(); // Restaurer affichage standard
        return;
    }
    // Lancer recherche Whoosh après délai
    setSearchStatus('Recherche...');
    searchDebounceTimeout = setTimeout(() => {
        performSearch(folderName, query);
    }, DEBOUNCE_DELAY);
}

/** Effectue la recherche plein texte via API /search. */
async function performSearch(folderName, query) {
    console.log(`Performing full-text search in '${folderName}' for: '${query}'`);
    setLoading(true);
    setSearchStatus(`Recherche pour "${query}"...`);
    conversationList.innerHTML = '';

    try {
        const response = await fetch(`/search?folder_name=${encodeURIComponent(folderName)}&query=${encodeURIComponent(query)}`);
        console.log("Search API Response Status:", response.status);
        if (!response.ok) { const errData = await response.json().catch(() => ({ error: `HTTP error ${response.status}` })); console.error("Search API Error:", errData); throw new Error(errData.error || `Search error ${response.status}`); }
        const results = await response.json();
        console.log("Search results (raw):", results);
        console.log("Is results an array?", Array.isArray(results));

        displaySearchResults(results); // Afficher résultats Whoosh
        setSearchStatus(`${results.length} résultat(s) pour "${query}" (contenu)`);

    } catch (error) {
        console.error('Error during search fetch/processing:', error);
        conversationList.innerHTML = `<li class="empty-list" style="color:orange;">Erreur recherche.</li>`;
        setSearchStatus(`Erreur recherche: ${error.message}`);
    } finally {
        setLoading(false);
    }
}

/** Affiche les résultats de la recherche Whoosh (liste d'ID/titre). */
function displaySearchResults(results) {
    console.log("--- displaySearchResults called with:", results);
    conversationList.innerHTML = '';
    if (!results || !Array.isArray(results) || results.length === 0) {
        conversationList.innerHTML = '<li class="empty-list">Aucun résultat (contenu).</li>';
        console.log("Displaying 'Aucun résultat' because results empty/invalid.");
        console.log("------------------------------------");
        return;
    }
    console.log(`Attempting to display ${results.length} search results...`);

    results.forEach((conv, index) => {
        console.log(`  Processing result ${index}:`, conv);
        if (typeof conv !== 'object' || !conv.id || typeof conv.title !== 'string') { console.warn(`  Invalid search result item @ ${index}:`, conv); return; }
        const listItem = document.createElement('li');
        listItem.textContent = conv.title || '[Sans Titre]';
        listItem.dataset.conversationId = conv.id;
        const originalConv = currentFolderData.conversations.find(c => c.id === conv.id);
        if (originalConv?.has_asset) listItem.innerHTML += ' <i class="fas fa-photo-video" style="opacity:0.6;font-size:0.8em;" title="Média/Fichier"></i>';
        console.log(`    Created listItem:`, listItem.outerHTML);
        conversationList.appendChild(listItem);
    });
     console.log("--- displaySearchResults finished ---");
}

/** Gère clic sur un item de la liste. */
function handleConversationClick(event) {
     const listItem = event.target.closest('li');
     if (listItem && listItem.dataset.conversationId) { selectConversationItem(listItem); }
}

/** Sélectionne un item et affiche le détail. */
function selectConversationItem(listItem) {
    if (!listItem?.dataset?.conversationId || listItem.dataset.conversationId.startsWith('invalid_') || listItem.dataset.conversationId.startsWith('errid_')) return;
    const conversationId = listItem.dataset.conversationId;
    document.querySelectorAll('#conversation-list li.selected').forEach(i => i.classList.remove('selected'));
    listItem.classList.add('selected'); listItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    displayConversation(conversationId);
}

/** Affiche le contenu détaillé d'une conversation. */
function displayConversation(conversationId) {
    // Reset vue
    conversationView.innerHTML = `<h2>Chargement...</h2><div id="global-actions" style="display: none;"><button id="copy-all-button" title="Copier toute la conversation au format Markdown"><i class="fas fa-copy"></i> Copier Tout (Markdown)</button></div><div id="conversation-content"></div>`;
    const conversationContentContainer = document.getElementById('conversation-content');
    const globalActionsContainer = document.getElementById('global-actions');
    const copyAllButton = document.getElementById('copy-all-button');

    // Trouver la conversation
    const conversation = currentFolderData.conversations.find(c => c.id === conversationId);
    if (!conversation) { console.error(`DisplayConv: Conv ${conversationId} not found.`); return; }
    if (!conversationContentContainer || !globalActionsContainer || !copyAllButton) { console.error(`DisplayConv: Missing UI elements.`); return; }

    console.log(`--- Displaying Conversation ID: ${conversationId}, Title: ${conversation.title || '[Sans Titre]'} ---`);
    console.log("  Mapping structure to process:", conversation.mapping);

    // Titre et actions
    conversationView.querySelector('h2').textContent = conversation.title || '[Sans Titre]';
    globalActionsContainer.style.display = 'block';
    copyAllButton.onclick = null; copyAllButton.addEventListener('click', handleCopyAllMarkdown);

    // Extrait les messages
    const messages = getMessagesFromMapping(conversation.mapping);
    if (!messages || messages.length === 0) {
        console.warn(`displayConversation: No messages from getMessagesFromMapping for ${conversationId}.`);
        conversationContentContainer.innerHTML = '<p><i>Conversation vide ou contenu non chargé.</i></p>';
        if(globalActionsContainer) globalActionsContainer.style.display = 'none';
        return;
    }
    console.log(`  Will display ${messages.length} messages.`);

    // Boucle d'affichage des messages
    messages.forEach((msg, index) => {
        const messageElement = document.createElement('div'); messageElement.classList.add('message', msg.role);
        // Auteur + Bouton Copie
        const authorElement = document.createElement('div'); authorElement.classList.add('message-author'); authorElement.textContent = msg.role;
        const copyButton = document.createElement('button'); copyButton.className = 'copy-button'; copyButton.title = 'Copier message (Md)'; copyButton.innerHTML = '<i class="fas fa-clipboard"></i>';
        copyButton.addEventListener('click', (e) => handleCopySingleMessage(e.currentTarget, msg)); authorElement.appendChild(copyButton); messageElement.appendChild(authorElement);
        // Contenu
        const contentElement = document.createElement('div'); contentElement.classList.add('message-content');
        if (msg.parts?.length) {
            msg.parts.forEach(part => {
                if (typeof part === 'string') { const cleaned=cleanString(part); if (cleaned.trim()) contentElement.innerHTML += md.render(cleaned); }
                else if (part && typeof part === 'object') {
                    // --- SECTION ASSET CORRIGÉE ---
                    if (part.asset_pointer && currentFolderData.asset_mapping) {
                        const assetFilename = currentFolderData.asset_mapping[part.asset_pointer];
                        if (assetFilename) {
                            const assetUrl = `/export_files/${encodeURIComponent(folderSelector.value)}/${encodeURIComponent(assetFilename)}`;
                            const explicitMimeType = currentFolderData.file_types?.[assetFilename];
                            let isImage = false, isAudio = false; let fileTypeDesc = "Fichier";
                            console.log(`  [Asset Debug] File: ${assetFilename}, Explicit Type: ${explicitMimeType}`);

                            // Décider basé sur MIME explicite (logique assouplie)
                            if (explicitMimeType && typeof explicitMimeType === 'string') {
                                const lowerMime = explicitMimeType.toLowerCase();
                                fileTypeDesc = explicitMimeType;
                                // Vérification MIME assouplie
                                if (lowerMime.startsWith('image/') || ['png image data', 'jpeg image data', 'gif image data', 'webp image data', 'svg xml'].some(k => lowerMime.includes(k))) {
                                    isImage = true; console.log(`    -> Classified as IMAGE (MIME)`);
                                } else if (lowerMime.startsWith('audio/') || ['mpeg layer 3', 'wave audio', 'ogg data', 'flac audio', 'aac audio'].some(k => lowerMime.includes(k))) {
                                    isAudio = true; console.log(`    -> Classified as AUDIO (MIME)`);
                                } else if (lowerMime === 'application/octet-stream' || lowerMime === 'file not found') { console.log(`    -> MIME inconclusive (${explicitMimeType}). Will try ext.`); fileTypeDesc = (lowerMime === 'file not found')?"Fichier non trouvé":"Binaire"; }
                                else { console.log(`    -> MIME '${explicitMimeType}' not recognized.`); }
                            } else { console.log(`    -> No explicit MIME. Will use extension.`); }

                            // Fallback extension SI non classifié par MIME
                            if (!isImage && !isAudio) {
                                console.log(`    -> Applying extension fallback: ${assetFilename}`);
                                if (/\.(png|jpg|jpeg|gif|webp|svg|bmp)$/i.test(assetFilename)) { isImage = true; console.log(`    -> Classified as IMAGE (Ext)`); if (fileTypeDesc === "Fichier" || fileTypeDesc === "Binaire") fileTypeDesc = "Image (Ext)"; }
                                else if (/\.(wav|mp3|ogg|m4a|aac|flac)$/i.test(assetFilename)) { isAudio = true; console.log(`    -> Classified as AUDIO (Ext)`); if (fileTypeDesc === "Fichier" || fileTypeDesc === "Binaire") fileTypeDesc = "Audio (Ext)"; }
                                else { console.log(`    -> Ext fallback no match.`); }
                            }
                            // Afficher l'élément
                            if (isImage) { const img=document.createElement('img'); img.src=assetUrl; img.alt=`Image: ${assetFilename}`; img.style.cssText='max-width:100%;max-height:450px;display:block;margin:10px 0;'; img.onerror=() => img.alt=`Erreur chargement image: ${assetFilename}`; contentElement.appendChild(img); }
                            else if (isAudio) { const audC=document.createElement('div'); const aud=document.createElement('audio'); aud.controls=true; aud.src=assetUrl; aud.style.width='100%'; audC.appendChild(aud); const d=document.createElement('p'); d.innerHTML=`<i style='font-size:0.9em;color:#555'>Audio: ${assetFilename} (${fileTypeDesc})</i>`; d.style.margin="0 0 10px 0"; contentElement.appendChild(audC); contentElement.appendChild(d); }
                            else { const a=document.createElement('a'); a.href=assetUrl; a.target='_blank'; a.textContent=`[${cleanString(fileTypeDesc)}]: ${assetFilename}`; a.classList.add('data-link'); const p=document.createElement('p'); p.appendChild(a); contentElement.appendChild(p); }
                        } else { contentElement.innerHTML += `<p><i>[Fichier (${cleanString(part.asset_pointer)}) non mappé]</i></p>`; }
                    // --- FIN SECTION ASSET CORRIGÉE ---
                    } else if (part.content_type === 'code' && part.text) { const pre=document.createElement('pre'); const code=document.createElement('code'); if(part.language) code.className=`language-${part.language}`; code.textContent=cleanString(part.text||''); pre.appendChild(code); contentElement.appendChild(pre); }
                    else if (part.text && typeof part.text === 'string') { const cleaned=cleanString(part.text); if (cleaned.trim()) contentElement.innerHTML += md.render(cleaned); }
                    else { console.warn("Unhandled object part:", part); contentElement.innerHTML += `<p><i>[Contenu Objet Non Géré]</i></p>`; }
                } else if (part !== null && part !== undefined) { console.warn("Unexpected part type:", typeof part, part); }
            });
        } else if (msg.text && typeof msg.text === 'string') { const cleaned=cleanString(msg.text); if (cleaned.trim()) contentElement.innerHTML += md.render(cleaned); }
        else if (contentElement.innerHTML.trim() === '') { contentElement.innerHTML = '<i>[Message vide]</i>'; }
        messageElement.appendChild(contentElement);
        conversationContentContainer.appendChild(messageElement);
    }); // Fin boucle messages

    // Trigger KaTeX
    try { if (window.renderMathInElement) { renderMathInElement(conversationContentContainer, { delimiters: [{left:"$$",right:"$$",display:true},{left:"$",right:"$",display:false},{left:"\\[",right:"\\]",display:true},{left:"\\(",right:"\\)",display:false}], throwOnError: false }); } } catch (e) { console.error("KaTeX Error:", e); }
    if (mainContent) { mainContent.scrollTop = 0; } // Scroll top
}


/** Extrait les messages ordonnés du mapping (Version avec Logs). */
function getMessagesFromMapping(mapping) {
    console.log("--- getMessagesFromMapping ---");
    if (!mapping || typeof mapping !== 'object' || Object.keys(mapping).length === 0) { console.warn("  Mapping invalid/empty."); console.log("-----------------------------"); return []; }
    console.log(`  Input mapping has ${Object.keys(mapping).length} nodes.`);
    const nodes = {}; const rootIds = new Set();
    console.log("  1. Building nodes & finding roots...");
    for (const id in mapping) { const nodeData = mapping[id]; if (typeof nodeData !== 'object' || nodeData === null) continue; nodes[id] = { id: id, message: nodeData.message, parent: nodeData.parent, children: nodeData.children || [] }; if ((!nodeData.parent || nodeData.parent === 'client-created-root') && id !== 'client-created-root') { rootIds.add(id); } }
    console.log(`  Found ${rootIds.size} roots.`);
    for (const id in nodes) { if (Array.isArray(nodes[id].children)) nodes[id].children = nodes[id].children.filter(cid => nodes[cid]); else nodes[id].children = []; }
    const messages = []; const visited = new Set(); let traversalOrder = 0;
    console.log("  2. Starting DFS traversal...");
    function dfs(nodeId) {
        if (!nodeId || visited.has(nodeId) || !nodes[nodeId]) return; visited.add(nodeId); traversalOrder++; const node = nodes[nodeId];
        const msg = node.message;
        if (msg && msg.content && (msg.content.parts || typeof msg.content.text === 'string')) {
            const role = msg.author?.role; const isUserSys = msg.metadata?.is_user_system_message === true;
            if (role === 'user' || role === 'assistant' || role === 'tool' || (role === 'system' && isUserSys)) {
                 let parts = msg.content.parts; if ((!Array.isArray(parts) || parts.length === 0) && typeof msg.content.text === 'string') parts = [msg.content.text];
                 if (Array.isArray(parts) && parts.length > 0) { messages.push({ role: role, parts: parts }); /* console.log(`      -> ADDED MESSAGE node ${nodeId}`); */ }
            }
        }
        if (Array.isArray(node.children)) { node.children.sort().forEach(childId => dfs(childId)); }
    }
    const sortedRootIds = Array.from(rootIds).sort();
    if (sortedRootIds.length > 0) { console.log(`  Starting from roots: ${sortedRootIds.join(', ')}`); sortedRootIds.forEach(dfs); }
    else { console.warn("  No explicit roots! Fallback."); const allIds = Object.keys(nodes).sort(); allIds.forEach(id => { if (id !== 'client-created-root' && !visited.has(id)) dfs(id); }); }
    console.log(`  DFS complete. Extracted ${messages.length} messages.`);
    if (messages.length === 0 && Object.keys(nodes).length > 0) console.warn("  WARNING: No messages extracted!");
    console.log("-----------------------------");
    return messages;
}

/** Génère Markdown pour une part de message (inchangé). */
function getMarkdownForMessagePart(part) {
    if (typeof part === 'string') { return cleanString(part).trim(); }
    else if (part && typeof part === 'object') {
        if (part.asset_pointer && currentFolderData.asset_mapping) { const fn = currentFolderData.asset_mapping[part.asset_pointer]; if (fn) { const safeFn = fn.replace(/[<>:"/\\|?*]/g, '_'); const type = currentFolderData.file_types?.[fn]; let i=0, a=0; if(type){const lt=type.toLowerCase();if(lt.startsWith('image/')||['png image data','jpeg image data'].some(k=>lt.includes(k)))i=1;else if(lt.startsWith('audio/')||['mpeg layer 3','wave audio'].some(k=>lt.includes(k)))a=1;} if(!i&&!a&&/\.(png|jpe?g|gif|webp|svg)$/i.test(fn))i=1;else if(!i&&!a&&/\.(wav|mp3|ogg|m4a|aac|flac)$/i.test(fn))a=1; if(i) return `![Image: ${fn}](${safeFn})`; if(a) return `[Audio: ${fn}](${safeFn})`; return `[Fichier: ${fn}](${safeFn})`; } else return `*[Mappage Manquant: ${part.asset_pointer}]*`; }
        else if (part.content_type === 'code' && part.text) { const lang=part.language||''; return `\`\`\`${lang}\n${cleanString(part.text||'')}\n\`\`\``; }
        else if (part.text && typeof part.text === 'string') { return cleanString(part.text).trim(); }
        else return `*[Contenu Objet Non Géré]*`;
    } return '';
}

/** Copie message unique (inchangé). */
function handleCopySingleMessage(buttonElement, messageData) {
    let md=''; if (messageData.parts?.length) md = messageData.parts.map(getMarkdownForMessagePart).filter(m=>m).join('\n\n'); else if(messageData.text) md = getMarkdownForMessagePart(messageData.text);
    if(md) copyTextToClipboard(md.trim(), buttonElement); else { /* feedback vide */ }
}

/** Copie toute la conversation (inchangé). */
function handleCopyAllMarkdown(event) {
    const li = conversationList.querySelector('li.selected'); if(!li?.dataset?.conversationId) return; const convId = li.dataset.conversationId; const conv = currentFolderData.conversations.find(c=>c.id===convId); if(!conv) return;
    let fullMd = `# ${conv.title||'Conversation'}\n\n`; const msgs = getMessagesFromMapping(conv.mapping);
    if(msgs?.length) msgs.forEach(msg => { fullMd += `**${msg.role.toUpperCase()}**:\n\n`; let msgMd=''; if(msg.parts?.length) msgMd=msg.parts.map(getMarkdownForMessagePart).filter(m=>m).join('\n\n'); else if(msg.text) msgMd=getMarkdownForMessagePart(msg.text); fullMd += msgMd.trim() + '\n\n---\n\n'; });
    else fullMd += "*[Vide]*"; copyTextToClipboard(fullMd.trim(), event.currentTarget);
}

/** Navigation clavier (inchangé). */
function handleKeyboardNavigation(event) {
    const activeEl = document.activeElement; const inputFocus = activeEl && (['input','textarea','select'].includes(activeEl.tagName.toLowerCase())); if (inputFocus || !mainContent) return;
    const scrollAmt = mainContent.clientHeight*0.85; switch(event.key){ case 'PageDown': event.preventDefault();mainContent.scrollBy({top:scrollAmt,behavior:'smooth'}); break; case 'PageUp': event.preventDefault();mainContent.scrollBy({top:-scrollAmt,behavior:'smooth'}); break; case 'End': if(event.ctrlKey||event.metaKey){event.preventDefault();mainContent.scrollTo({top:mainContent.scrollHeight,behavior:'smooth'});} break; case 'Home': if(event.ctrlKey||event.metaKey){event.preventDefault();mainContent.scrollTo({top:0,behavior:'smooth'});} break; }
}
