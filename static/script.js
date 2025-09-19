// static/script.js (Complete version with relaxed MIME detection adjustments)

// --- Global Variables ---
let currentFolderData = {
    conversations: [],
    asset_mapping: {},
    file_types: {}
};
let md; // Markdown-it instance
const badCharsRegex = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F\uE000-\uF8FF]/gu; // Strip control and private Unicode ranges

// --- DOM Elements ---
const folderSelector = document.getElementById('folder-selector');
const conversationList = document.getElementById('conversation-list');
const conversationView = document.getElementById('conversation-view');
const mainContent = document.getElementById('main-content');
const loadingIndicator = document.getElementById('loading-indicator');
const searchBox = document.getElementById('search-box');
const filterAudioCheckbox = document.getElementById('filter-audio-checkbox');
const filterImagesCheckbox = document.getElementById('filter-images-checkbox');
const filterToolsCheckbox = document.getElementById('filter-tools-checkbox');
const searchStatus = document.getElementById('search-status'); // Displays search status/results
const searchStartInput = document.getElementById('search-start');
const searchEndInput = document.getElementById('search-end');
const searchRangePanel = document.getElementById('search-range-panel');
const toggleDateFiltersButton = document.getElementById('toggle-date-filters');
const uploadExportForm = document.getElementById('upload-export-form');
const uploadExportStatus = document.getElementById('upload-export-status');
const uploadExportButton = document.getElementById('upload-export-button');
const uploadExportFileInput = document.getElementById('export-zip-input');
const uploadExportFolderInput = document.getElementById('export-folder-name');
const uploadExportDestinationInput = document.getElementById('export-destination');
const uploadExportPanel = document.getElementById('upload-export-panel');
const toggleUploadFormButton = document.getElementById('toggle-upload-form');

const AUDIO_MIME_KEYWORDS = ['mpeg layer 3', 'wave audio', 'ogg data', 'flac audio', 'aac audio'];
const IMAGE_MIME_KEYWORDS = ['png image data', 'jpeg image data', 'gif image data', 'webp image data', 'svg xml', 'bitmap'];
const AUDIO_EXTENSION_REGEX = /\.(wav|mp3|ogg|m4a|aac|flac)$/i;
const IMAGE_EXTENSION_REGEX = /\.(png|jpe?g|gif|bmp|webp|svg|avif|heic|heif)$/i;

// --- Global debounce timer for full-text search ---
let searchDebounceTimeout = null;
const DEBOUNCE_DELAY = 400; // Delay (ms) before triggering the remote search after input

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
    if (searchBox) { searchBox.addEventListener('input', handleSearchInput); } // Debounced search input
    else { console.error("Search box element not found."); }
    // Filters trigger the list refresh directly
    if (filterAudioCheckbox) { filterAudioCheckbox.addEventListener('change', updateMediaFilters); }
    else { console.error("Audio filter checkbox not found."); }
    if (filterImagesCheckbox) { filterImagesCheckbox.addEventListener('change', updateMediaFilters); }
    else { console.error("Image filter checkbox not found."); }
    if (filterToolsCheckbox) { filterToolsCheckbox.addEventListener('change', handleToolFilterChange); }
    else { console.error("Tool filter checkbox not found."); }
    document.addEventListener('keydown', handleKeyboardNavigation);
    if (uploadExportForm) { uploadExportForm.addEventListener('submit', handleUploadExportSubmit); }
    if (uploadExportFileInput && uploadExportFolderInput) {
        uploadExportFileInput.addEventListener('change', populateFolderNameSuggestion);
    }
    if (toggleUploadFormButton) { toggleUploadFormButton.addEventListener('click', toggleUploadFormVisibility); }
    if (toggleDateFiltersButton && searchRangePanel) {
        toggleDateFiltersButton.addEventListener('click', toggleDateRangeVisibility);
        const isExpanded = !searchRangePanel.classList.contains('d-none');
        toggleDateFiltersButton.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
        toggleDateFiltersButton.textContent = isExpanded ? 'Hide date range' : 'Date range';
    }
    // The "Copy all" listener is attached dynamically in displayConversation
    if (searchStartInput) { searchStartInput.addEventListener('change', handleSearchRangeChange); }
    if (searchEndInput) { searchEndInput.addEventListener('change', handleSearchRangeChange); }

    // Initial Load Logic
    if (folderSelector && folderSelector.options.length > 1) {
        folderSelector.selectedIndex = 1; // Select the first real folder option
        console.log(`Initial load: Selecting first folder '${folderSelector.value}'`);
        folderSelector.dispatchEvent(new Event('change')); // Trigger initial load
    } else { console.log("Initial load: No folders found or only default option."); }
});

// --- Utility Functions ---

/** Remove unwanted control characters from a string. */
function cleanString(inputText) {
    if (typeof inputText !== 'string') return inputText;
    return inputText.replace(badCharsRegex, '');
}

function formatTimestampSeconds(timestampSeconds) {
    if (typeof timestampSeconds !== 'number' || !Number.isFinite(timestampSeconds)) return null;
    const date = new Date(timestampSeconds * 1000);
    if (Number.isNaN(date.getTime())) return null;
    return date.toLocaleString();
}

function normaliseDateInputValue(value) {
    if (!value || typeof value !== 'string') return '';
    return value.trim();
}

