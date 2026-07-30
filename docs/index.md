
# ovos-simple-listener: Lightweight Voice Listener

## What Is This?

`ovos-simple-listener` is a **minimal voice listener** for OpenVoiceOS. It implements the core microphone → wake word → STT pipeline in approximately 150 lines of Python, using the same plugin interfaces as `ovos-dinkum-listener`.

It was originally created to power [hivemind-listener](https://github.com/JarbasHiveMind/hivemind-listener) and [hivemind-mic-satellite](https://github.com/JarbasHiveMind/hivemind-mic-satellite), two HiveMind satellite devices that need a lightweight audio frontend. It can also be used as a drop-in replacement for `ovos-dinkum-listener` in standard OVOS setups.

## What Makes It "Simple"?

The key design difference from `ovos-dinkum-listener` is scope. The simple listener deliberately omits features that add complexity.

`ovos-simple-listener` supports wake word detection, VAD (voice activity detection), STT transcription, and messagebus integration (via `__main__.py`), the same as `ovos-dinkum-listener`.

`ovos-simple-listener` does not support these `ovos-dinkum-listener` features:

- Audio Transformer plugins
- Continuous Listening mode
- Hybrid Listening mode
- Recording Mode
- Sleep Mode
- Multiple wake words

`ovos-dinkum-listener` is the full-featured production listener. `ovos-simple-listener` is appropriate when the missing features above are not needed and minimal resource usage or code simplicity is a priority.

## Architecture

The listener is a `threading.Thread` subclass. The pipeline operates in a single read loop:

```
Microphone.read_chunk()
    │
    ├─ [WAITING_WAKEWORD state]
    │       ├─ wakeword is None? → use VAD (0.5s of speech activates)
    │       └─ wakeword set? → HotWordEngine.update(chunk) + found_wake_word()
    │
    └─ [IN_COMMAND state]
            accumulate speech_data bytes
            track silence duration (VAD.is_silence())
            track total duration
            │
            ├─ silence ≥ max_silence_seconds AND speech ≥ min_speech_seconds → done
            └─ total duration ≥ max_speech_seconds → done
                    │
                    ├─ build sr.AudioData from speech_data
                    ├─ callbacks.audio_callback(audio)
                    ├─ STT.transcribe(audio)
                    ├─ utterance found → callbacks.text_callback(utterance, lang)
                    └─ no utterance → callbacks.error_callback(audio)
                    return to WAITING_WAKEWORD
```

### State Machine

```
WAITING_WAKEWORD ──(wake word detected or VAD threshold crossed)──> IN_COMMAND
IN_COMMAND       ──(silence timeout or max duration reached)──────> WAITING_WAKEWORD
```

### Plugin Types Used

| Plugin Type | Factory | Interface |
|---|---|---|
| Microphone | `OVOSMicrophoneFactory` | `Microphone` |
| Voice Activity Detection | `OVOSVADFactory` | `VADEngine` |
| Hot Word / Wake Word | `OVOSWakeWordFactory` | `HotWordEngine` |
| Speech-to-Text | `OVOSSTTFactory` | `STT` |

All four come from `ovos-plugin-manager`. Plugin selection follows the standard OVOS configuration in `~/.config/mycroft/mycroft.conf`.

## Configuration Parameters

`SimpleListener.__init__()` accepts these timing parameters:

| Parameter | Default | Description |
|---|---|---|
| `max_silence_seconds` | 1.5 | Seconds of silence after which the utterance is considered complete (given `min_speech_seconds` has been reached) |
| `min_speech_seconds` | 1 | Minimum speech duration before silence timeout applies |
| `max_speech_seconds` | 8 | Hard limit on utterance duration regardless of silence |

When `wakeword=None`, the listener uses VAD alone: any 0.5 seconds of non-silence activates the `IN_COMMAND` state.

## Callback System

`ListenerCallbacks` defines five event hooks:

- `listen_callback()`: called when the wake word is detected or recording begins. Default behavior logs `IN_COMMAND`.
- `end_listen_callback()`: called after the utterance is processed and the listener returns to idle. Default behavior logs `WAITING_WAKEWORD`.
- `audio_callback(audio)`: called when audio recording is complete, before STT. Default behavior logs "Speech finished!"
- `error_callback(audio)`: called when STT returns empty or fails. Default behavior logs "STT Failure".
- `text_callback(utterance, lang)`: called when STT returns text. Default behavior logs the transcript.

The default callbacks only log. Subclass `ListenerCallbacks` to add custom behaviour.

## OVOS Integration (Messagebus)

`__main__.py` provides the `OVOSCallbacks` subclass and a `main()` function that wires the listener to the OVOS messagebus:

| Callback | Messages Emitted |
|---|---|
| `listen_callback` | `mycroft.audio.play_sound` (start sound), `recognizer_loop:wakeword`, `recognizer_loop:record_begin` |
| `end_listen_callback` | `recognizer_loop:record_end` |
| `error_callback` | `recognizer_loop:speech.recognition.unknown` |
| `text_callback` | `recognizer_loop:utterance` with `{"utterances": [text], "lang": lang}` |

This means `ovos-simple-listener` is compatible with `ovos-core`'s skill routing: recognized utterances are dispatched to skills the same way as when using `ovos-dinkum-listener`.

## Usage

### As an OVOS Service

```bash
pip install ovos-simple-listener
ovos-simple-listener
```

Plugin selection comes from `~/.config/mycroft/mycroft.conf` via `ovos-config`. The wake word name is read from `listener.wake_word` in the config (defaults to `"hey_mycroft"`).

### As a Python Library

```python
from ovos_simple_listener import SimpleListener
from ovos_plugin_manager.microphone import OVOSMicrophoneFactory
from ovos_plugin_manager.stt import OVOSSTTFactory
from ovos_plugin_manager.vad import OVOSVADFactory
from ovos_plugin_manager.wakewords import OVOSWakeWordFactory

listener = SimpleListener(
    mic=OVOSMicrophoneFactory.create(),
    vad=OVOSVADFactory.create(),
    wakeword=OVOSWakeWordFactory.create_hotword("hey_mycroft"),
    stt=OVOSSTTFactory.create()
)
listener.run()
```

### With Custom Callbacks

```python
from ovos_simple_listener import ListenerCallbacks, SimpleListener
import speech_recognition as sr

class MyCallbacks(ListenerCallbacks):
    @classmethod
    def listen_callback(cls):
        print("Listening...")

    @classmethod
    def text_callback(cls, utterance: str, lang: str):
        print(f"You said: {utterance} [{lang}]")

    @classmethod
    def error_callback(cls, audio: sr.AudioData):
        print("Could not understand")

listener = SimpleListener(callbacks=MyCallbacks())
listener.start()  # runs in background thread (daemon=True)
```

### VAD-only Mode (No Wake Word)

Pass `wakeword=None` to activate on any speech without a wake word:

```python
listener = SimpleListener(
    mic=OVOSMicrophoneFactory.create(),
    vad=OVOSVADFactory.create(),
    stt=OVOSSTTFactory.create(),
    wakeword=None  # activates after 0.5s of non-silence
)
```

## Installation

```bash
pip install ovos-simple-listener
```

**Dependencies** (from `pyproject.toml`):
- `ovos-plugin-manager>=2.1.1,<3.0.0`
- `ovos-utils>=0.0.38,<1.0.0`
- `ovos-config>=0.4.3,<3.0.0`
- `ovos_bus_client>=0.0.10,<2.0.0`
- `SpeechRecognition~=3.9`

## Entry Point

The package registers a console script:

```
ovos-simple-listener = ovos_simple_listener.__main__:main
```

## When to Use Simple vs Dinkum

Use `ovos-simple-listener` when:
- You are building a HiveMind satellite (`hivemind-listener`, `hivemind-mic-satellite`).
- You need minimal dependencies or minimal resource usage.
- You want a readable reference implementation of the OVOS audio plugin pipeline.
- The missing features (audio transformers, continuous listening, multiple wake words, etc.) are not needed.

Use `ovos-dinkum-listener` when:
- Running a full OVOS installation on a capable device.
- You need continuous listening or hybrid listening modes.
- You need audio transformer plugins (noise reduction, language detection, etc.).
- You need multiple simultaneous wake words.

## Cross-References

- [architecture.md](architecture.md): pipeline stages and plugin interfaces in detail
- [ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener): full-featured production listener
- [ovos-plugin-manager](https://github.com/OpenVoiceOS/ovos-plugin-manager): plugin discovery and factory classes
- [ovos-core](https://github.com/OpenVoiceOS/ovos-core): receives `recognizer_loop:utterance` messages
- [ovos-bus-client](https://github.com/OpenVoiceOS/ovos-bus-client): messagebus client used for OVOS integration

Related projects that use this listener:

- [hivemind-listener](https://github.com/JarbasHiveMind/hivemind-listener): primary use case for this listener
- [hivemind-mic-satellite](https://github.com/JarbasHiveMind/hivemind-mic-satellite): satellite device using this listener
