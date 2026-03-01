/* ============================================================
   Orravyn Research Platform — Global JavaScript
   ============================================================ */

'use strict';

/* ── Particle system ─────────────────────────────────────────── */
function createParticles() {
    const container = document.getElementById('particles');
    if (!container) return;

    container.innerHTML = '';
    const count = Math.min(50, Math.floor(window.innerWidth / 30));

    for (let i = 0; i < count; i++) {
        const el = document.createElement('div');
        el.className = 'particle';

        const size = Math.random() * 4 + 1;
        const duration = Math.random() * 3 + 3;
        const delay = Math.random() * 2;

        Object.assign(el.style, {
            width: size + 'px',
            height: size + 'px',
            left: Math.random() * window.innerWidth + 'px',
            top: Math.random() * window.innerHeight + 'px',
            animationDuration: duration + 's',
            animationDelay: delay + 's',
        });

        container.appendChild(el);
    }
}

/* ── Navbar scroll behaviour ─────────────────────────────────── */
(function initNavbarScroll() {
    const navbar = document.querySelector('.navbar');
    if (!navbar) return;

    window.addEventListener('scroll', function () {
        if (window.pageYOffset > 50) {
            navbar.style.background = 'rgba(0, 0, 0, 0.95)';
            navbar.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.3)';
        } else {
            navbar.style.background = 'rgba(0, 0, 0, 0.2)';
            navbar.style.boxShadow = 'none';
        }
    }, { passive: true });
})();

/* ── DOMContentLoaded ────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function () {
    createParticles();

    /* Dropdown hover micro-animation */
    document.querySelectorAll('.dropdown-item').forEach(function (item) {
        item.addEventListener('mouseenter', function () {
            this.style.transform = 'translateX(10px) scale(1.02)';
        });
        item.addEventListener('mouseleave', function () {
            this.style.transform = '';
        });
    });

    /* Auto-dismiss alerts after 5 s */
    setTimeout(function () {
        document.querySelectorAll('.alert').forEach(function (alert) {
            if (alert.querySelector('.btn-close')) {
                alert.style.transition = 'all 0.5s ease-out';
                alert.style.transform = 'translateY(-100%)';
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 500);
            }
        });
    }, 5000);

    /* Mobile navbar auto-close on link click */
    const toggler = document.querySelector('.navbar-toggler');
    const collapse = document.querySelector('.navbar-collapse');

    if (toggler && collapse) {
        toggler.addEventListener('click', function () {
            if (this.getAttribute('aria-expanded') !== 'true') {
                collapse.style.animation = 'slideInDown 0.3s ease-out';
            }
        });

        collapse.querySelectorAll('.nav-link:not(.dropdown-toggle)').forEach(function (link) {
            link.addEventListener('click', function () {
                if (window.innerWidth < 992) {
                    const bsCollapse = new bootstrap.Collapse(collapse, { toggle: false });
                    bsCollapse.hide();
                }
            });
        });
    }
});

/* ── Beta notice ─────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function () {
    const notice = document.getElementById('beta-notice');
    if (!notice) return;

    function dismissNotice() {
        notice.style.opacity = '0';
        notice.style.pointerEvents = 'none';
        setTimeout(() => notice.remove(), 500);
    }

    if (!sessionStorage.getItem('betaNoticeShown')) {
        notice.style.display = 'flex';
        sessionStorage.setItem('betaNoticeShown', 'true');

        // Auto-dismiss after 4 s
        setTimeout(dismissNotice, 4000);

        // Click the dark backdrop (not the card) to dismiss immediately
        notice.addEventListener('click', function (e) {
            if (e.target === notice) dismissNotice();
        });
    } else {
        notice.remove();
    }
});

/* ── Smooth scroll for anchor links ──────────────────────────── */
document.addEventListener('click', function (e) {
    const anchor = e.target.closest('a[href^="#"]');
    if (anchor && !anchor.hasAttribute('data-bs-toggle') && anchor.getAttribute('href').length > 1) {
        e.preventDefault();
        const target = document.getElementById(anchor.getAttribute('href').substring(1));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
});

/* ── Rebuild particles on resize (debounced) ─────────────────── */
let _resizeTimer;
window.addEventListener('resize', function () {
    clearTimeout(_resizeTimer);
    _resizeTimer = setTimeout(createParticles, 150);
}, { passive: true });

/* ── Global Confirm Overlay using SweetAlert2 ────────────────── */
window.confirmAction = function(event, message) {
    event.preventDefault();
    const target = event.currentTarget;
    
    // Check if it's already fired by SweetAlert logic (handling direct calls bypass)
    // Actually, simple setup:
    Swal.fire({
        title: 'Are you sure?',
        text: message || "Do you want to proceed with this action?",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#2563eb', // Matches var(--accent-color)
        cancelButtonColor: '#e11d48',
        confirmButtonText: '<i class="fas fa-check"></i> Yes, proceed!',
        cancelButtonText: 'Cancel',
        background: 'rgba(255, 255, 255, 0.95)',
        backdrop: 'rgba(0, 0, 0, 0.5)',
        customClass: {
            popup: 'swal2-glass-popup',
            confirmButton: 'btn btn-primary',
            cancelButton: 'btn btn-secondary'
        }
    }).then((result) => {
        if (result.isConfirmed) {
            // Handle links
            if (target.tagName.toLowerCase() === 'a' && target.href) {
                window.location.href = target.href;
            } 
            // Handle buttons/forms
            else if (target.tagName.toLowerCase() === 'button' && target.closest('form')) {
                // Submit the parent form
                target.closest('form').submit();
            } else if (target.tagName.toLowerCase() === 'button') {
                target.click(); // Not ideal, might loop, but mostly buttons have a submit logic above
            }
        }
    });
    
    return false; // Crucial to return false for inline onclick handlers
};

/* ── ESC key to clear search inputs ──────────────────────────── */
document.addEventListener('keydown', function(e) {
    // Check if ESC key is pressed
    if (e.key === 'Escape' || e.keyCode === 27) {
        const activeElement = document.activeElement;
        
        // Check if the focused element is a search input
        if (activeElement && 
            (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA') &&
            (activeElement.type === 'text' || activeElement.type === 'search' || 
             activeElement.placeholder.toLowerCase().includes('search') ||
             activeElement.id.toLowerCase().includes('search') ||
             activeElement.className.toLowerCase().includes('search'))) {
            
            // Clear the input value
            activeElement.value = '';
            
            // Trigger input event to update any live search results
            const inputEvent = new Event('input', { bubbles: true });
            activeElement.dispatchEvent(inputEvent);
            
            // Optional: blur the input to close any dropdowns
            // activeElement.blur();
            
            // Visual feedback - brief highlight
            const originalBorder = activeElement.style.borderColor;
            activeElement.style.borderColor = 'var(--accent-color)';
            activeElement.style.transition = 'border-color 0.3s ease';
            
            setTimeout(() => {
                activeElement.style.borderColor = originalBorder;
            }, 300);
        }
    }
});