/** Copy text to the clipboard and give visual feedback on a button. */
async function copyTextToClipboard(text, buttonElement) {
    // Fallback when navigator.clipboard is unavailable
    const doFeedback = () => {
        if (buttonElement) {
            const originalHtml = buttonElement.innerHTML;
            const originalTitle = buttonElement.title;
            buttonElement.innerHTML = '<i class="fas fa-check"></i> Copied!';
            buttonElement.classList.add('copied');
            buttonElement.disabled = true;
            buttonElement.title = 'Copied!';
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
            alert('Copy failed.');
            if (buttonElement) buttonElement.disabled = false;
        }
    } else {
        // Legacy fallback for insecure contexts or older browsers
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
                alert('Copy not supported.');
            }
        } catch (err) {
            alert('Copy not supported.');
        }
    }
}


// --- Core Application Logic ---

/** Load conversations, asset mapping, and file types for the selected folder. */
async function loadConversationsForFolder() {
    const selectedFolder = folderSelector.value;
    console.log(`Folder selected: ${selectedFolder}`);
    resetUI(); // Reset the UI before loading
    if (!selectedFolder) { setLoading(false); return; }
    setLoading(true);
    try {
        // API call returns data and triggers server-side ingestion when needed
        const response = await fetch(`/conversations?folder_name=${encodeURIComponent(selectedFolder)}`);
        if (!response.ok) { const errData = await response.json().catch(()=>({})); throw new Error(errData.error || `HTTP ${response.status}`); }
        const data = await response.json();
        console.log("Base data received:", data);
        currentFolderData = data; // Cache the snapshot locally
        preprocessConversationData(); // Augment conversations with computed flags
        updateDisplayedConversationList(); // Render the list
    } catch (error) {
        console.error('Error loading folder data:', error);
        conversationView.innerHTML = `<p style="color:red;padding:20px;">Load error: ${error.message}</p>`;
        conversationList.innerHTML = '<li class="empty-list">Failed to load conversations.</li>';
        setSearchStatus('');
    } finally {
        setLoading(false);
    }
}

/** Reset the user interface to its default state. */
function resetUI() {
    conversationList.innerHTML = '';
    conversationView.innerHTML = '<h2>Select a conversation</h2><p>Click a title.</p><div id="conversation-content"></div>';
    if (searchBox) searchBox.value = '';
    if (searchStartInput) searchStartInput.value = '';
    if (searchEndInput) searchEndInput.value = '';
    if (filterAudioCheckbox) filterAudioCheckbox.checked = false;
    if (filterImagesCheckbox) filterImagesCheckbox.checked = false;
    if (filterToolsCheckbox) filterToolsCheckbox.checked = true;
    currentFolderData = { conversations: [], asset_mapping: {}, file_types: {} };
    document.querySelectorAll('#conversation-list li.selected').forEach(i => i.classList.remove('selected'));
    setSearchStatus('');
    clearTimeout(searchDebounceTimeout);
    setLoading(false);
}

function handleToolFilterChange() {
    const selected = conversationList?.querySelector('li.selected');
    if (selected?.dataset?.conversationId) {
        displayConversation(selected.dataset.conversationId);
    }
}

/** Show or hide the global loading indicator. */
function setLoading(isLoading) {
    loadingIndicator.style.display = isLoading ? 'block' : 'none';
}

/** Update the status message displayed under the search box. */
function setSearchStatus(message) {
    if (!searchStatus) return;
    searchStatus.textContent = message || '';
    searchStatus.style.display = message ? 'block' : 'none';
}

function setUploadStatus(message) {
    if (!uploadExportStatus) return;
    uploadExportStatus.textContent = message || '';
    uploadExportStatus.style.color = message && message.toLowerCase().startsWith('error') ? '#c92a2a' : '#6c757d';
}

function toggleUploadFormVisibility() {
    if (!uploadExportPanel || !toggleUploadFormButton) return;
    const hidden = uploadExportPanel.classList.contains('d-none');
    if (hidden) {
        uploadExportPanel.classList.remove('d-none');
        toggleUploadFormButton.textContent = 'Close import form';
        toggleUploadFormButton.classList.remove('btn-outline-secondary');
        toggleUploadFormButton.classList.add('btn-secondary');
        if (uploadExportFileInput) {
            uploadExportFileInput.focus({ preventScroll: true });
        }
    } else {
        uploadExportPanel.classList.add('d-none');
        toggleUploadFormButton.textContent = 'Import a ZIP export';
        toggleUploadFormButton.classList.add('btn-outline-secondary');
        toggleUploadFormButton.classList.remove('btn-secondary');
        if (uploadExportForm) uploadExportForm.reset();
        setUploadStatus('');
    }
}

function toggleDateRangeVisibility() {
    if (!searchRangePanel || !toggleDateFiltersButton) return;
    const hidden = searchRangePanel.classList.contains('d-none');
    if (hidden) {
        searchRangePanel.classList.remove('d-none');
        toggleDateFiltersButton.textContent = 'Hide date range';
        toggleDateFiltersButton.setAttribute('aria-expanded', 'true');
        if (searchStartInput && typeof searchStartInput.focus === 'function') {
            try {
                searchStartInput.focus({ preventScroll: true });
            } catch (err) {
                searchStartInput.focus();
            }
        }
    } else {
        if (searchStartInput) searchStartInput.value = '';
        if (searchEndInput) searchEndInput.value = '';
        clearTimeout(searchDebounceTimeout);
        const queryPresent = !!(searchBox && searchBox.value.trim());
        if (queryPresent) {
            scheduleSearch();
        } else {
            updateDisplayedConversationList();
            setSearchStatus('');
        }
        searchRangePanel.classList.add('d-none');
        toggleDateFiltersButton.textContent = 'Date range';
        toggleDateFiltersButton.setAttribute('aria-expanded', 'false');
    }
}

