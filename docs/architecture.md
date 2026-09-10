
# ovos-simple-listener: Architecture Reference

## Overview

`ovos-simple-listener` is implemented as a single `threading.Thread` subclass (`SimpleListener`) that runs a continuous audio pipeline loop. The entire pipeline is approximately 150 lines of Python in `ovos_simple_listener/__init__.py`, making it a useful reference for understanding how OVOS audio plugins fit together.

## Module Structure

```
ovos_simple_listener/
├── __init__.py       # SimpleListener, ListenerCallbacks, State
├── __main__.py       # OVOSCallbacks, main(): OVOS messagebus integration
└── version.py        # __version__
```

## Pipeline Stages

### Stage 1: Audio Capture (Microphone Plugin)

**Interface**: `ovos_plugin_manager.templates.microphone.Microphone`
**Factory**: `ovos_plugin_manager.microphone.OVOSMicrophoneFactory`

The microphone plugin provides raw audio in chunks. The pipeline reads one chunk per loop iteration via `mic.read_chunk()`.

Key microphone properties used by the listener:
- `mic.sample_rate`: samples per second (e.g. 16000 Hz), used to calculate chunk duration.
- `mic.chunk_size`: number of samples per chunk, used to calculate chunk duration.
- `mic.sample_width`: bytes per sample, passed to `sr.AudioData` for STT.
- `mic.start()`: called once at the start of `SimpleListener.run()`.

**Chunk duration calculation**:
```python
chunk_duration = mic.chunk_size / mic.sample_rate  # seconds per chunk
```

This is used to track cumulative VAD time in `WAITING_WAKEWORD` mode when no wake word engine is configured.

### Stage 2: Wake Word Detection (HotWord Plugin)

**Interface**: `ovos_plugin_manager.templates.hotwords.HotWordEngine`
**Factory**: `ovos_plugin_manager.wakewords.OVOSWakeWordFactory`

Wake word detection only runs in `WAITING_WAKEWORD` state.

Two activation modes:

**Mode A: with wake word engine** (`wakeword is not None`):
```python
self.wakeword.update(chunk)       # feed audio chunk to the engine
ww = self.wakeword.found_wake_word()  # returns True if wake word detected
```

**Mode B: VAD-only** (`wakeword is None`):
```python
if self.vad.is_silence(chunk):
    vad_seconds = 0
else:
    vad_seconds += chunk_duration
ww = vad_seconds >= 0.5  # activates after 0.5 continuous seconds of speech
```

When `ww` becomes `True`, the listener transitions to `IN_COMMAND`.

### Stage 3: Voice Activity Detection (VAD Plugin)

**Interface**: `ovos_plugin_manager.templates.vad.VADEngine`
**Factory**: `ovos_plugin_manager.vad.OVOSVADFactory`

VAD is used in two roles:

1. **Wake trigger** (when no wake word engine): 0.5 continuous seconds of non-silence activates the listener.
2. **Utterance end detection** (in `IN_COMMAND`): the listener tracks silence duration after speech begins.

```python
if self.vad.is_silence(chunk):
    sil_start = sil_start or time.time()   # record when silence started
else:
    sil_start = total_silence_duration = 0  # reset on speech
```

The utterance is considered complete when:
```python
timed_out = (
    total_silence_duration >= self.max_silence_seconds
    and self.min_speech_seconds <= total_speech_duration
) or total_speech_duration >= self.max_speech_seconds
```

Parameters with defaults:
- `max_silence_seconds = 1.5`
- `min_speech_seconds = 1`
- `max_speech_seconds = 8`

### Stage 4: Audio Buffering

During `IN_COMMAND`, every chunk from the microphone is appended to `speech_data` regardless of whether it is speech or silence:

```python
speech_data += chunk
```

This captures the complete utterance including any natural pauses within speech.

### Stage 5: STT Transcription (STT Plugin)

**Interface**: `ovos_plugin_manager.templates.stt.STT`
**Factory**: `ovos_plugin_manager.stt.OVOSSTTFactory`

When the utterance is complete:

1. The buffered bytes are wrapped in `speech_recognition.AudioData`:
   ```python
   audio = sr.AudioData(speech_data, self.mic.sample_rate, self.mic.sample_width)
   ```

2. The STT plugin transcribes it:
   ```python
   tx = self.stt.transcribe(audio)
   ```
   `transcribe()` returns a list of hypothesis tuples. The listener reads `tx[0][0]` for the top hypothesis.

3. If the hypothesis is non-empty, leading/trailing quotes and whitespace are stripped:
   ```python
   utt = tx[0][0].rstrip(" '\"").lstrip(" '\"")
   ```

4. The result is dispatched via callbacks:
   - Non-empty: `callbacks.text_callback(utt, self.lang)`
   - Empty: `callbacks.error_callback(audio)`

