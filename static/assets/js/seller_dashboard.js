// Kishan Hub Dashboard JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize dashboard
    initializeDashboard();
    
    // Setup event listeners
    setupEventListeners();
    
    // Load dashboard data
    loadDashboardData();
});

function initializeDashboard() {
    // Add fade-in animation to main content
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.classList.add('fade-in');
    }
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

function setupEventListeners() {
    // Sidebar navigation
    const navLinks = document.querySelectorAll('.sidebar .nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            // ✅ FIX: No preventDefault — allow link navigation
            // Remove active class from all links
            navLinks.forEach(l => l.classList.remove('active'));
            
            // Add active class to clicked link
            this.classList.add('active');
        });
    });
    
    // Quick action buttons
    const quickActionButtons = document.querySelectorAll('.card-body .btn');
    quickActionButtons.forEach(button => {
        button.addEventListener('click', function() {
            const buttonText = this.textContent.trim();
            handleQuickAction(buttonText);
        });
    });
    
    // Stats cards click events
    const statCards = document.querySelectorAll('.stat-card');
    statCards.forEach(card => {
        card.addEventListener('click', function() {
            this.style.transform = 'scale(0.98)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
        });
    });
    
    // Table row click events
    const tableRows = document.querySelectorAll('tbody tr');
    tableRows.forEach(row => {
        row.addEventListener('click', function() {
            // Highlight selected row
            tableRows.forEach(r => r.classList.remove('table-active'));
            this.classList.add('table-active');
            
            // Show booking details (placeholder)
            const tool = this.cells[0].textContent;
            const customer = this.cells[1].textContent;
            showBookingDetails(tool, customer);
        });
    });
}

function handleQuickAction(action) {
    console.log(`Quick action: ${action}`);
    
    if (action.includes('Add New Tool')) {
        showAddToolModal();
    } else if (action.includes('View All Bookings')) {
        navigateToBookings();
    } else if (action.includes('View Earnings')) {
        navigateToEarnings();
    } else if (action.includes('Shop Settings')) {
        navigateToSettings();
    }
}

function showAddToolModal() {
    const modalHtml = `
        <div class="modal fade" id="addToolModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Add New Tool</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="addToolForm">
                            <div class="mb-3">
                                <label for="toolName" class="form-label">Tool Name</label>
                                <input type="text" class="form-control" id="toolName" required>
                            </div>
                            <div class="mb-3">
                                <label for="toolCategory" class="form-label">Category</label>
                                <select class="form-select" id="toolCategory" required>
                                    <option value="">Select Category</option>
                                    <option value="tractor">Tractor</option>
                                    <option value="harvester">Harvester</option>
                                    <option value="plough">Plough</option>
                                    <option value="seeder">Seeder</option>
                                </select>
                            </div>
                            <div class="mb-3">
                                <label for="dailyRate" class="form-label">Daily Rate (Rs)</label>
                                <input type="number" class="form-control" id="dailyRate" required>
                            </div>
                            <div class="mb-3">
                                <label for="toolDescription" class="form-label">Description</label>
                                <textarea class="form-control" id="toolDescription" rows="3"></textarea>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-success" onclick="submitNewTool()">Add Tool</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    const existingModal = document.getElementById('addToolModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    const modal = new bootstrap.Modal(document.getElementById('addToolModal'));
    modal.show();
}

function submitNewTool() {
    const form = document.getElementById('addToolForm');
    const formData = new FormData(form);
    
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    
    showNotification('Tool added successfully!', 'success');
    
    const modal = bootstrap.Modal.getInstance(document.getElementById('addToolModal'));
    modal.hide();
    
    updateToolCount();
}

function showBookingDetails(tool, customer) {
    showNotification(`Viewing details for ${tool} booked by ${customer}`, 'info');
}

function navigateToBookings() {
    const bookingsLink = document.querySelector('[data-section="bookings"]');
    if (bookingsLink) {
        bookingsLink.click();
    }
}

function navigateToEarnings() {
    const earningsLink = document.querySelector('[data-section="earnings"]');
    if (earningsLink) {
        earningsLink.click();
    }
}

function navigateToSettings() {
    const settingsLink = document.querySelector('[data-section="settings"]');
    if (settingsLink) {
        settingsLink.click();
    }
}

function showLoading() {
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.classList.add('loading');
    }
}

function hideLoading() {
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.classList.remove('loading');
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 80px; right: 20px; z-index: 1050; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

function updateToolCount() {
    const toolCountElement = document.querySelector('.stat-card-blue .stat-number');
    if (toolCountElement) {
        const currentCount = parseInt(toolCountElement.textContent);
        toolCountElement.textContent = currentCount + 1;
        
        toolCountElement.style.transform = 'scale(1.2)';
        setTimeout(() => {
            toolCountElement.style.transform = '';
        }, 300);
    }
}

function loadDashboardData() {
    console.log('Loading dashboard data...');
    // Example: Fetch real data here if needed
    // fetch('/api/dashboard-stats')
    //     .then(response => response.json())
    //     .then(data => updateDashboardStats(data));
}

function updateDashboardStats(data) {
    if (data.totalTools) {
        document.querySelector('.stat-card-blue .stat-number').textContent = data.totalTools;
    }
    if (data.activeBookings) {
        document.querySelector('.stat-card-green .stat-number').textContent = data.activeBookings;
    }
    if (data.monthlyEarnings) {
        document.querySelector('.stat-card-yellow .stat-number').textContent = `Rs ${data.monthlyEarnings.toLocaleString()}`;
    }
    if (data.avgRating) {
        document.querySelector('.stat-card-cyan .stat-number').textContent = data.avgRating;
    }
}

// Placeholder functions for different sections
function showDashboard() {
    console.log('Showing Dashboard');
}

function showMyTools() {
    console.log('Showing My Tools');
}

function showAddTool() {
    showAddToolModal();
}

function showBookings() {
    console.log('Showing Bookings');
}

function showEarnings() {
    console.log('Showing Earnings');
}

function showReviews() {
    console.log('Showing Reviews');
}

function showSettings() {
    console.log('Showing Settings');
}

function showAnalytics() {
    console.log('Showing Analytics');
}

function formatCurrency(amount) {
    return `Rs ${amount.toLocaleString()}`;
}

function formatDate(date) {
    return new Date(date).toLocaleDateString('en-IN');
}

// Export functions for external use
window.KishanHub = {
    showNotification,
    updateToolCount,
    loadDashboardData,
    formatCurrency,
    formatDate
};
