function toggleStatus(violationId, btnElement) {
    const originalText = btnElement.innerHTML;
    btnElement.disabled = true;
    btnElement.innerHTML = "Updating... <i class='fas fa-spinner fa-spin ms-1'></i>";

    // Grab the CSRF token from a meta tag or cookie. We will assume we added a meta tag in base.html
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    fetch(`/violations/update/${violationId}/`, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrfToken
        }
    })
    .then(response => response.json())
    .then(data => {
        btnElement.disabled = false;
        btnElement.innerHTML = "Advance Status <i class='fas fa-arrow-right ms-1'></i>";
        
        if (data.status) {
            const badge = document.getElementById(`badge-${violationId}`);
            if (badge) {
                badge.textContent = data.status;
                let bgClass = 'bg-info';
                if (data.status === 'Pending') bgClass = 'bg-danger';
                else if (data.status === 'Resolved') bgClass = 'bg-success';
                else if (data.status === 'Under Review') bgClass = 'bg-warning text-dark';
                
                badge.className = `badge fs-6 fw-bold text-white ${bgClass}`;
            }
        } else if (data.error) {
            alert("Error: " + data.error);
        }
    })
    .catch(error => {
        btnElement.disabled = false;
        btnElement.innerHTML = originalText;
        console.error('Error toggling status:', error);
        alert('Failed to update status due to network error.');
    });
}
