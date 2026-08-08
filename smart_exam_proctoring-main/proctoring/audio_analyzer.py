import librosa
import numpy as np
import sounddevice as sd
import threading
import time

# Global states for real-time monitoring
global_audio_level = 0.0
global_audio_status = "Silence"
global_mic_error = None
is_monitoring = False

def analyze_audio_chunk(filepath):
    """
    Analyzes a 10-second audio chunk.
    Returns: 'Silence', 'Single Voice', or 'Multiple Voices'
    Uses a local heuristic based on RMS energy and Pitch/Spectral variation.
    """
    try:
        y, sr = librosa.load(filepath, sr=16000)
        
        # Calculate RMS energy for silence detection
        rms = librosa.feature.rms(y=y)[0]
        mean_rms = np.mean(rms)
        
        if mean_rms < 0.01:
            return "Silence"
            
        # Calculate fundamental frequency (pitch) to identify active speakers
        f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
        valid_f0 = f0[~np.isnan(f0)]
        
        if len(valid_f0) < 5:
            return "Silence" # Just non-vocal background noise
            
        std_pitch = np.std(valid_f0)
        
        # Spectral contrast variance helps identify overlapping/competing sounds
        contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
        contrast_var = np.var(contrast)
        
        # Heuristic thresholds for detecting multiple speakers vs single speaker
        if std_pitch > 65 and contrast_var > 12:
            return "Multiple Voices"
            
        # Add broad spectral bandwidth detection for music/external audio
        spec_bw = librosa.feature.spectral_bandwidth(y=y, sr=sr)
        mean_bw = np.mean(spec_bw)
        
        # Typical human speech bandwidth is lower. Broad bandwidth often indicates music, noise, or full-spectrum media.
        if mean_bw > 2500:
            return "External Audio Detected"
            
        return "Single Voice"
        
    except Exception as e:
        print(f"Audio Analysis Error: {e}")
        return "Silence"

def audio_callback(indata, frames, time_info, status):
    global global_audio_level, global_audio_status
    if status:
        pass # Handle status if needed

    # Calculate RMS volume of the current chunk
    rms = np.sqrt(np.mean(indata**2))
    global_audio_level = float(rms)
    
    # Update status based on threshold
    if global_audio_level > 0.05:
        global_audio_status = "Audio Detected"
    else:
        global_audio_status = "Silence"

def start_audio_monitoring():
    global is_monitoring, global_mic_error
    if is_monitoring: return
    
    def monitor_thread():
        global is_monitoring, global_mic_error
        try:
            print("Microphone initialized")
            with sd.InputStream(callback=audio_callback, channels=1, samplerate=16000):
                print("Audio stream active")
                is_monitoring = True
                while is_monitoring:
                    # Optional: periodically print RMS to console
                    # print(f"Live RMS: {global_audio_level:.4f}")
                    time.sleep(1)
        except Exception as e:
            global_mic_error = f"Mic Initialization Failed: {e}"
            print(global_mic_error)
            is_monitoring = False

    t = threading.Thread(target=monitor_thread, daemon=True)
    t.start()
    
def stop_audio_monitoring():
    global is_monitoring
    is_monitoring = False
