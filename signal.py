import numpy as np
from scipy.io.wavfile import write
import sounddevice as sd

duration = 2.0
sample_rate = 44100

t = np.linspace(0, duration, int(sample_rate * duration), False)

# Lower base frequency for more bass
f = 220 * 1.25 # lowered from 500 → deeper, fuller
f2 = f * 2.03  # slightly detuned harmonic
# f3 = f * 3.05  # another harmonic

# Raw horn tone with harmonics
wave = ( 0.8 * np.sin(2 * np.pi * f * t + 0) 
        + 0.5 * np.sin(2 * np.pi * f2 * t + 0)
#  + 0.3 * np.sin(2 * np.pi * f3 * t + 0)
)

# --- Envelope (Attack, Sustain, Release) ---
attack_time = 0.07   # 70 ms
release_time = 0.45 # 450 ms (longer, natural fade)

attack_samples = int(attack_time * sample_rate)
release_samples = int(release_time * sample_rate)
sustain_samples = len(t) - attack_samples - release_samples

attack_env = np.linspace(0, 1, attack_samples)
sustain_env = np.ones(sustain_samples)
release_env = np.linspace(1, 0, release_samples) ** 2

envelope = np.concatenate([attack_env, sustain_env, release_env])

# Apply envelope
wave = wave * envelope

# Distortion for air-horn rasp
wave = np.tanh(2.3 * wave)

# Normalize
audio = np.int16(wave / np.max(np.abs(wave)) * 32767)

# Play
sd.play(audio, sample_rate)
sd.wait()

# Save
write("air_horn.wav", sample_rate, audio)
print("Saved as air_horn.wav")
