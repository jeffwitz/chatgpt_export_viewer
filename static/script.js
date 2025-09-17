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
const filterAssetsCheckbox = document.getElementById('filter-assets-checkbox');
const filterAudioCheckbox = document.getElementById('filter-audio-checkbox');
const filterImagesCheckbox = document.getElementById('filter-images-checkbox');
const searchStatus = document.getElementById('search-status'); // Pour afficher statut/résultats recherche

const AUDIO_MIME_KEYWORDS = ['mpeg layer 3', 'wave audio', 'ogg data', 'flac audio', 'aac audio'];
const IMAGE_MIME_KEYWORDS = ['png image data', 'jpeg image data', 'gif image data', 'webp image data', 'svg xml', 'bitmap'];
const AUDIO_EXTENSION_REGEX = /\.(wav|mp3|ogg|m4a|aac|flac)$/i;
const IMAGE_EXTENSION_REGEX = /\.(png|jpe?g|gif|bmp|webp|svg|avif|heic|heif)$/i;

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
    if (filterImagesCheckbox) { filterImagesCheckbox.addEventListener('change', updateDisplayedConversationList); }
    else { console.error("Image filter checkbox not found."); }
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
    if (searchBox) searchBox.value = '';
    if (filterAssetsCheckbox) filterAssetsCheckbox.checked = false;
    if (filterAudioCheckbox) filterAudioCheckbox.checked = false;
    if (filterImagesCheckbox) filterImagesCheckbox.checked = false;
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
        conv.has_asset = conversationHasAsset(conv);
        conv.has_audio = conversationHasAudio(conv);
        conv.has_image = conversationHasImage(conv);
        let id = conv.conversation_id || conv.id;
        if (!id || typeof id !== 'string' || id.startsWith('invalid_')) { id = `genid_${index}`; }
        conv.id = id;
        if (!conv.id) { console.error(`preprocess: FATAL ID fail @ ${index}`); conv.id = `errid_${index}`; }
    });
    console.log("preprocess: Complete.");
}

/** Vérifie si une conversation contient une référence à un asset. */
function collectAssetPartsFromNode(node) {
    const parts = [];
    if (node?.message?.content?.parts && Array.isArray(node.message.content.parts)) {
        parts.push(...node.message.content.parts);
    }
    if (node?.message?.author?.role === 'tool') {
        const toolParts = node.message?.metadata?.aggregate_result?.message?.content?.parts;
        if (Array.isArray(toolParts)) {
            parts.push(...toolParts);
        }
    }
    return parts;
}

function conversationHasAsset(conversation) {
    if (!conversation?.mapping || typeof conversation.mapping !== 'object') return false;
    for (const nodeId in conversation.mapping) {
        const node = conversation.mapping[nodeId];
        if (!node) continue;
        const parts = collectAssetPartsFromNode(node);
        if (parts.some(part => part?.asset_pointer)) return true;
    }
    return false;
}

/** Vérifie spécifiquement les assets audio. */
function conversationHasAudio(conversation) {
    if (!conversation?.mapping || typeof conversation.mapping !== 'object') return false;
    const am = currentFolderData.asset_mapping || {};
    const tm = currentFolderData.file_types || {};
    for (const id in conversation.mapping) {
        const node = conversation.mapping[id];
        if (!node) continue;
        const parts = collectAssetPartsFromNode(node);
        for (const part of parts) {
            if (!part?.asset_pointer || !am[part.asset_pointer]) continue;
            const filename = am[part.asset_pointer];
            const explicitType = tm[filename];
            if (typeof explicitType === 'string') {
                const lower = explicitType.toLowerCase();
                if (lower.startsWith('audio/') || AUDIO_MIME_KEYWORDS.some(keyword => lower.includes(keyword))) return true;
            }
            if (AUDIO_EXTENSION_REGEX.test(filename)) return true;
        }
    }
    return false;
}

