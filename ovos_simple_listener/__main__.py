from typing import Optional, Union

import speech_recognition as sr
from ovos_bus_client import MessageBusClient
from ovos_bus_client.message import Message
from ovos_bus_client.util import get_mycroft_bus
from ovos_plugin_manager.microphone import OVOSMicrophoneFactory
from ovos_plugin_manager.stt import OVOSSTTFactory
from ovos_plugin_manager.vad import OVOSVADFactory
from ovos_plugin_manager.wakewords import OVOSWakeWordFactory
from ovos_utils.fakebus import FakeBus
from ovos_utils.log import LOG
from ovos_config import Configuration
from ovos_simple_listener import ListenerCallbacks, SimpleListener


class OVOSCallbacks(ListenerCallbacks):
    bus = None

    def __init__(self, bus: Optional[Union[MessageBusClient, FakeBus]] = None):
        OVOSCallbacks.bus = bus or get_mycroft_bus()

    @classmethod
    def listen_callback(cls):
        LOG.info("New loop state: IN_COMMAND")
        cls.bus.emit(Message("mycroft.audio.play_sound",
                             {"uri": "smd/start_listening.wav"}))
        cls.bus.emit(Message("recognizer_loop:wakeword"))
        cls.bus.emit(Message("recognizer_loop:record_begin"))

    @classmethod
    def end_listen_callback(cls):
        LOG.info("New loop state: WAITING_WAKEWORD")
        cls.bus.emit(Message("recognizer_loop:record_end"))

    @classmethod
    def error_callback(cls, audio: sr.AudioData):
        LOG.error("STT Failure")
        cls.bus.emit(Message("recognizer_loop:speech.recognition.unknown"))

    @classmethod
    def text_callback(cls, utterance: str, lang: str):
        LOG.info(f"STT: {utterance}")
        cls.bus.emit(Message("recognizer_loop:utterance",
                             {"utterances": [utterance], "lang": lang}))


def main():
    ww = Configuration().get("listener", {}).get("wake_word", "hey_mycroft")
    t = SimpleListener(
        mic=OVOSMicrophoneFactory.create(),
        vad=OVOSVADFactory.create(),
        wakeword=OVOSWakeWordFactory.create_hotword(ww),
        stt=OVOSSTTFactory.create(),
        callbacks=OVOSCallbacks()
    )
    t.run()


if __name__ == "__main__":
    main()
