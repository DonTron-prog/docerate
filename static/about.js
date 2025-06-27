// About page interactions
document.addEventListener('DOMContentLoaded', function() {
    // Get all resume tiles
    const resumeTiles = document.querySelectorAll('.resume-tile');
    
    // Add click handlers to each tile
    resumeTiles.forEach(tile => {
        const header = tile.querySelector('.tile-header');
        
        header.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleTile(tile);
        });
        
        // Prevent clicks on content from toggling
        const content = tile.querySelector('.tile-content');
        content.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    });
    
    // Function to toggle a tile
    function toggleTile(tile) {
        const isExpanded = tile.classList.contains('expanded');
        
        // If expanding this tile, collapse others first (optional behavior)
        // Uncomment the next 3 lines if you want only one tile open at a time
        // resumeTiles.forEach(t => {
        //     t.classList.remove('expanded');
        // });
        
        // Toggle the clicked tile
        tile.classList.toggle('expanded');
        
        // Smooth scroll to tile if expanding
        if (!isExpanded) {
            setTimeout(() => {
                const rect = tile.getBoundingClientRect();
                const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                const targetY = rect.top + scrollTop - 100; // 100px offset from top
                
                window.scrollTo({
                    top: targetY,
                    behavior: 'smooth'
                });
            }, 100);
        }
    }
    
    // Keyboard navigation
    document.addEventListener('keydown', function(e) {
        // Escape key closes all tiles
        if (e.key === 'Escape') {
            resumeTiles.forEach(tile => {
                tile.classList.remove('expanded');
            });
        }
    });
    
    // URL hash navigation
    function checkHashAndExpand() {
        const hash = window.location.hash.slice(1);
        if (hash) {
            const targetTile = document.querySelector(`[data-section="${hash}"]`);
            if (targetTile && !targetTile.classList.contains('expanded')) {
                // Collapse all tiles first
                resumeTiles.forEach(tile => {
                    tile.classList.remove('expanded');
                });
                // Expand the target tile
                targetTile.classList.add('expanded');
                // Scroll to it
                setTimeout(() => {
                    targetTile.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 100);
            }
        }
    }
    
    // Check on page load
    checkHashAndExpand();
    
    // Check on hash change
    window.addEventListener('hashchange', checkHashAndExpand);
    
    // Add hover effect for tiles
    resumeTiles.forEach(tile => {
        tile.addEventListener('mouseenter', function() {
            if (!tile.classList.contains('expanded')) {
                tile.style.transform = 'translateY(-4px)';
            }
        });
        
        tile.addEventListener('mouseleave', function() {
            if (!tile.classList.contains('expanded')) {
                tile.style.transform = 'translateY(0)';
            }
        });
    });
    
    // Optional: Add analytics tracking for tile interactions
    resumeTiles.forEach(tile => {
        tile.addEventListener('click', function() {
            const section = tile.getAttribute('data-section');
            const action = tile.classList.contains('expanded') ? 'expand' : 'collapse';
            
            // You can add analytics tracking here
            console.log(`About section ${action}: ${section}`);
        });
    });
    
    // Print functionality - expand all tiles when printing
    window.addEventListener('beforeprint', function() {
        resumeTiles.forEach(tile => {
            tile.classList.add('expanded');
        });
    });
    
    // Optional: Restore state after printing
    window.addEventListener('afterprint', function() {
        // You might want to restore the previous state
        // For now, we'll just collapse all
        resumeTiles.forEach(tile => {
            tile.classList.remove('expanded');
        });
    });
});