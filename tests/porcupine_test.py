import pvporcupine
import pyaudio
import numpy as np

ACCESS_KEY = "6JAh0fQzeyIShI1QwlHtilRIqow5QVa63syT3MPVHkN3Q4IgZ0uPIA=="  # 👈 paste it here

# Initialize Porcupine wake word detector
porcupine = pvporcupine.create(
    access_key=ACCESS_KEY,
    keywords=["porcupine"]  # You can switch this to "computer", "jarvis", etc. too
)

pa = pyaudio.PyAudio()

stream = pa.open(
    rate=porcupine.sample_rate,
    channels=1,
    format=pyaudio.paInt16,
    input=True,
    frames_per_buffer=porcupine.frame_length
)

print("[WakeWord] 🐗 Porcupine is listening... Say 'Porcupine' to trigger.")

try:
    while True:
        pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
        pcm_int16 = np.frombuffer(pcm, dtype=np.int16)
        keyword_index = porcupine.process(pcm_int16)
        if keyword_index >= 0:
            print("[WakeWord] ✅ Detected wake word!")
            break

except KeyboardInterrupt:
    print("\n[WakeWord] Exiting.")

finally:
    stream.stop_stream()
    stream.close()
    pa.terminate()
    porcupine.delete()