The `lang` property delegates to the STT plugin's configured language:
```python
@property
def lang(self) -> str:
    return self.stt.lang
```

### Stage 6: Callback Dispatch

`ListenerCallbacks` is a plain class with five classmethod hooks. All five are called with `try/except` guards, so a callback exception does not crash the listener loop.

```python
class ListenerCallbacks:
    @classmethod
    def listen_callback(cls): ...          # wake word triggered
    @classmethod
    def end_listen_callback(cls): ...      # utterance processed, back to idle
    @classmethod
    def audio_callback(cls, audio): ...    # raw audio ready
    @classmethod
    def error_callback(cls, audio): ...    # STT returned nothing
    @classmethod
    def text_callback(cls, utterance, lang): ...  # text recognized
```

## OVOS Messagebus Integration

`__main__.py` extends the callback system to emit OVOS bus messages, making the listener a drop-in for `ovos-dinkum-listener`:

```python
class OVOSCallbacks(ListenerCallbacks):
    bus = None

    def __init__(self, bus=None):
        OVOSCallbacks.bus = bus or get_mycroft_bus()
```

The `get_mycroft_bus()` function connects to the running OVOS messagebus using the standard connection parameters from `ovos-config`.

### Bus Messages

- Wake word detected: sends `recognizer_loop:wakeword` with no payload.
- Recording starts: sends `recognizer_loop:record_begin` with no payload.
- Play listen sound: sends `mycroft.audio.play_sound` with payload `{"uri": "smd/start_listening.wav"}`.
- Recording ends: sends `recognizer_loop:record_end` with no payload.

- STT success: sends `recognizer_loop:utterance` with payload `{"utterances": [text], "lang": lang}`.
- STT failure: sends `recognizer_loop:speech.recognition.unknown` with no payload.

The `recognizer_loop:utterance` message is the primary output. `ovos-core` listens for this message to route the utterance to the correct skill through the intent pipeline.

## Thread Model

`SimpleListener` runs as a **daemon thread**. The `run()` loop does this:
- Calls `self.mic.start()` once.
- Loops continuously, reading chunks and processing state.
- Breaks on `KeyboardInterrupt`.

- Sets `self.running = False` on exit.
- Can be stopped from outside by calling `listener.stop()`, which sets `self.running = False`.

Because it is a daemon thread, it will be killed automatically when the main thread exits. In the OVOS `main()` entrypoint, `t.run()` is called directly (blocking), not `t.start()`.

## State Transitions

```
State.WAITING_WAKEWORD (0)
    Variables reset on entry:
        vad_seconds = 0
        speech_data = b""

    Each chunk:
        if wakeword:
            wakeword.update(chunk)
            if wakeword.found_wake_word():
                → transition to IN_COMMAND
        else:
            if not vad.is_silence(chunk):
                vad_seconds += chunk_duration
            else:
                vad_seconds = 0
            if vad_seconds >= 0.5:
                → transition to IN_COMMAND

State.IN_COMMAND (2)
    Variables reset on entry:
        sil_start = 0
        total_silence_duration = 0.0
        start = time.time()

    Each chunk:
        speech_data += chunk
        if vad.is_silence(chunk): track sil_start
        else: reset silence tracking

        if timed_out:
            audio = sr.AudioData(speech_data, ...)
            callbacks.audio_callback(audio)
            tx = stt.transcribe(audio)
            if tx[0][0]: callbacks.text_callback(...)
            else: callbacks.error_callback(...)
            speech_data = b""
            → transition to WAITING_WAKEWORD
```

## Dependency Graph

```
SimpleListener
    ├── Microphone (OVOSMicrophoneFactory)
    │       configured by: mycroft.conf listener.microphone_module
    ├── VADEngine (OVOSVADFactory)
    │       configured by: mycroft.conf listener.VAD.module
    ├── HotWordEngine (OVOSWakeWordFactory)
    │       configured by: mycroft.conf listener.wake_word
    ├── STT (OVOSSTTFactory)
    │       configured by: mycroft.conf stt.module
    └── ListenerCallbacks
            └── OVOSCallbacks (for OVOS integration)
                    └── MessageBusClient (ovos-bus-client)
```

All plugin instances are created by their respective factory classes, which read plugin configuration from the OVOS config system (`ovos-config`).

## Cross-References

- [index.md](index.md): overview, usage, and when to use simple vs dinkum
- [ovos-plugin-manager](https://github.com/OpenVoiceOS/ovos-plugin-manager): plugin factories and base templates
- [ovos-config](https://github.com/OpenVoiceOS/ovos-config): configuration system
- [ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener): full-featured listener for comparison

---
[Home](index.md)
