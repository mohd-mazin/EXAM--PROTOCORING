document.addEventListener("DOMContentLoaded", function() {
    const liveWarningEl = document.getElementById('liveWarning');
    const headDirectionEl = document.getElementById('headDirection');
    const warningBadgeEl = document.getElementById('warningBadge');

    function updateStatus() {
        fetch('/status')
            .then(response => response.json())
            .then(data => {
                const w = data.live_warning;
                if (liveWarningEl) liveWarningEl.innerText = w;
                if (headDirectionEl) headDirectionEl.innerText = data.head_direction;
                
                if (warningBadgeEl) {
                    if(w !== "Safe") {
                        warningBadgeEl.classList.remove('status-safe');
                        warningBadgeEl.classList.add('status-warning');
                    } else {
                        warningBadgeEl.classList.remove('status-warning');
                        warningBadgeEl.classList.add('status-safe');
                    }
                }
                
                const activePersonsEl = document.getElementById('activePersons');
                if (activePersonsEl) activePersonsEl.innerText = data.active_persons !== undefined ? data.active_persons : 0;
                
                const activePhonesEl = document.getElementById('activePhones');
                if (activePhonesEl) activePhonesEl.innerText = data.active_phones !== undefined ? data.active_phones : 0;
                
                // Update stats
                const faceCount = document.getElementById('face-count');
                if (faceCount) faceCount.innerText = data.face_absent;

                const phoneCount = document.getElementById('phone-count');
                if (phoneCount) phoneCount.innerText = data.phone;

                const mpCount = document.getElementById('mp-count');
                if (mpCount) mpCount.innerText = data.multiple_persons;

                const riskScoreEl = document.getElementById('risk-score');
                if (riskScoreEl) riskScoreEl.innerText = data.risk_percentage + "%";
                
                const lookCount = document.getElementById('look-count');
                if (lookCount) lookCount.innerText = data.look_away;
                
                const tabCount = document.getElementById('tab-count');
                if (tabCount) tabCount.innerText = data.tab_switch;
                
                const fsCount = document.getElementById('fs-count');
                if (fsCount) fsCount.innerText = data.fullscreen;
                
                const keyCount = document.getElementById('key-count');
                if (keyCount) keyCount.innerText = data.restricted_key;
                
                const voiceCount = document.getElementById('voice-count');
                if (voiceCount) voiceCount.innerText = data.voice;

                const extAudioCount = document.getElementById('ext-audio-count');
                if (extAudioCount) extAudioCount.innerText = data.external_audio !== undefined ? data.external_audio : 0;
                
                // Update voice status & audio level from backend monitor
                const audioLvlSpan = document.getElementById('audioLevelSpan');
                if (audioLvlSpan) {
                    audioLvlSpan.innerText = (data.audio_level !== undefined ? data.audio_level.toFixed(4) : "0.0000");
                }
                
                // There might be multiple voiceStatus elements on the page, update all
                const statusElems = document.querySelectorAll('#voiceStatus');
                statusElems.forEach(el => el.innerText = data.audio_status);
            });
            
        fetch('/api/timeline')
            .then(res => res.json())
            .then(timeline => {
                const timelineContainer = document.getElementById('timeline-container');
                if (timelineContainer) {
                    timelineContainer.innerHTML = '';
                    timeline.forEach(item => {
                        const div = document.createElement('div');
                        div.className = 'timeline-item';
                        div.innerText = `${item.timestamp} - ${item.type}`;
                        timelineContainer.appendChild(div);
                    });
                }
            });
    }

    setInterval(updateStatus, 1000);
    
    function logFrontendViolation(type) {
        fetch('/log_frontend_violation', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ type: type })
        });
    }

    document.addEventListener("visibilitychange", () => {
        if (document.hidden) logFrontendViolation("Tab Switch Detected");
    });

    document.addEventListener("fullscreenchange", () => {
        if (!document.fullscreenElement) logFrontendViolation("Fullscreen Exited");
    });

    document.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        logFrontendViolation("Right Click Attempt");
    });

    document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey && ['c', 'v', 'x', 'a', 'p', 's'].includes(e.key.toLowerCase())) || e.key === "PrintScreen") {
            e.preventDefault();
            logFrontendViolation("Restricted Key Attempt");
        }
    });

    window.addEventListener("resize", () => {
        if (window.outerWidth - window.innerWidth > 100 || window.outerHeight - window.innerHeight > 100) {
            logFrontendViolation("Browser Manipulation Detected");
        }
    });

    const startExamBtn = document.getElementById('start-exam-btn');
    if (startExamBtn) {
        startExamBtn.addEventListener('click', () => {
            const overlay = document.getElementById('start-overlay');
            if (overlay) {
                overlay.style.display = 'none';
            }
            
            document.documentElement.requestFullscreen().catch(err => {
                console.log(`Error attempting to enable fullscreen: ${err.message}`);
            });
        });
    }

    const endExamBtn = document.getElementById('end-exam-btn');
    if (endExamBtn) {
        endExamBtn.addEventListener('click', () => {
            endExamBtn.disabled = true;
            document.getElementById('loading-spinner').style.display = 'block';
            
            // Log end exam telemetry
            fetch('/end_exam', { method: 'POST' }).then(() => {
                // Generate AI report
                fetch('/generate_ai_report', { method: 'POST' })
                    .then(res => res.json())
                    .then(() => {
                        window.location.href = '/report';
                    });
            });
        });
    }

    // Backend Audio Monitoring replaces the frontend MediaRecorder
    // The server natively runs sounddevice to process microphone.
});
