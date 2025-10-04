import pyaudio
import wave

CHUNK = 2048
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 48000

# Candidate SlimFit indices you listed
CANDIDATE_DEVICES = [1, 9, 21, 32]

def test_device(idx, seconds=3):
    print(f"\n[TEST] Trying device index {idx}...")
    p = pyaudio.PyAudio()
    try:
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        input_device_index=idx,
                        frames_per_buffer=CHUNK)
    except Exception as e:
        print(f"[TEST] ❌ Could not open device {idx}: {e}")
        return

    frames = []
    try:
        for _ in range(0, int(RATE / CHUNK * seconds)):
            data = stream.read(CHUNK)
            frames.append(data)
    except Exception as e:
        print(f"[TEST] ❌ Error during recording: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

    filename = f"mic_test_idx{idx}.wav"
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

    print(f"[TEST] ✅ Saved recording for device {idx} to '{filename}'")

if __name__ == "__main__":
    for dev in CANDIDATE_DEVICES:
        test_device(dev)
