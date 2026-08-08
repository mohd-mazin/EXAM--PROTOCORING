document.addEventListener("DOMContentLoaded", () => {
    // Navigation Logic
    const links = document.querySelectorAll('.sidebar-link[data-target]');
    const sections = document.querySelectorAll('.view-section');

    links.forEach(link => {
        link.addEventListener('click', () => {
            links.forEach(l => l.classList.remove('active'));
            sections.forEach(s => s.classList.remove('active'));
            
            link.classList.add('active');
            const target = link.getAttribute('data-target');
            document.getElementById(target).classList.add('active');
            
            // Fetch data based on active section
            loadData(target);
        });
    });

    // API Data Loaders
    function loadData(section) {
        if (section === 'dashboard') fetchDashboard();
        else if (section === 'students') fetchStudents();
        else if (section === 'violations') fetchViolations();
        else if (section === 'analytics') fetchAnalytics();
        else if (section === 'evidence') fetchEvidence();
        else if (section === 'live') fetchLive();
    }

    function fetchDashboard() {
        fetch('/api/admin/dashboard')
            .then(res => res.json())
            .then(data => {
                document.getElementById('dash-students').innerText = data.total_students;
                document.getElementById('dash-sessions').innerText = data.total_sessions;
                document.getElementById('dash-completed').innerText = data.completed_exams;
                document.getElementById('dash-risk').innerText = data.average_risk_score;
                document.getElementById('dash-violations').innerText = data.total_violations;
            });
    }

    function fetchStudents() {
        fetch('/api/admin/students')
            .then(res => res.json())
            .then(data => {
                const tbody = document.querySelector('#students-table tbody');
                tbody.innerHTML = '';
                data.forEach(s => {
                    tbody.innerHTML += `
                        <tr>
                            <td>${s.student_name}</td>
                            <td>${s.usn}</td>
                            <td>${s.user_id}</td>
                            <td><span style="color:var(--success-color); font-weight:bold;">${s.exam_status}</span></td>
                            <td>${s.risk_score}</td>
                            <td>${s.classification}</td>
                            <td>
                                <a href="#" style="color:var(--primary-color);">View</a>
                            </td>
                        </tr>
                    `;
                });
            });
    }

    function fetchViolations() {
        fetch('/api/admin/violations')
            .then(res => res.json())
            .then(data => {
                const tbody = document.querySelector('#violations-table tbody');
                tbody.innerHTML = '';
                data.forEach(v => {
                    tbody.innerHTML += `
                        <tr>
                            <td>${v.timestamp}</td>
                            <td>${v.session_id || 'N/A'}</td>
                            <td><strong>${v.violation_type}</strong></td>
                            <td>${v.details || '-'}</td>
                        </tr>
                    `;
                });
            });
    }

    let violationsChartInstance = null;
    let riskChartInstance = null;

    function fetchAnalytics() {
        fetch('/api/admin/analytics')
            .then(res => res.json())
            .then(data => {
                const vCtx = document.getElementById('violationsChart').getContext('2d');
                if (violationsChartInstance) violationsChartInstance.destroy();
                violationsChartInstance = new Chart(vCtx, {
                    type: 'bar',
                    data: {
                        labels: Object.keys(data.violation_types),
                        datasets: [{
                            label: 'Violation Count',
                            data: Object.values(data.violation_types),
                            backgroundColor: '#4A90E2',
                            borderRadius: 6
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: false }
                });

                const rCtx = document.getElementById('riskChart').getContext('2d');
                if (riskChartInstance) riskChartInstance.destroy();
                riskChartInstance = new Chart(rCtx, {
                    type: 'doughnut',
                    data: {
                        labels: Object.keys(data.risk_distribution),
                        datasets: [{
                            data: Object.values(data.risk_distribution),
                            backgroundColor: ['#2ecc71', '#f39c12', '#e74c3c']
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: false }
                });
            });
    }

    function fetchEvidence() {
        console.log("fetchEvidence() called");
        fetch(`/api/admin/evidence?t=${Date.now()}`)
            .then(res => res.json())
            .then(data => {
                console.log("Evidence count received:", data.length);
                console.log("Rendering evidence IDs:", data.map(x => x.id));
                const grid = document.getElementById('evidence-grid');
                grid.innerHTML = '';
                data.forEach(e => {
                    const ext = e.evidence_path.split('.').pop().toLowerCase();
                    let content = '';
                    if (['jpg', 'png', 'jpeg'].includes(ext)) {
                        content = `<img src="/${e.evidence_path.replace('\\', '/')}" style="width:100%; border-radius:8px;">`;
                    } else if (['webm', 'mp4'].includes(ext)) {
                        content = `<video src="/${e.evidence_path.replace('\\', '/')}" style="width:100%; border-radius:8px;" controls></video>`;
                    } else if (['wav', 'mp3'].includes(ext)) {
                        content = `<audio src="/${e.evidence_path.replace('\\', '/')}" style="width:100%; margin-top:10px;" controls></audio>`;
                    } else {
                        content = `<p>File: ${e.evidence_path}</p>`;
                    }
                    
                    grid.innerHTML += `
                        <div class="stat-card" id="evidence-${e.id}" style="background:var(--card-bg)!important;">
                            <p style="font-size:0.85rem; color:#888; margin-bottom:0.5rem;">${e.timestamp}</p>
                            <h4 style="margin-top:0;">${e.violation_type}</h4>
                            ${content}
                            <div style="margin-top: 10px; display: flex; gap: 10px;">
                                <a href="/${e.evidence_path.replace('\\', '/')}" target="_blank" class="btn" style="flex:1; text-align:center; background-color:#34495e; text-decoration:none; padding:5px; font-size:0.9rem;">View</a>
                                <button class="btn" onclick="promptDeleteEvidence(${e.id})" style="flex:1; background-color:var(--danger-color); padding:5px; font-size:0.9rem;">Delete</button>
                            </div>
                        </div>
                    `;
                });

                // No event listener bindings needed here since we use onclick now
            });
    }

    function fetchLive() {
        fetch('/api/admin/live')
            .then(res => res.json())
            .then(data => {
                const tbody = document.querySelector('#live-table tbody');
                tbody.innerHTML = '';
                data.forEach(s => {
                    tbody.innerHTML += `
                        <tr>
                            <td>${s.student_name}</td>
                            <td>${s.usn}</td>
                            <td><strong style="color:var(--danger-color);">${s.current_risk}</strong></td>
                            <td>${s.current_warning}</td>
                        </tr>
                    `;
                });
            });
    }

    // Clear Evidence Logic
    const clearBtn = document.getElementById('clear-evidence-btn');
    const modal = document.getElementById('clear-modal');
    const cancelBtn = document.getElementById('cancel-clear-btn');
    const confirmBtn = document.getElementById('confirm-clear-btn');
    const spinner = document.getElementById('clear-spinner');

    if (clearBtn && modal) {
        clearBtn.addEventListener('click', () => {
            const grid = document.getElementById('evidence-grid');
            if (!grid || grid.children.length === 0) {
                alert("No evidence available to clear.");
                return;
            }
            modal.style.display = 'flex';
        });

        cancelBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        confirmBtn.addEventListener('click', () => {
            confirmBtn.style.display = 'none';
            cancelBtn.style.display = 'none';
            spinner.style.display = 'block';

            fetch('/api/admin/evidence/clear', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    modal.style.display = 'none';
                    confirmBtn.style.display = 'inline-block';
                    cancelBtn.style.display = 'inline-block';
                    spinner.style.display = 'none';
                    
                    if (data.success || data.error === "Unauthorized") {
                        if (data.error) {
                            alert("Unauthorized: Admin access required.");
                        } else {
                            alert("Evidence data cleared successfully.");
                            fetchEvidence();
                        }
                    } else {
                        alert("Error clearing evidence.");
                    }
                })
                .catch(err => {
                    modal.style.display = 'none';
                    confirmBtn.style.display = 'inline-block';
                    cancelBtn.style.display = 'inline-block';
                    spinner.style.display = 'none';
                    alert("Error clearing evidence.");
                });
        });
    }

    // Individual Delete Logic Modal UI
    const singleModal = document.getElementById('delete-single-modal');
    const cancelSingleBtn = document.getElementById('cancel-single-delete-btn');
    const confirmSingleBtn = document.getElementById('confirm-single-delete-btn');
    const singleSpinner = document.getElementById('single-delete-spinner');

    window.promptDeleteEvidence = function(id) {
        window.currentDeleteId = id;
        if (singleModal) {
            singleModal.style.display = 'flex';
        } else {
            // Fallback if modal is missing
            if (confirm("Are you sure you want to delete this evidence?")) {
                deleteEvidence(id);
            }
        }
    };

    if (singleModal) {
        cancelSingleBtn.addEventListener('click', () => {
            singleModal.style.display = 'none';
        });

        confirmSingleBtn.addEventListener('click', () => {
            if (!window.currentDeleteId) return;
            
            confirmSingleBtn.style.display = 'none';
            cancelSingleBtn.style.display = 'none';
            singleSpinner.style.display = 'block';

            deleteEvidence(window.currentDeleteId).then(() => {
                singleModal.style.display = 'none';
                confirmSingleBtn.style.display = 'inline-block';
                cancelSingleBtn.style.display = 'inline-block';
                singleSpinner.style.display = 'none';
            });
        });
    }

    // COMPLETE deleteEvidence() FUNCTION AS REQUESTED
    window.deleteEvidence = function(id) {
        console.log("DELETE CLICKED", id);
        
        return fetch(`/delete_evidence/${id}`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                console.log("SERVER RESPONSE", data);
                if (data.success) {
                    console.log("Removing card:", id);
                    console.log(document.getElementById(`evidence-${id}`));
                    
                    fetchEvidence(); // Force reload evidence data as requested
                    
                    // The delay allows the modal to close smoothly before alert blocks thread
                    setTimeout(() => alert("Evidence deleted successfully"), 100);
                } else {
                    alert(data.message || data.error || "Error deleting evidence.");
                }
            })
            .catch(err => {
                console.error("Delete error:", err);
                alert("Error deleting evidence.");
            });
    };

    // Initial load
    loadData('dashboard');
});