function conversationHasImage(conversation) {
    if (!conversation?.mapping || typeof conversation.mapping !== 'object') return false;
    const am = currentFolderData.asset_mapping || {};
    const tm = currentFolderData.file_types || {};
    for (const id in conversation.mapping) {
        const node = conversation.mapping[id];
        if (!node) continue;
        const parts = collectAssetPartsFromNode(node);
        for (const part of parts) {
            if (!part?.asset_pointer || !am[part.asset_pointer]) continue;
            const filename = am[part.asset_pointer];
            const explicitType = tm[filename];
            if (typeof explicitType === 'string') {
                const lower = explicitType.toLowerCase();
                if (lower.startsWith('image/') || IMAGE_MIME_KEYWORDS.some(keyword => lower.includes(keyword))) return true;
            }
            if (IMAGE_EXTENSION_REGEX.test(filename)) return true;
        }
    }
    return false;
}

function appendConversationIcons(listItem, conversation) {
    if (!listItem || !conversation) return;
    const icons = [];
    if (conversation.has_image) {
        icons.push({ className: 'fas fa-image', title: 'Image' });
    }
    if (conversation.has_audio) {
        icons.push({ className: 'fas fa-volume-up', title: 'Audio' });
    }
    if (conversation.has_asset && !conversation.has_image && !conversation.has_audio) {
        icons.push({ className: 'fas fa-photo-video', title: 'Média/Fichier' });
    }
    icons.forEach(iconCfg => {
        listItem.appendChild(document.createTextNode(' '));
        const iconEl = document.createElement('i');
        iconEl.className = iconCfg.className;
        iconEl.style.opacity = '0.6';
        iconEl.style.fontSize = '0.8em';
        iconEl.title = iconCfg.title;
        listItem.appendChild(iconEl);
    });
}

/** Met à jour la liste affichée basée sur FILTRE TITRE et CHECKBOXES. */
function updateDisplayedConversationList() {
    console.log("updateDisplayedConversationList: Based on title search and filters.");
    const searchTerm = searchBox.value.toLowerCase().trim(); // Recherche TITRE
    const filterAssets = !!(filterAssetsCheckbox && filterAssetsCheckbox.checked);
    const filterAudio = !!(filterAudioCheckbox && filterAudioCheckbox.checked);
    const filterImages = !!(filterImagesCheckbox && filterImagesCheckbox.checked);
    conversationList.innerHTML = '';
    if (!searchTerm) setSearchStatus('');

    if (!currentFolderData.conversations?.length) { conversationList.innerHTML = '<li class="empty-list">Aucune conversation.</li>'; return; }

    const filtered = currentFolderData.conversations.filter(c => {
        if (typeof c !== 'object' || !c?.id) return false;
        const titleMatch = !searchTerm || (c.title && typeof c.title === 'string' && c.title.toLowerCase().includes(searchTerm));
        const assetMatch = !filterAssets || c.has_asset;
        const audioMatch = !filterAudio || c.has_audio;
        const imageMatch = !filterImages || c.has_image;
        return titleMatch && assetMatch && audioMatch && imageMatch;
    });

    if (filtered.length > 0) {
        filtered.forEach(c => {
            const listItem = document.createElement('li');
            const titleText = c.title || '[Sans Titre]';
            if (c.id) listItem.dataset.conversationId = c.id;
            else { listItem.style.opacity = "0.5"; listItem.title = "ID invalide"; }
            listItem.textContent = '';
            const titleSpan = document.createElement('span');
            titleSpan.textContent = titleText;
            listItem.appendChild(titleSpan);
            appendConversationIcons(listItem, c);
            conversationList.appendChild(listItem);
        });
        if (searchTerm || filterAssets || filterAudio || filterImages) setSearchStatus(`${filtered.length} résultat(s) pour filtres/titre.`);
    } else {
        if (searchTerm) conversationList.innerHTML = '<li class="empty-list">Aucun titre ne correspond.</li>';
        else if (filterAssets || filterAudio || filterImages) conversationList.innerHTML = '<li class="empty-list">Aucun résultat avec ces filtres.</li>';
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
        const titleText = conv.title || '[Sans Titre]';
        listItem.textContent = '';
        const titleSpan = document.createElement('span');
        titleSpan.textContent = titleText;
        listItem.appendChild(titleSpan);
        listItem.dataset.conversationId = conv.id;
        const originalConv = currentFolderData.conversations.find(c => c.id === conv.id);
        if (originalConv) appendConversationIcons(listItem, originalConv);
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
                    } else if (part.content_type === 'code' && part.text) {
                        const pre = document.createElement('pre');
                        pre.classList.add('code-block');
                        const code = document.createElement('code');
                        const rawLanguage = (part.language || '').toLowerCase();
                        if (rawLanguage) { code.classList.add(`language-${rawLanguage}`); }
                        const sanitizedText = cleanString(part.text || '');
                        code.innerHTML = basicHighlightToHtml(sanitizedText, rawLanguage);
                        code.dataset.basicHighlighted = 'true';
                        pre.appendChild(code);
                        contentElement.appendChild(pre);
                    }
                    else if (part.text && typeof part.text === 'string') { const cleaned=cleanString(part.text); if (cleaned.trim()) contentElement.innerHTML += md.render(cleaned); }
                    else { console.warn("Unhandled object part:", part); contentElement.innerHTML += `<p><i>[Contenu Objet Non Géré]</i></p>`; }
                } else if (part !== null && part !== undefined) { console.warn("Unexpected part type:", typeof part, part); }
            });
        } else if (msg.text && typeof msg.text === 'string') { const cleaned=cleanString(msg.text); if (cleaned.trim()) contentElement.innerHTML += md.render(cleaned); }
        else if (contentElement.innerHTML.trim() === '') { contentElement.innerHTML = '<i>[Message vide]</i>'; }
        enhanceCodeBlocks(contentElement);
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