/** Enrich conversations with computed flags (has_asset, has_audio, has_image, id). */
function preprocessConversationData() {
    if (!currentFolderData.conversations?.length) { console.warn("preprocess: No convos."); currentFolderData.conversations = []; return; }
    currentFolderData.conversations.forEach((conv, index) => {
        if (typeof conv !== 'object' || conv === null) { console.warn(`preprocess: Invalid item @ ${index}.`); conv = { id: `invalid_${index}`, title: '[Invalid]', mapping: {} }; currentFolderData.conversations[index] = conv; return; }
        conv.has_asset = conversationHasAsset(conv);
        conv.has_audio = conversationHasAudio(conv);
        conv.has_image = conversationHasImage(conv);
        conv.has_tool = conversationHasTool(conv);
        let id = conv.conversation_id || conv.id;
        if (!id || typeof id !== 'string' || id.startsWith('invalid_')) { id = `genid_${index}`; }
        conv.id = id;
        if (!conv.id) { console.error(`preprocess: FATAL ID fail @ ${index}`); conv.id = `errid_${index}`; }
    });
    console.log("preprocess: Complete.");
}

function conversationHasTool(conversation) {
    if (!conversation?.mapping || typeof conversation.mapping !== 'object') return false;
    for (const nodeId in conversation.mapping) {
        const node = conversation.mapping[nodeId];
        const role = node?.message?.author?.role;
        if (role === 'tool') {
            return true;
        }
    }
    return false;
}

/** Gather all parts that may reference assets for a mapping node. */
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

