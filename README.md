# OVOS Simple Listener

`ovos-simple-listener` is a lightweight alternative to `ovos-dinkum-listener`. It handles wake word detection, voice activity detection (VAD), and speech-to-text (STT) transcription for the Open Voice OS (OVOS) framework.

It was built to power [hivemind-listener](https://github.com/JarbasHiveMind/hivemind-listener) and [hivemind-mic-satellite](https://github.com/JarbasHiveMind/hivemind-mic-satellite). You can also use it in place of [ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener) in your OVOS setup.

At around 150 lines of code, this repo is a clean reference for how to use OVOS audio plugins in your own applications.

## Features

- **Wake Word Detection**: supports customizable wake word engines to start listening.
- **Voice Activity Detection (VAD)**: detects silence and speech to optimize audio processing.
- **Speech Recognition**: uses various speech-to-text (STT) engines to transcribe audio input.
- **Callback System**: gives a flexible callback mechanism to handle state changes and processed audio.
- **Multithreading Support**: runs in a separate thread so it does not block the main application flow.

This repo is lighter than [ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener), so it is also missing some features:

- Audio Transformer plugins
- Continuous Listening
- Hybrid Listening
- Recording Mode
- Sleep Mode
- Multiple WakeWords

## Installation

Install `ovos-simple-listener` with pip:

```bash
pip install ovos-simple-listener
```

## OVOS Usage

Run `ovos_simple_listener/__main__.py` in place of `ovos-dinkum-listener`. Plugins are selected from the default OVOS config at `~/.config/mycroft/mycroft.conf`.

## Library Usage

Initialize `ovos-simple-listener` with the components you want (microphone, STT, VAD, and wake word), as shown below.

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

### Callbacks

You can add your own callbacks by extending the `ListenerCallbacks` class. Use it to handle events such as starting a command, ending listening, processing audio, errors, and recognizing text.

```python
from ovos_simple_listener import ListenerCallbacks

class MyCallbacks(ListenerCallbacks):
    @classmethod
    def listen_callback(cls):
        # Handle when the listener starts processing a command
        pass

    @classmethod
    def end_listen_callback(cls):
        # Handle when the listener stops processing a command
        pass

    @classmethod
    def audio_callback(cls, audio):
        # Handle processed audio data
        pass

    @classmethod
    def error_callback(cls, audio):
        # Handle STT errors
        pass

    @classmethod
    def text_callback(cls, utterance, lang):
        # Handle recognized text
        pass
```

## Related Projects

- [ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener): the full-featured production listener this repo is a lightweight alternative to.
- [ovos-plugin-manager](https://github.com/OpenVoiceOS/ovos-plugin-manager): supplies the microphone, STT, VAD, and wake word factories this repo uses.
- [ovos-core](https://github.com/OpenVoiceOS/ovos-core): receives the recognized utterances this repo sends over the messagebus.
- [hivemind-listener](https://github.com/JarbasHiveMind/hivemind-listener): a primary use case for this listener.
- [hivemind-mic-satellite](https://github.com/JarbasHiveMind/hivemind-mic-satellite): a satellite device that uses this listener.

See [docs/index.md](docs/index.md) for a full overview, and [docs/architecture.md](docs/architecture.md) for the pipeline architecture in detail.

## Contributing

Contributions are welcome. Open an issue or submit a pull request for any improvements or bug fixes.

## Acknowledgements

- [Open Voice OS](https://openvoiceos.org) for the framework and plugins.

## License

This project is licensed under the terms in [LICENSE](LICENSE).