const CODE_LANGUAGE_ALIASES = {
    py: 'python',
    py3: 'python',
    python: 'python',
    js: 'javascript',
    jsx: 'javascript',
    javascript: 'javascript',
    json: 'javascript',
    ts: 'javascript',
    typescript: 'javascript',
    c: 'c',
    h: 'c',
    cpp: 'c',
    'c++': 'c',
    html: 'html',
    xml: 'html',
    css: 'css'
};

const CODE_KEYWORDS = {
    python: ['def','class','return','if','elif','else','for','while','try','except','finally','raise','import','from','as','with','lambda','yield','True','False','None','pass','break','continue','global','nonlocal','assert','async','await'],
    javascript: ['function','return','if','else','for','while','do','switch','case','break','continue','const','let','var','class','extends','import','from','export','default','new','this','super','try','catch','finally','throw','async','await','null','undefined','true','false'],
    c: ['int','float','double','char','void','long','short','unsigned','signed','return','if','else','for','while','do','switch','case','break','continue','struct','typedef','enum','sizeof','static','const','volatile','extern','NULL'],
    css: ['@media','@import','@font-face','@keyframes','from','to','var'],
    html: ['html','head','body','title','meta','link','script','style','div','span','section','article','nav','header','footer','main','aside','ul','ol','li','table','thead','tbody','tr','td','th','form','input','button','label','textarea','canvas','svg','img','a'],
    default: ['return','if','else','for','while','class','function','def','true','false','null','None','True','False']
};

