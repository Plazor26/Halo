# voice/wakeword.py
import pvporcupine
import pyaudio
import numpy as np

class WakeWordDetector:
    def __init__(self, access_key: str, keyword: str = "porcupine", keyword_path: str = None):
        """
        Initialize Porcupine wake word detector.
        If keyword_path is provided, use custom .ppn file. Otherwise use built-in keywords.
        """
        if keyword_path:
            self.porcupine = pvporcupine.create(
                access_key=access_key,
                keyword_paths=[keyword_path]
            )
        else:
            self.porcupine = pvporcupine.create(
                access_key=access_key,
                keywords=[keyword]
            )

        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(
            rate=self.porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self.porcupine.frame_length
        )

    def listen_for_wake_word(self):
        """Continuously listens for the wake word and returns when detected."""
        print("[WakeWord] 👂 Halo is listening...")
        while True:
            pcm = self.stream.read(self.porcupine.frame_length, exception_on_overflow=False)
            pcm_int16 = np.frombuffer(pcm, dtype=np.int16)
            keyword_index = self.porcupine.process(pcm_int16)
            if keyword_index >= 0:
                print("[WakeWord] ✅ Wake word detected")
                return True

    def close(self):
        """Gracefully close the audio stream and Porcupine engine."""
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()
        self.porcupine.delete()
