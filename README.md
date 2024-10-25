# OVOS Simple Listener

`ovos-simple-listener` is a lightweight alternative to `ovos-dinkum-listener`, designed for efficient wake word detection and speech recognition. 

This listener provides a streamlined approach for integrating voice command capabilities into your applications using the Open Voice OS (OVOS) framework.

It was made to power [hivemind-listener](https://github.com/JarbasHiveMind/hivemind-listener) and [hivemind-mic-satellite](https://github.com/JarbasHiveMind/hivemind-mic-satellite), but can also be used in place of [ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener) in your OVOS setups

> at around 150 Lines of code, this repo is a good clean reference of how to use OVOS audio plugins in your own applications

## Features

- **Wake Word Detection**: Supports customizable wake word engines to initiate listening.
- **Voice Activity Detection (VAD)**: Detects silence and speech to optimize audio processing.
- **Speech Recognition**: Utilizes various speech-to-text (STT) engines to transcribe audio input.
- **Callback System**: Provides a flexible callback mechanism to handle state changes and processed audio.
- **Multithreading Support**: Operates in a separate thread to avoid blocking the main application flow.

## Installation

> TODO: This has not yet been packaged and published on pypi, you must run the code manually

To use `ovos-simple-listener`, clone this repository and install the necessary dependencies. You can do this using pip:

```bash
git clone https://github.com/TigreGotico/ovos-simple-listener
cd ovos-simple-listener
pip install -r requirements.txt
```

## OVOS Usage

run `ovos_simple_listener/__main__.py` in place of ovos-dinkum-listener, plugins are selected from the default OVOS config `~/.config/mycroft/mycroft.conf`

## Library Usage

To use `ovos-simple-listener`, you can initialize it with the desired components (microphone, STT, VAD, and wake word) as shown in the example below:

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

You can implement your own callbacks by extending the `ListenerCallbacks` class to handle events such as starting a command, ending listening, processing audio, errors, and recognizing text.

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

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## Acknowledgements

- [Open Voice OS](https://openvoiceos.org) for providing the framework and plugins.