/** Detect whether a conversation references audio assets. */
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
        icons.push({ className: 'fas fa-photo-video', title: 'Media/File' });
    }
    if (conversation.has_tool) {
        icons.push({ className: 'fas fa-robot', title: 'Tool messages present' });
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

/** Refresh the displayed list based on title search and filter checkboxes. */
function getMediaFilterState() {
    const wantsAudio = !!(filterAudioCheckbox && filterAudioCheckbox.checked);
    const wantsImages = !!(filterImagesCheckbox && filterImagesCheckbox.checked);
    return { wantsAudio, wantsImages, hasFilter: wantsAudio || wantsImages };
}

function updateMediaFilters() {
    updateDisplayedConversationList();
    const selected = conversationList?.querySelector('li.selected');
    if (selected?.dataset?.conversationId) {
        displayConversation(selected.dataset.conversationId);
    }
}

function updateDisplayedConversationList() {
    console.log("updateDisplayedConversationList: Based on title search and filters.");
    const searchTerm = searchBox.value.toLowerCase().trim(); // Title filter
    const mediaFilters = getMediaFilterState();
    conversationList.innerHTML = '';
    if (!searchTerm) setSearchStatus('');

    if (!currentFolderData.conversations?.length) { conversationList.innerHTML = '<li class="empty-list">No conversations.</li>'; return; }

    const filtered = currentFolderData.conversations.filter(c => {
        if (typeof c !== 'object' || !c?.id) return false;
        const titleMatch = !searchTerm || (c.title && typeof c.title === 'string' && c.title.toLowerCase().includes(searchTerm));
        const mediaMatch = !mediaFilters.hasFilter || (
            (mediaFilters.wantsAudio && c.has_audio) ||
            (mediaFilters.wantsImages && c.has_image)
        );
        return titleMatch && mediaMatch;
    });

    if (filtered.length > 0) {
        filtered.forEach(c => {
            const listItem = document.createElement('li');
            const titleText = c.title || '[Untitled]';
            if (c.id) listItem.dataset.conversationId = c.id;
            else { listItem.style.opacity = "0.5"; listItem.title = "Invalid ID"; }
            listItem.textContent = '';
            const titleSpan = document.createElement('span');
            titleSpan.textContent = titleText;
            listItem.appendChild(titleSpan);
            appendConversationIcons(listItem, c);
            conversationList.appendChild(listItem);
        });
        if (searchTerm || mediaFilters.hasFilter) setSearchStatus(`${filtered.length} result(s) with current filters.`);
    } else {
        if (searchTerm) conversationList.innerHTML = '<li class="empty-list">No title matches.</li>';
        else if (mediaFilters.hasFilter) conversationList.innerHTML = '<li class="empty-list">No conversation matches these filters.</li>';
        else conversationList.innerHTML = '<li class="empty-list">No valid conversations.</li>';
    }
}


/** Handle typing in the search box: debounce remote search or revert to the local list. */
function scheduleSearch() {
    clearTimeout(searchDebounceTimeout);
    const query = searchBox.value.trim();
    const folderName = folderSelector.value;
    if (!folderName) return;

    const startValue = normaliseDateInputValue(searchStartInput?.value);
    const endValue = normaliseDateInputValue(searchEndInput?.value);
    if (startValue && endValue) {
        const startDate = new Date(startValue);
        const endDate = new Date(endValue);
        if (startDate > endDate) {
            setSearchStatus('Invalid date range: start must be before end.');
            return;
        }
    }

    if (!query) {
        console.log("Search cleared, running updateDisplayedConversationList.");
        updateDisplayedConversationList();
        return;
    }

    setSearchStatus('Searching...');
    searchDebounceTimeout = setTimeout(() => {
        performSearch(folderName, query);
    }, DEBOUNCE_DELAY);
}

function handleSearchInput() {
    scheduleSearch();
}

function handleSearchRangeChange() {
    scheduleSearch();
}

/** Perform the full-text search via the /search API. */
async function performSearch(folderName, query) {
    console.log(`Performing full-text search in '${folderName}' for: '${query}'`);
    setLoading(true);
    const startValue = normaliseDateInputValue(searchStartInput?.value);
    const endValue = normaliseDateInputValue(searchEndInput?.value);
    setSearchStatus(`Searching for "${query}"...`);
    conversationList.innerHTML = '';

    try {
        const params = new URLSearchParams({
            folder_name: folderName,
            query
        });
        if (startValue) params.set('start', startValue);
        if (endValue) params.set('end', endValue);

        const response = await fetch(`/search?${params.toString()}`);
        console.log("Search API Response Status:", response.status);
        if (!response.ok) { const errData = await response.json().catch(() => ({ error: `HTTP error ${response.status}` })); console.error("Search API Error:", errData); throw new Error(errData.error || `Search error ${response.status}`); }
        const results = await response.json();
        console.log("Search results (raw):", results);
        console.log("Is results an array?", Array.isArray(results));

        displaySearchResults(results);
        const rangeParts = [];
        if (startValue) {
            const date = new Date(startValue);
            if (!Number.isNaN(date.getTime())) rangeParts.push(`from ${date.toLocaleString()}`);
        }
        if (endValue) {
            const date = new Date(endValue);
            if (!Number.isNaN(date.getTime())) rangeParts.push(`to ${date.toLocaleString()}`);
        }
        const rangeSuffix = rangeParts.length ? ` | ${rangeParts.join(' ')}` : '';
        setSearchStatus(`${results.length} result(s) for "${query}" (content)${rangeSuffix}`);

    } catch (error) {
        console.error('Error during search fetch/processing:', error);
        conversationList.innerHTML = `<li class="empty-list" style="color:orange;">Search error.</li>`;
        setSearchStatus(`Search error: ${error.message}`);
    } finally {
        setLoading(false);
    }
}

/** Render the search results (list of conversation id/title pairs). */
function displaySearchResults(results) {
    console.log("--- displaySearchResults called with:", results);
    conversationList.innerHTML = '';
    if (!results || !Array.isArray(results) || results.length === 0) {
        conversationList.innerHTML = '<li class="empty-list">No results (content).</li>';
        console.log("Displaying 'No results' because results empty/invalid.");
        console.log("------------------------------------");
        return;
    }
    console.log(`Attempting to display ${results.length} search results...`);

    results.forEach((conv, index) => {
        console.log(`  Processing result ${index}:`, conv);
        if (typeof conv !== 'object' || !conv.id || typeof conv.title !== 'string') { console.warn(`  Invalid search result item @ ${index}:`, conv); return; }
        const listItem = document.createElement('li');
        const titleText = conv.title || '[Untitled]';
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

/** Handle clicks within the conversation list. */
function handleConversationClick(event) {
     const listItem = event.target.closest('li');
     if (listItem && listItem.dataset.conversationId) { selectConversationItem(listItem); }
}

/** Mark a list item as selected and show its details. */
function selectConversationItem(listItem) {
    if (!listItem?.dataset?.conversationId || listItem.dataset.conversationId.startsWith('invalid_') || listItem.dataset.conversationId.startsWith('errid_')) return;
    const conversationId = listItem.dataset.conversationId;
    document.querySelectorAll('#conversation-list li.selected').forEach(i => i.classList.remove('selected'));
    listItem.classList.add('selected'); listItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    displayConversation(conversationId);
}

/** Render the detailed content of a conversation. */
function displayConversation(conversationId) {
    // Reset the view
    conversationView.innerHTML = `<h2>Loading...</h2><div id="global-actions" class="global-actions" style="display: none;"><button id="copy-all-button" class="btn-action" title="Copy the entire conversation in Markdown format"><i class=\"fas fa-copy\"></i><span>Copy all</span></button><button id="print-conversation-button" class="btn-action primary" title="Open a print-friendly view"><i class=\"fas fa-print\"></i><span>Print / PDF</span></button></div><div id="conversation-content"></div>`;
    const conversationContentContainer = document.getElementById('conversation-content');
    const globalActionsContainer = document.getElementById('global-actions');
    const copyAllButton = document.getElementById('copy-all-button');
    const printConversationButton = document.getElementById('print-conversation-button');

    // Trouver la conversation
    const conversation = currentFolderData.conversations.find(c => c.id === conversationId);
    if (!conversation) { console.error(`DisplayConv: Conv ${conversationId} not found.`); return; }
    if (!conversationContentContainer || !globalActionsContainer || !copyAllButton) { console.error(`DisplayConv: Missing UI elements.`); return; }

    console.log(`--- Displaying Conversation ID: ${conversationId}, Title: ${conversation.title || '[Untitled]'} ---`);
    console.log("  Mapping structure to process:", conversation.mapping);

    // Title and actions
    conversationView.querySelector('h2').textContent = conversation.title || '[Untitled]';
    globalActionsContainer.style.display = 'block';
    copyAllButton.onclick = null; copyAllButton.addEventListener('click', handleCopyAllMarkdown);
    if (printConversationButton) {
        printConversationButton.onclick = null;
        printConversationButton.addEventListener('click', handleOpenPrintView);
    }

    // Extrait les messages
    const messages = getMessagesFromMapping(conversation.mapping);
    const allowToolMessages = filterToolsCheckbox?.checked !== false;
    if (!messages || messages.length === 0) {
        console.warn(`displayConversation: No messages from getMessagesFromMapping for ${conversationId}.`);
        conversationContentContainer.innerHTML = '<p><i>Empty conversation or content not available.</i></p>';
        if(globalActionsContainer) globalActionsContainer.style.display = 'none';
        return;
    }
    console.log(`  Will display ${messages.length} messages.`);

    // Boucle d'affichage des messages
    let visibleMessages = 0;
    messages.forEach((msg, index) => {
        if (!allowToolMessages && msg.role === 'tool') {
            return;
        }
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', msg.role || 'unknown');

        const roleElement = document.createElement('div');
        roleElement.classList.add('message-role');
        roleElement.textContent = (msg.role || 'unknown').toUpperCase();
        messageElement.appendChild(roleElement);

        const metaElement = document.createElement('div');
        metaElement.classList.add('message-meta');
        const timeSpan = document.createElement('span');
        if (msg.createdAtDisplay) {
            timeSpan.textContent = msg.createdAtDisplay;
            if (msg.createdAtISO) {
                timeSpan.setAttribute('data-timestamp', msg.createdAtISO);
            }
        } else {
            timeSpan.textContent = '';
        }
        metaElement.appendChild(timeSpan);

        const copyButton = document.createElement('button');
        copyButton.className = 'copy-button';
        copyButton.type = 'button';
        copyButton.title = 'Copier ce message en Markdown';
        copyButton.setAttribute('aria-label', 'Copier ce message en Markdown');
        copyButton.innerHTML = '<i class="fas fa-clipboard"></i> Copier';
        copyButton.addEventListener('click', (e) => handleCopySingleMessage(e.currentTarget, msg));
        metaElement.appendChild(copyButton);
        messageElement.appendChild(metaElement);
        // Contenu
        const contentElement = document.createElement('div'); contentElement.classList.add('message-content');
        if (msg.parts?.length) {
            msg.parts.forEach(part => {
                if (typeof part === 'string') {
                    const cleaned = cleanString(part);
                    if (!cleaned.trim()) { return; }
                    const latexMatch = cleaned.match(/\\(?:documentclass|begin\{document\}|maketitle)/i);
                    if (latexMatch && looksLikeLatexSource(cleaned)) {
                        const splitIndex = latexMatch.index ?? 0;
                        const prefix = cleaned.slice(0, splitIndex);
                        const latexBlock = cleaned.slice(splitIndex);
                        if (prefix.trim()) {
                            contentElement.innerHTML += md.render(prefix);
                        }
                        if (latexBlock.trim()) {
                            const pre = document.createElement('pre');
                            const code = document.createElement('code');
                            code.className = 'language-latex';
                            code.innerHTML = basicHighlightToHtml(latexBlock, 'latex');
                            pre.appendChild(code);
                            contentElement.appendChild(pre);
                        }
                    } else {
                        contentElement.innerHTML += md.render(cleaned);
                    }
                }
                else if (part && typeof part === 'object') {
                    // --- Asset rendering block (revised) ---
                    if (part.asset_pointer && currentFolderData.asset_mapping) {
                        const assetFilename = currentFolderData.asset_mapping[part.asset_pointer];
                        if (assetFilename) {
                            const assetUrl = `/export_files/${encodeURIComponent(folderSelector.value)}/${encodeURIComponent(assetFilename)}`;
                            const explicitMimeType = currentFolderData.file_types?.[assetFilename];
                            let isImage = false, isAudio = false; let fileTypeDesc = "File";
                            console.log(`  [Asset Debug] File: ${assetFilename}, Explicit Type: ${explicitMimeType}`);

                            // Decide based on the explicit MIME type (relaxed logic)
                            if (explicitMimeType && typeof explicitMimeType === 'string') {
                                const lowerMime = explicitMimeType.toLowerCase();
                                fileTypeDesc = explicitMimeType;
                                // Relaxed MIME identification
                                if (lowerMime.startsWith('image/') || ['png image data', 'jpeg image data', 'gif image data', 'webp image data', 'svg xml'].some(k => lowerMime.includes(k))) {
                                    isImage = true; console.log(`    -> Classified as IMAGE (MIME)`);
                                } else if (lowerMime.startsWith('audio/') || ['mpeg layer 3', 'wave audio', 'ogg data', 'flac audio', 'aac audio'].some(k => lowerMime.includes(k))) {
                                    isAudio = true; console.log(`    -> Classified as AUDIO (MIME)`);
                                } else if (lowerMime === 'application/octet-stream' || lowerMime === 'file not found') { console.log(`    -> MIME inconclusive (${explicitMimeType}). Will try ext.`); fileTypeDesc = (lowerMime === 'file not found')?"File not found":"Binary"; }
                                else { console.log(`    -> MIME '${explicitMimeType}' not recognized.`); }
                            } else { console.log(`    -> No explicit MIME. Will use extension.`); }

                            // Extension-based fallback when MIME does not classify the file
                            if (!isImage && !isAudio) {
                                console.log(`    -> Applying extension fallback: ${assetFilename}`);
                                if (/\.(png|jpg|jpeg|gif|webp|svg|bmp)$/i.test(assetFilename)) { isImage = true; console.log(`    -> Classified as IMAGE (Ext)`); if (fileTypeDesc === "File" || fileTypeDesc === "Binary") fileTypeDesc = "Image (Ext)"; }
                                else if (/\.(wav|mp3|ogg|m4a|aac|flac)$/i.test(assetFilename)) { isAudio = true; console.log(`    -> Classified as AUDIO (Ext)`); if (fileTypeDesc === "File" || fileTypeDesc === "Binary") fileTypeDesc = "Audio (Ext)"; }
                                else { console.log(`    -> Ext fallback no match.`); }
                            }
                            // Render the asset element
                            if (isImage) { const img=document.createElement('img'); img.src=assetUrl; img.alt=`Image: ${assetFilename}`; img.style.cssText='max-width:100%;max-height:450px;display:block;margin:10px 0;'; img.onerror=() => img.alt=`Image load error: ${assetFilename}`; contentElement.appendChild(img); }
                            else if (isAudio) { const audC=document.createElement('div'); const aud=document.createElement('audio'); aud.controls=true; aud.src=assetUrl; aud.style.width='100%'; audC.appendChild(aud); const d=document.createElement('p'); d.innerHTML=`<i style='font-size:0.9em;color:#555'>Audio: ${assetFilename} (${fileTypeDesc})</i>`; d.style.margin="0 0 10px 0"; contentElement.appendChild(audC); contentElement.appendChild(d); }
                            else { const a=document.createElement('a'); a.href=assetUrl; a.target='_blank'; a.textContent=`[${cleanString(fileTypeDesc)}]: ${assetFilename}`; a.classList.add('data-link'); const p=document.createElement('p'); p.appendChild(a); contentElement.appendChild(p); }
                        } else { contentElement.innerHTML += `<p><i>[File (${cleanString(part.asset_pointer)}) not mapped]</i></p>`; }
                    // --- End of asset rendering block ---
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
                    else { console.warn("Unhandled object part:", part); contentElement.innerHTML += `<p><i>[Unhandled object content]</i></p>`; }
                } else if (part !== null && part !== undefined) { console.warn("Unexpected part type:", typeof part, part); }
            });
        } else if (msg.text && typeof msg.text === 'string') { const cleaned=cleanString(msg.text); if (cleaned.trim()) contentElement.innerHTML += md.render(cleaned); }
        else if (contentElement.innerHTML.trim() === '') { contentElement.innerHTML = '<i>[Empty message]</i>'; }
        enhanceCodeBlocks(contentElement);
        messageElement.appendChild(contentElement);
        conversationContentContainer.appendChild(messageElement);
        visibleMessages += 1;
    }); // End of message loop

    // Trigger KaTeX
    try { if (window.renderMathInElement) { renderMathInElement(conversationContentContainer, { delimiters: [{left:"$$",right:"$$",display:true},{left:"$",right:"$",display:false},{left:"\\[",right:"\\]",display:true},{left:"\\(",right:"\\)",display:false}], throwOnError: false }); } } catch (e) { console.error("KaTeX Error:", e); }
    if (mainContent) { mainContent.scrollTop = 0; } // Scroll top

    if (visibleMessages === 0) {
        conversationContentContainer.innerHTML = '<p><i>All tool messages are hidden by the current filter.</i></p>';
        if (globalActionsContainer) {
            globalActionsContainer.style.display = 'none';
        }
    }
}


/** Extract ordered messages from the mapping (verbose logging version). */
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
                 if (Array.isArray(parts) && parts.length > 0) {
                     let createdAt = null;
                     if (typeof msg.create_time === 'number' && Number.isFinite(msg.create_time)) {
                         createdAt = msg.create_time;
                     } else if (typeof msg.create_time === 'string' && msg.create_time.trim()) {
                         const parsedTs = Number(msg.create_time);
                         if (Number.isFinite(parsedTs)) createdAt = parsedTs;
                     }
                     const createdAtDisplay = createdAt !== null ? formatTimestampSeconds(createdAt) : null;
                     const createdAtISO = createdAt !== null ? new Date(createdAt * 1000).toISOString() : null;
                     messages.push({ role: role, parts: parts, createdAt, createdAtDisplay, createdAtISO });
                     /* console.log(`      -> ADDED MESSAGE node ${nodeId}`); */
                 }
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

/** Produce Markdown for a single message part. */
function getMarkdownForMessagePart(part) {
    if (typeof part === 'string') { return cleanString(part).trim(); }
    else if (part && typeof part === 'object') {
        if (part.asset_pointer && currentFolderData.asset_mapping) { const fn = currentFolderData.asset_mapping[part.asset_pointer]; if (fn) { const safeFn = fn.replace(/[<>:"/\\|?*]/g, '_'); const type = currentFolderData.file_types?.[fn]; let i=0, a=0; if(type){const lt=type.toLowerCase();if(lt.startsWith('image/')||['png image data','jpeg image data'].some(k=>lt.includes(k)))i=1;else if(lt.startsWith('audio/')||['mpeg layer 3','wave audio'].some(k=>lt.includes(k)))a=1;} if(!i&&!a&&/\.(png|jpe?g|gif|webp|svg)$/i.test(fn))i=1;else if(!i&&!a&&/\.(wav|mp3|ogg|m4a|aac|flac)$/i.test(fn))a=1; if(i) return `![Image: ${fn}](${safeFn})`; if(a) return `[Audio: ${fn}](${safeFn})`; return `[File: ${fn}](${safeFn})`; } else return `*[Missing mapping: ${part.asset_pointer}]*`; }
        else if (part.content_type === 'code' && part.text) { const lang=part.language||''; return `\`\`\`${lang}\n${cleanString(part.text||'')}\n\`\`\``; }
        else if (part.text && typeof part.text === 'string') {
            const text = cleanString(part.text).trim();
            if (!text) return '';
            if (looksLikeLatexSource(text)) {
                const latexMatch = text.match(/\\(?:documentclass|begin\{document\}|maketitle)/i);
                if (latexMatch && latexMatch.index > 0) {
                    const prefix = text.slice(0, latexMatch.index).trim();
                    const latexBlock = text.slice(latexMatch.index).trim();
                    const parts = [];
                    if (prefix) {
                        parts.push(prefix);
                    }
                    if (latexBlock) {
                        parts.push(`\`\`\`latex\n${latexBlock}\n\`\`\``);
                    }
                    return parts.join('\n\n');
                }
                return `\`\`\`latex\n${text}\n\`\`\``;
            }
            return text;
        }
        else return `*[Unhandled object content]*`;
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
    css: 'css',
    tex: 'latex',
    plaintex: 'latex'
};

const CODE_KEYWORDS = {
    python: ['def','class','return','if','elif','else','for','while','try','except','finally','raise','import','from','as','with','lambda','yield','True','False','None','pass','break','continue','global','nonlocal','assert','async','await'],
    javascript: ['function','return','if','else','for','while','do','switch','case','break','continue','const','let','var','class','extends','import','from','export','default','new','this','super','try','catch','finally','throw','async','await','null','undefined','true','false'],
    c: ['int','float','double','char','void','long','short','unsigned','signed','return','if','else','for','while','do','switch','case','break','continue','struct','typedef','enum','sizeof','static','const','volatile','extern','NULL'],
    css: ['@media','@import','@font-face','@keyframes','from','to','var'],
    html: ['html','head','body','title','meta','link','script','style','div','span','section','article','nav','header','footer','main','aside','ul','ol','li','table','thead','tbody','tr','td','th','form','input','button','label','textarea','canvas','svg','img','a'],
    latex: [],
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
    if (!language) return '';
    const key = language.toLowerCase();
    return CODE_LANGUAGE_ALIASES[key] || key;
}

function looksLikeLatexSource(source) {
    if (typeof source !== 'string') return false;
    return /\\(?:begin|end|frac|left|right|text|mathit|mathrm|mathbf|mathbb|documentclass|usepackage|section|subsection)/i.test(source);
}

function getHighlightPatterns(language, source) {
    const normalisedLang = normalizeLanguageAlias(language);
    const effectiveLang = normalisedLang || (looksLikeLatexSource(source) ? 'latex' : '');
    const patterns = [];

    patterns.push({ regex: /"(?:\\.|[^"\\])*"/g, type: 'string', priority: 40 });
    if (effectiveLang !== 'latex') {
        patterns.push({ regex: /'(?:\\.|[^'\\])*'/g, type: 'string', priority: 40 });
    }
    patterns.push({ regex: /`(?:\\.|[^`\\])*`/g, type: 'string', priority: 40 });
    patterns.push({ regex: /\b0x[0-9a-fA-F]+\b/g, type: 'number', priority: 25 });
    patterns.push({ regex: /\b\d+(?:\.\d+)?\b/g, type: 'number', priority: 25 });

    if (effectiveLang === 'python') {
        patterns.push({ regex: /(?<!["'])#.*$/gm, type: 'comment', priority: 50 });
        patterns.push({ regex: /("""|''')[\s\S]*?\1/g, type: 'string', priority: 45 });
    } else if (effectiveLang === 'javascript' || effectiveLang === 'c' || effectiveLang === 'css') {
        patterns.push({ regex: /\/\/.*$/gm, type: 'comment', priority: 50 });
        patterns.push({ regex: /\/\*[\s\S]*?\*\//g, type: 'comment', priority: 50 });
    } else if (effectiveLang === 'html') {
        patterns.push({ regex: /<!--[\s\S]*?-->/g, type: 'comment', priority: 50 });
    } else if (effectiveLang === 'latex') {
        patterns.push({ regex: /%.*$/gm, type: 'comment', priority: 55 });
        patterns.push({ regex: /\\[a-zA-Z@]+\*?/g, type: 'command', priority: 52 });
        patterns.push({ regex: /\\[^\s]/g, type: 'command', priority: 51 });
        patterns.push({ regex: /[{}]/g, type: 'brace', priority: 26 });
        patterns.push({ regex: /[\[\]]/g, type: 'optional-delim', priority: 26 });
    }

    if (effectiveLang === 'c') {
        patterns.push({ regex: /#[a-zA-Z_]\w*/g, type: 'keyword', priority: 32 });
    }

    if (effectiveLang === 'css') {
        patterns.push({ regex: /@[a-zA-Z-]+/g, type: 'keyword', priority: 32 });
        patterns.push({ regex: /(?:--)?[a-zA-Z][a-zA-Z0-9-]*(?=\s*:)/g, type: 'property', priority: 28 });
    }

    if (effectiveLang === 'html') {
        patterns.push({ regex: /<\/?[a-zA-Z][a-zA-Z0-9:-]*/g, type: 'tag', priority: 45 });
        patterns.push({ regex: /\b[a-zA-Z-:]+(?=\s*=)/g, type: 'attr', priority: 30 });
        patterns.push({ regex: /&[a-zA-Z0-9#]+;/g, type: 'entity', priority: 20 });
    }

    const keywordList = CODE_KEYWORDS[effectiveLang] || CODE_KEYWORDS.default;
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
    const patterns = getHighlightPatterns(language, source);
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

function populateFolderNameSuggestion() {
    setUploadStatus('');
    if (!uploadExportFileInput?.files?.length || !uploadExportFolderInput) return;
    if (uploadExportFolderInput.value && uploadExportFolderInput.value.trim()) return;
    const file = uploadExportFileInput.files[0];
    if (!file || !file.name) return;
    const suggestion = file.name.replace(/\.zip$/i, '').replace(/[^A-Za-z0-9._-]+/g, '-');
    if (suggestion) {
        uploadExportFolderInput.value = suggestion;
    }
}

async function handleUploadExportSubmit(event) {
    event.preventDefault();
    setUploadStatus('');
    if (!uploadExportFileInput?.files?.length) {
        setUploadStatus('Error: select a ZIP file.');
        return;
    }
    const destination = (uploadExportDestinationInput?.value || '').trim();
    if (!destination) {
        setUploadStatus('Error: provide a destination path.');
        return;
    }
    const folderName = (uploadExportFolderInput?.value || '').trim();
    const file = uploadExportFileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    formData.append('destination_root', destination);
    if (folderName) {
        formData.append('folder_name', folderName);
    }

    setUploadStatus('Import in progress...');
    if (uploadExportButton) {
        uploadExportButton.disabled = true;
    }
    try {
        const response = await fetch('/upload_export', {
            method: 'POST',
            body: formData
        });
        let payload = {};
        try {
            payload = await response.json();
        } catch (err) {
            payload = {};
        }
        if (!response.ok) {
            const msg = payload.error || 'Import failed.';
            throw new Error(msg);
        }
        setUploadStatus('Import successful. Reloading...');
        setTimeout(() => {
            window.location.reload();
        }, 800);
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error.';
        setUploadStatus(`Error: ${message}`);
    } finally {
        if (uploadExportButton) {
            uploadExportButton.disabled = false;
        }
    }
}

/** Copy a single message block to the clipboard. */
function handleCopySingleMessage(buttonElement, messageData) {
    let md=''; if (messageData.parts?.length) md = messageData.parts.map(getMarkdownForMessagePart).filter(m=>m).join('\n\n'); else if(messageData.text) md = getMarkdownForMessagePart(messageData.text);
    if(md) copyTextToClipboard(md.trim(), buttonElement); else { /* empty feedback */ }
}

/** Copy the entire conversation in Markdown form. */
function handleCopyAllMarkdown(event) {
    const li = conversationList.querySelector('li.selected'); if(!li?.dataset?.conversationId) return; const convId = li.dataset.conversationId; const conv = currentFolderData.conversations.find(c=>c.id===convId); if(!conv) return;
    let fullMd = `# ${conv.title||'Conversation'}\n\n`; const msgs = getMessagesFromMapping(conv.mapping);
    const allowToolMessages = filterToolsCheckbox?.checked !== false;
    if(msgs?.length) msgs.forEach(msg => {
        if (!allowToolMessages && msg.role === 'tool') { return; }
        fullMd += `**${msg.role.toUpperCase()}**:\n\n`;
        let msgMd='';
        if(msg.parts?.length) msgMd=msg.parts.map(getMarkdownForMessagePart).filter(m=>m).join('\n\n');
        else if(msg.text) msgMd=getMarkdownForMessagePart(msg.text);
        fullMd += msgMd.trim() + '\n\n---\n\n';
    });
    else fullMd += "*[Empty]*"; copyTextToClipboard(fullMd.trim(), event.currentTarget);
}

function withScopedClassOnBody(className, callback) {
    if (!document?.body) {
        callback();
        return;
    }
    document.body.classList.add(className);
    const removeClass = () => document.body.classList.remove(className);

    let cleanup = null;
    if ('onafterprint' in window) {
        const handler = () => {
            window.removeEventListener('afterprint', handler);
            removeClass();
        };
        window.addEventListener('afterprint', handler);
        cleanup = () => window.removeEventListener('afterprint', handler);
    } else if (window.matchMedia) {
        const mediaQueryList = window.matchMedia('print');
        const mqHandler = (event) => {
            if (!event.matches) {
                mediaQueryList.removeEventListener('change', mqHandler);
                removeClass();
            }
        };
        mediaQueryList.addEventListener('change', mqHandler);
        cleanup = () => mediaQueryList.removeEventListener('change', mqHandler);
    } else {
        setTimeout(removeClass, 500);
    }

    try {
        callback();
    } catch (error) {
        if (cleanup) {
            cleanup();
        }
        removeClass();
        throw error;
    }
}

function handleOpenPrintView(event) {
    const selected = conversationList?.querySelector('li.selected');
    if (!selected?.dataset?.conversationId) {
        alert('Select a conversation first.');
        return;
    }

    if (!document?.body) {
        window.print();
        return;
    }

    withScopedClassOnBody('print-mode', () => {
        window.print();
    });
}

/** Keyboard navigation shortcuts. */
function handleKeyboardNavigation(event) {
    const activeEl = document.activeElement; const inputFocus = activeEl && (['input','textarea','select'].includes(activeEl.tagName.toLowerCase())); if (inputFocus || !mainContent) return;
    const scrollAmt = mainContent.clientHeight*0.85; switch(event.key){ case 'PageDown': event.preventDefault();mainContent.scrollBy({top:scrollAmt,behavior:'smooth'}); break; case 'PageUp': event.preventDefault();mainContent.scrollBy({top:-scrollAmt,behavior:'smooth'}); break; case 'End': if(event.ctrlKey||event.metaKey){event.preventDefault();mainContent.scrollTo({top:mainContent.scrollHeight,behavior:'smooth'});} break; case 'Home': if(event.ctrlKey||event.metaKey){event.preventDefault();mainContent.scrollTo({top:0,behavior:'smooth'});} break; }
}
