import array
import sounddevice


def apply_gain(pcm: bytes, gain: float) -> bytes:
    if gain >= 1:
        return pcm
    if gain <= 0:
        return bytes(len(pcm))
    samples = array.array("h")
    samples.frombytes(pcm)
    return array.array("h", [int(sample * gain) for sample in samples]).tobytes()


class AudioOutput:
    def __init__(self) -> None:
        self.sample_rate: int | None = None
        self._stream: sounddevice.RawOutputStream | None = None
        try:
            device = sounddevice.query_devices(kind="output")
            sample_rate = int(device["default_samplerate"])
            stream = sounddevice.RawOutputStream(samplerate=sample_rate, channels=2, dtype="int16")
            stream.start()
        except Exception as error:
            print(f"Audio disabled: {error}")
            return
        self.sample_rate = sample_rate
        self._stream = stream

    @property
    def available(self) -> bool:
        return self._stream is not None

    def attach(self, emulator) -> None:
        if self.sample_rate is not None:
            emulator.set_audio_rate(self.sample_rate)

    def play(self, pcm: bytes, gain: float) -> None:
        if self._stream is None:
            return
        try:
            self._stream.write(apply_gain(pcm, gain))
        except sounddevice.PortAudioError as error:
            print(f"Audio stopped: {error}")
            self._stream = None

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
