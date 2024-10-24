import enum
import threading
import time
from typing import Optional

import speech_recognition as sr
from ovos_plugin_manager.microphone import OVOSMicrophoneFactory
from ovos_plugin_manager.stt import OVOSSTTFactory
from ovos_plugin_manager.templates.hotwords import HotWordEngine
from ovos_plugin_manager.templates.microphone import Microphone
from ovos_plugin_manager.templates.stt import STT
from ovos_plugin_manager.templates.vad import VADEngine
from ovos_plugin_manager.vad import OVOSVADFactory
from ovos_utils.log import LOG


class State(enum.IntEnum):
    WAITING_WAKEWORD = 0
    IN_COMMAND = 2


class ListenerCallbacks:
    @classmethod
    def listen_callback(cls):
        LOG.info("New loop state: IN_COMMAND")

    @classmethod
    def end_listen_callback(cls):
        LOG.info("New loop state: WAITING_WAKEWORD")

    @classmethod
    def audio_callback(cls, audio: sr.AudioData):
        LOG.info("Speech finished!")

    @classmethod
    def error_callback(cls, audio: sr.AudioData):
        LOG.error("STT Failure")

    @classmethod
    def text_callback(cls, utterance: str, lang: str):
        LOG.info(f"STT: {utterance}")


class SimpleListener(threading.Thread):
    def __init__(self,
                 wakeword: Optional[HotWordEngine] = None,
                 mic: Optional[Microphone] = None,
                 vad: Optional[VADEngine] = None,
                 stt: Optional[STT] = None,
                 max_silence_seconds=1.5,
                 min_speech_seconds=1,
                 max_speech_seconds=8,
                 callbacks: ListenerCallbacks = ListenerCallbacks()):
        super().__init__(daemon=True)
        self.stt = stt or OVOSSTTFactory.create()
        self.mic = mic or OVOSMicrophoneFactory.create()
        self.vad = vad or OVOSVADFactory.create()
        self.wakeword = wakeword
        self.state = State.WAITING_WAKEWORD
        self.min_speech_seconds = min_speech_seconds
        self.max_speech_seconds = max_speech_seconds
        self.max_silence_seconds = max_silence_seconds  # silence duration limit in seconds

        self.running = False
        self.callbacks = callbacks

    @property
    def lang(self) -> str:
        return self.stt.lang

    def stop(self):
        self.running = False

    def run(self):
        self.running = True
        self.mic.start()

        chunk_duration = self.mic.chunk_size / self.mic.sample_rate  # time (in seconds) per chunk
        total_silence_duration = 0.0  # in seconds
        vad_seconds = 0
        speech_data = b""
        start = 0
        sil_start = 0
        while self.running:

            try:
                chunk = self.mic.read_chunk()

                if self.state == State.WAITING_WAKEWORD and chunk is not None:
                    if self.wakeword is None:
                        if self.vad.is_silence(chunk):
                            vad_seconds = 0
                        else:
                            vad_seconds += chunk_duration
                        ww = vad_seconds >= 0.5
                    else:
                        self.wakeword.update(chunk)
                        ww = self.wakeword.found_wake_word(chunk)

                    if ww:
                        if self.callbacks:
                            self.callbacks.listen_callback()
                        self.state = State.IN_COMMAND
                        sil_start = total_silence_duration = 0.0
                        start = time.time()
                        #if self.wakeword:
                        #    continue  # don't save ww audio

                if self.state == State.IN_COMMAND:
                    total_speech_duration = time.time() - start
                    if sil_start:
                        total_silence_duration = time.time() - sil_start

                    if chunk is not None:
                        if self.vad.is_silence(chunk):
                            sil_start = sil_start or time.time()
                        else:
                            sil_start = total_silence_duration = 0

                        speech_data += chunk

                    timed_out = (total_silence_duration >= self.max_silence_seconds and
                                 self.min_speech_seconds <= total_speech_duration) \
                                or total_speech_duration >= self.max_speech_seconds

                    # reached the max allowed silence time for STT
                    if timed_out:
                        audio = sr.AudioData(speech_data, self.mic.sample_rate, self.mic.sample_width)
                        if self.callbacks:
                            self.callbacks.audio_callback(audio)

                        tx = self.stt.transcribe(audio)
                        if self.callbacks:
                            if tx:
                                utt = tx[0][0].rstrip(" '\"").lstrip(" '\"")
                                self.callbacks.text_callback(utt, self.lang)
                            else:
                                self.callbacks.error_callback(audio)

                        speech_data = b""
                        self.state = State.WAITING_WAKEWORD
                        if self.callbacks:
                            self.callbacks.end_listen_callback()
            except KeyboardInterrupt:
                break
            except Exception as e:
                LOG.debug(f"ERROR: {e}")
        self.running = False
