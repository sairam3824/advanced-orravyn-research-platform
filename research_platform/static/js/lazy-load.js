/**
 * Lazy Loading & Performance Utilities
 * Orravyn Research Platform
 */

(function() {
    'use strict';

    // ============================================================
    // LAZY LOAD IMAGES
    // ============================================================
    
    function initLazyImages() {
        const lazyImages = document.querySelectorAll('img[loading="lazy"]');
        
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src || img.src;
                        img.classList.add('loaded');
                        observer.unobserve(img);
                    }
                });
            }, {
                rootMargin: '50px 0px',
                threshold: 0.01
            });

            lazyImages.forEach(img => imageObserver.observe(img));
        } else {
            // Fallback for browsers without IntersectionObserver
            lazyImages.forEach(img => {
                img.src = img.dataset.src || img.src;
                img.classList.add('loaded');
            });
        }
    }

    // ============================================================
    // LAZY LOAD CONTENT SECTIONS
    // ============================================================
    
    function initLazyContent() {
        const lazyElements = document.querySelectorAll('.lazy-load');
        
        if ('IntersectionObserver' in window) {
            const contentObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('visible');
                        observer.unobserve(entry.target);
                    }
                });
            }, {
                rootMargin: '0px 0px -100px 0px',
                threshold: 0.1
            });

            lazyElements.forEach(el => contentObserver.observe(el));
        } else {
            // Fallback
            lazyElements.forEach(el => el.classList.add('visible'));
        }
    }

    // ============================================================
    // INFINITE SCROLL (Optional)
    // ============================================================
    
    function initInfiniteScroll() {
        const loadMoreBtn = document.querySelector('[data-load-more]');
        if (!loadMoreBtn) return;

        const container = document.querySelector('[data-infinite-scroll]');
        if (!container) return;

        let loading = false;
        let page = 2;

        const loadMore = async () => {
            if (loading) return;
            loading = true;

            loadMoreBtn.innerHTML = '<span class="loading-spinner"></span> Loading...';
            loadMoreBtn.disabled = true;

            try {
                const url = new URL(window.location.href);
                url.searchParams.set('page', page);
                
                const response = await fetch(url.toString(), {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                if (response.ok) {
                    const html = await response.text();
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    const newItems = doc.querySelectorAll('[data-infinite-scroll] > *');

                    if (newItems.length > 0) {
                        newItems.forEach(item => {
                            item.classList.add('fade-in');
                            container.appendChild(item);
                        });
                        page++;
                        loadMoreBtn.innerHTML = 'Load More';
                        loadMoreBtn.disabled = false;
                    } else {
                        loadMoreBtn.innerHTML = 'No more items';
                        loadMoreBtn.disabled = true;
                    }
                }
            } catch (error) {
                console.error('Error loading more items:', error);
                loadMoreBtn.innerHTML = 'Error loading. Try again';
                loadMoreBtn.disabled = false;
            }

            loading = false;
        };

        loadMoreBtn.addEventListener('click', loadMore);

        // Optional: Auto-load on scroll
        if (loadMoreBtn.dataset.autoLoad === 'true') {
            const observer = new IntersectionObserver((entries) => {
                if (entries[0].isIntersecting && !loading) {
                    loadMore();
                }
            }, { rootMargin: '200px' });

            observer.observe(loadMoreBtn);
        }
    }

    // ============================================================
    // DEBOUNCE UTILITY
    // ============================================================
    
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // ============================================================
    // RESPONSIVE IMAGES
    // ============================================================
    
    function initResponsiveImages() {
        const images = document.querySelectorAll('img[data-srcset]');
        
        images.forEach(img => {
            if (img.dataset.srcset) {
                img.srcset = img.dataset.srcset;
            }
        });
    }

    // ============================================================
    // PERFORMANCE MONITORING
    // ============================================================
    
    function logPerformance() {
        if ('performance' in window && 'getEntriesByType' in performance) {
            window.addEventListener('load', () => {
                setTimeout(() => {
                    const perfData = performance.getEntriesByType('navigation')[0];
                    if (perfData) {
                        console.log('Page Load Time:', Math.round(perfData.loadEventEnd - perfData.fetchStart), 'ms');
                        console.log('DOM Content Loaded:', Math.round(perfData.domContentLoadedEventEnd - perfData.fetchStart), 'ms');
                    }
                }, 0);
            });
        }
    }

    // ============================================================
    // SMOOTH SCROLL
    // ============================================================
    
    function initSmoothScroll() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function(e) {
                const href = this.getAttribute('href');
                if (href === '#') return;

                const target = document.querySelector(href);
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    }

    // ============================================================
    // BACK TO TOP BUTTON
    // ============================================================
    
    function initBackToTop() {
        const backToTop = document.createElement('button');
        backToTop.innerHTML = '<i class="fas fa-arrow-up"></i>';
        backToTop.className = 'back-to-top';
        backToTop.setAttribute('aria-label', 'Back to top');
        backToTop.style.cssText = `
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: var(--primary-gradient);
            color: white;
            border: none;
            cursor: pointer;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
            z-index: 1000;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
        `;

        document.body.appendChild(backToTop);

        const toggleBackToTop = debounce(() => {
            if (window.pageYOffset > 300) {
                backToTop.style.opacity = '1';
                backToTop.style.visibility = 'visible';
            } else {
                backToTop.style.opacity = '0';
                backToTop.style.visibility = 'hidden';
            }
        }, 100);

        window.addEventListener('scroll', toggleBackToTop);

        backToTop.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }

    // ============================================================
    // INITIALIZE ALL
    // ============================================================
    
    function init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        initLazyImages();
        initLazyContent();
        initResponsiveImages();
        initInfiniteScroll();
        initSmoothScroll();
        initBackToTop();
        
        // Performance monitoring (only in development)
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            logPerformance();
        }
    }

    // Start initialization
    init();

})();