function escapeHtmlForCode(value) {
    return value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escapeRegex(value) {
    return value.replace(/[.*+?^${}()|\[\]\\]/g, '\\$&');
}

function normalizeLanguageAlias(language) {
    if (!language) return 'plain';
    const key = language.toLowerCase();
    return CODE_LANGUAGE_ALIASES[key] || key;
}

function getHighlightPatterns(language) {
    const lang = normalizeLanguageAlias(language);
    const patterns = [
        { regex: /"(?:\\.|[^"\\])*"/g, type: 'string', priority: 40 },
        { regex: /'(?:\\.|[^'\\])*'/g, type: 'string', priority: 40 },
        { regex: /`(?:\\.|[^`\\])*`/g, type: 'string', priority: 40 },
        { regex: /\b0x[0-9a-fA-F]+\b/g, type: 'number', priority: 25 },
        { regex: /\b\d+(?:\.\d+)?\b/g, type: 'number', priority: 25 }
    ];

    if (lang === 'python') {
        patterns.push({ regex: /(?<!["'])#.*$/gm, type: 'comment', priority: 50 });
        patterns.push({ regex: /("""|''')[\s\S]*?\1/g, type: 'string', priority: 45 });
    } else if (lang === 'javascript' || lang === 'c' || lang === 'css') {
        patterns.push({ regex: /\/\/.*$/gm, type: 'comment', priority: 50 });
        patterns.push({ regex: /\/\*[\s\S]*?\*\//g, type: 'comment', priority: 50 });
    } else if (lang === 'html') {
        patterns.push({ regex: /<!--[\s\S]*?-->/g, type: 'comment', priority: 50 });
    }

    if (lang === 'c') {
        patterns.push({ regex: /#[a-zA-Z_]\w*/g, type: 'keyword', priority: 32 });
    }

    if (lang === 'css') {
        patterns.push({ regex: /@[a-zA-Z-]+/g, type: 'keyword', priority: 32 });
        patterns.push({ regex: /(?:--)?[a-zA-Z][a-zA-Z0-9-]*(?=\s*:)/g, type: 'property', priority: 28 });
    }

    if (lang === 'html') {
        patterns.push({ regex: /<\/?[a-zA-Z][a-zA-Z0-9:-]*/g, type: 'tag', priority: 45 });
        patterns.push({ regex: /\b[a-zA-Z-:]+(?=\s*=)/g, type: 'attr', priority: 30 });
        patterns.push({ regex: /&[a-zA-Z0-9#]+;/g, type: 'entity', priority: 20 });
    }

    const keywordList = CODE_KEYWORDS[lang] || CODE_KEYWORDS.default;
    if (keywordList && keywordList.length) {
        const escapedList = keywordList.map(escapeRegex).join('|');
        if (escapedList) {
            patterns.push({ regex: new RegExp(`\\b(?:${escapedList})\\b`, 'g'), type: 'keyword', priority: 35 });
        }
    }

    return patterns;
}

function basicHighlightToHtml(codeText, language) {
    const source = typeof codeText === 'string' ? codeText : String(codeText ?? '');
    if (!source) { return ''; }
    const patterns = getHighlightPatterns(language);
    const tokens = [];

    patterns.forEach((pattern, idx) => {
        const regex = pattern.regex;
        regex.lastIndex = 0;
        let match;
        while ((match = regex.exec(source)) !== null) {
            const text = match[0];
            tokens.push({
                start: match.index,
                end: match.index + text.length,
                type: pattern.type,
                priority: pattern.priority ?? (patterns.length - idx),
                text
            });
            if (match.index === regex.lastIndex) { regex.lastIndex += 1; }
        }
    });

    tokens.sort((a, b) => {
        if (a.start !== b.start) return a.start - b.start;
        if (a.priority !== b.priority) return b.priority - a.priority;
        const lenDiff = (b.end - b.start) - (a.end - a.start);
        if (lenDiff !== 0) return lenDiff;
        return 0;
    });

    const merged = [];
    let currentEnd = -1;
    tokens.forEach(token => {
        if (token.start >= currentEnd) {
            merged.push(token);
            currentEnd = token.end;
        }
    });

    let cursor = 0;
    let html = '';
    merged.forEach(token => {
        if (cursor < token.start) {
            html += escapeHtmlForCode(source.slice(cursor, token.start));
        }
        html += `<span class="code-${token.type}">${escapeHtmlForCode(token.text)}</span>`;
        cursor = token.end;
    });
    if (cursor < source.length) {
        html += escapeHtmlForCode(source.slice(cursor));
    }
    return html;
}

function enhanceCodeBlocks(container) {
    if (!container) return;
    container.querySelectorAll('pre').forEach(pre => {
        pre.classList.add('code-block');
    });
    container.querySelectorAll('pre code').forEach(codeEl => {
        if (!codeEl || codeEl.dataset.basicHighlighted === 'true') return;
        const langClass = Array.from(codeEl.classList || []).find(cls => cls.startsWith('language-'));
        const lang = langClass ? langClass.replace('language-', '') : '';
        const original = codeEl.textContent || '';
        codeEl.innerHTML = basicHighlightToHtml(original, lang);
        codeEl.dataset.basicHighlighted = 'true';
    });
    container.querySelectorAll(':not(pre) > code').forEach(inlineCode => {
        inlineCode.classList.add('inline-code');
    });
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
