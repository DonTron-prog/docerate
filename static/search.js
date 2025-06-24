// Simple client-side search implementation
(function() {
    let searchData = [];
    let searchModal = null;
    let searchInput = null;
    let searchResults = null;
    
    // Initialize search
    function initSearch() {
        searchModal = document.getElementById('search-modal');
        searchInput = document.getElementById('search-input');
        searchResults = document.getElementById('search-results');
        
        if (!searchModal || !searchInput || !searchResults) return;
        
        // Load search data
        fetch('/search.json')
            .then(response => response.json())
            .then(data => {
                searchData = data;
            })
            .catch(error => console.error('Failed to load search data:', error));
        
        // Event listeners
        document.querySelector('.search-toggle').addEventListener('click', openSearch);
        document.querySelector('.search-close').addEventListener('click', closeSearch);
        searchModal.addEventListener('click', function(e) {
            if (e.target === searchModal) closeSearch();
        });
        
        searchInput.addEventListener('input', performSearch);
        
        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (e.key === '/' && !isInputFocused()) {
                e.preventDefault();
                openSearch();
            } else if (e.key === 'Escape' && searchModal.classList.contains('active')) {
                closeSearch();
            }
        });
    }
    
    function isInputFocused() {
        const activeElement = document.activeElement;
        return activeElement.tagName === 'INPUT' || 
               activeElement.tagName === 'TEXTAREA';
    }
    
    function openSearch(e) {
        if (e) e.preventDefault();
        searchModal.classList.add('active');
        searchInput.focus();
        searchInput.value = '';
        searchResults.innerHTML = '';
    }
    
    function closeSearch() {
        searchModal.classList.remove('active');
    }
    
    function performSearch() {
        const query = searchInput.value.toLowerCase().trim();
        
        if (query.length < 2) {
            searchResults.innerHTML = '';
            return;
        }
        
        const results = searchData.filter(post => {
            const searchText = (
                post.title + ' ' + 
                post.content + ' ' + 
                post.tags.join(' ')
            ).toLowerCase();
            
            return searchText.includes(query);
        });
        
        displayResults(results, query);
    }
    
    function displayResults(results, query) {
        if (results.length === 0) {
            searchResults.innerHTML = '<p class="no-results">No results found</p>';
            return;
        }
        
        const html = results.map(post => {
            const excerpt = getExcerpt(post.content, query);
            const highlightedTitle = highlightText(post.title, query);
            const date = new Date(post.date).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
            
            return `
                <div class="search-result">
                    <h3><a href="${post.url}">${highlightedTitle}</a></h3>
                    <div class="search-meta">
                        <time>${date}</time>
                        ${post.tags.length > 0 ? `• ${post.tags.join(', ')}` : ''}
                    </div>
                    <p class="search-excerpt">${excerpt}</p>
                </div>
            `;
        }).join('');
        
        searchResults.innerHTML = html;
    }
    
    function getExcerpt(content, query) {
        const queryIndex = content.toLowerCase().indexOf(query);
        if (queryIndex === -1) {
            return content.substring(0, 150) + '...';
        }
        
        const start = Math.max(0, queryIndex - 50);
        const end = Math.min(content.length, queryIndex + query.length + 100);
        let excerpt = content.substring(start, end);
        
        if (start > 0) excerpt = '...' + excerpt;
        if (end < content.length) excerpt = excerpt + '...';
        
        return highlightText(excerpt, query);
    }
    
    function highlightText(text, query) {
        const regex = new RegExp(`(${escapeRegExp(query)})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }
    
    function escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSearch);
    } else {
        initSearch();
    }
})();