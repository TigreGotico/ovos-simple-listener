"""
Unit tests for ovos_simple_listener.

SimpleListener is a thin state machine with two states:
  WAITING_WAKEWORD → IN_COMMAND (on wakeword or VAD trigger)
  IN_COMMAND → WAITING_WAKEWORD (after silence timeout or max speech timeout)

Tests drive the run() loop by mocking the mic, VAD, STT and wakeword engines,
then calling run() in a background thread that we stop after a short time.
"""
import threading
import time
import unittest
from unittest.mock import MagicMock, patch, call

import speech_recognition as sr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
CHUNK_SIZE = 1024

SILENT_CHUNK = b"\x00" * CHUNK_SIZE
SPEECH_CHUNK = b"\xff" * CHUNK_SIZE


def _make_mock_mic(chunks=None):
    """Return a mock Microphone that yields the given sequence of chunks."""
    mic = MagicMock()
    mic.sample_rate = SAMPLE_RATE
    mic.sample_width = SAMPLE_WIDTH
    mic.chunk_size = CHUNK_SIZE
    if chunks is not None:
        mic.read_chunk.side_effect = chunks
    else:
        mic.read_chunk.return_value = SILENT_CHUNK
    return mic


def _make_mock_vad(silence=True):
    vad = MagicMock()
    vad.is_silence.return_value = silence
    return vad


def _make_mock_stt(transcript="hello"):
    stt = MagicMock()
    stt.lang = "en-us"
    stt.transcribe.return_value = [(transcript, 0.9)]
    return stt


def _make_mock_wakeword(found=False):
    ww = MagicMock()
    ww.found_wake_word.return_value = found
    return ww


# ---------------------------------------------------------------------------
# State enum
# ---------------------------------------------------------------------------

class TestState(unittest.TestCase):
    """Tests for ovos_simple_listener.State enum."""

    def test_values(self):
        """WAITING_WAKEWORD=0, IN_COMMAND=2."""
        from ovos_simple_listener import State
        self.assertEqual(State.WAITING_WAKEWORD, 0)
        self.assertEqual(State.IN_COMMAND, 2)


# ---------------------------------------------------------------------------
# ListenerCallbacks
# ---------------------------------------------------------------------------

class TestListenerCallbacks(unittest.TestCase):
    """Tests for default (no-op) ListenerCallbacks."""

    def test_listen_callback_does_not_raise(self):
        from ovos_simple_listener import ListenerCallbacks
        ListenerCallbacks.listen_callback()

    def test_end_listen_callback_does_not_raise(self):
        from ovos_simple_listener import ListenerCallbacks
        ListenerCallbacks.end_listen_callback()

    def test_audio_callback_does_not_raise(self):
        from ovos_simple_listener import ListenerCallbacks
        audio = sr.AudioData(b"\x00" * 100, SAMPLE_RATE, SAMPLE_WIDTH)
        ListenerCallbacks.audio_callback(audio)

    def test_error_callback_does_not_raise(self):
        from ovos_simple_listener import ListenerCallbacks
        audio = sr.AudioData(b"\x00" * 100, SAMPLE_RATE, SAMPLE_WIDTH)
        ListenerCallbacks.error_callback(audio)

    def test_text_callback_does_not_raise(self):
        from ovos_simple_listener import ListenerCallbacks
        ListenerCallbacks.text_callback("hello", "en-us")


# ---------------------------------------------------------------------------
# SimpleListener construction
# ---------------------------------------------------------------------------

class TestSimpleListenerInit(unittest.TestCase):
    """Tests for SimpleListener.__init__()."""

    def _make(self, **kwargs):
        from ovos_simple_listener import SimpleListener
        defaults = dict(
            mic=_make_mock_mic(),
            vad=_make_mock_vad(),
            stt=_make_mock_stt(),
            wakeword=_make_mock_wakeword(),
        )
        defaults.update(kwargs)
        return SimpleListener(**defaults)

    def test_initial_state_is_waiting_wakeword(self):
        """Listener starts in WAITING_WAKEWORD state."""
        from ovos_simple_listener import State
        sl = self._make()
        self.assertEqual(sl.state, State.WAITING_WAKEWORD)

    def test_not_running_before_start(self):
        sl = self._make()
        self.assertFalse(sl.running)

    def test_lang_delegates_to_stt(self):
        stt = _make_mock_stt()
        stt.lang = "de-de"
        sl = self._make(stt=stt)
        self.assertEqual(sl.lang, "de-de")

    def test_default_timing_params(self):
        sl = self._make()
        self.assertEqual(sl.max_silence_seconds, 1.5)
        self.assertEqual(sl.min_speech_seconds, 1)
        self.assertEqual(sl.max_speech_seconds, 8)

    def test_custom_timing_params(self):
        sl = self._make(max_silence_seconds=2.0, min_speech_seconds=0.5, max_speech_seconds=10)
        self.assertEqual(sl.max_silence_seconds, 2.0)
        self.assertEqual(sl.min_speech_seconds, 0.5)
        self.assertEqual(sl.max_speech_seconds, 10)

    def test_is_daemon_thread(self):
        sl = self._make()
        self.assertTrue(sl.daemon)


# ---------------------------------------------------------------------------
# SimpleListener.stop()
# ---------------------------------------------------------------------------

class TestSimpleListenerStop(unittest.TestCase):
    def test_stop_sets_running_false(self):
        from ovos_simple_listener import SimpleListener
        sl = SimpleListener(
            mic=_make_mock_mic(),
            vad=_make_mock_vad(),
            stt=_make_mock_stt(),
        )
        sl.running = True
        sl.stop()
        self.assertFalse(sl.running)

    def test_stop_calls_mic_stop(self):
        from ovos_simple_listener import SimpleListener
        mic = _make_mock_mic()
        sl = SimpleListener(
            mic=mic,
            vad=_make_mock_vad(),
            stt=_make_mock_stt(),
        )
        sl.running = True
        sl.stop()
        mic.stop.assert_called_once()


# ---------------------------------------------------------------------------
# Wakeword detection path
# ---------------------------------------------------------------------------

class TestWakewordDetection(unittest.TestCase):
    """Tests for wakeword-triggered transition to IN_COMMAND."""

    def _run_briefly(self, sl, seconds=0.1):
        """Start run() in a thread, stop after `seconds`."""
        t = threading.Thread(target=sl.run, daemon=True)
        t.start()
        time.sleep(seconds)
        sl.stop()
        t.join(timeout=2)

    def test_wakeword_found_calls_listen_callback(self):
        """When WW found, listen_callback is called."""
        from ovos_simple_listener import SimpleListener, State

        ww = _make_mock_wakeword(found=True)
        callbacks = MagicMock()
        mic = _make_mock_mic()
        vad = _make_mock_vad(silence=True)
        stt = _make_mock_stt()

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=ww, callbacks=callbacks)
        self._run_briefly(sl)

        callbacks.listen_callback.assert_called()

    def test_wakeword_found_transitions_to_in_command(self):
        """After WW found, state eventually reaches IN_COMMAND."""
        from ovos_simple_listener import SimpleListener, State

        ww = _make_mock_wakeword(found=True)
        callbacks = MagicMock()
        mic = _make_mock_mic()
        vad = _make_mock_vad(silence=True)
        stt = _make_mock_stt()

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=ww, callbacks=callbacks,
                            max_silence_seconds=100, min_speech_seconds=100)
        t = threading.Thread(target=sl.run, daemon=True)
        t.start()
        # Wait until state changes
        deadline = time.time() + 2
        while sl.state != State.IN_COMMAND and time.time() < deadline:
            time.sleep(0.01)
        sl.stop()
        t.join(timeout=2)
        self.assertEqual(sl.state, State.IN_COMMAND)

    def test_no_wakeword_no_listen_callback(self):
        """When WW not found, listen_callback is never called."""
        from ovos_simple_listener import SimpleListener

        ww = _make_mock_wakeword(found=False)
        callbacks = MagicMock()
        mic = _make_mock_mic()
        vad = _make_mock_vad(silence=True)
        stt = _make_mock_stt()

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=ww, callbacks=callbacks)
        self._run_briefly(sl)

        callbacks.listen_callback.assert_not_called()

    def test_vad_only_mode_no_wakeword(self):
        """With wakeword=None, VAD speech triggers listen_callback."""
        from ovos_simple_listener import SimpleListener

        callbacks = MagicMock()
        mic = _make_mock_mic()
        # VAD returns speech (not silence)
        vad = _make_mock_vad(silence=False)
        stt = _make_mock_stt()

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=None, callbacks=callbacks)
        self._run_briefly(sl, seconds=0.05)

        callbacks.listen_callback.assert_called()


# ---------------------------------------------------------------------------
# STT / utterance path
# ---------------------------------------------------------------------------

class TestUtterancePath(unittest.TestCase):
    """Tests for STT transcription and callback dispatch."""

    def _run_to_utterance(self, sl, timeout=3.0):
        """Run in a thread; return when text_callback or error_callback fires."""
        t = threading.Thread(target=sl.run, daemon=True)
        t.start()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if (sl.callbacks.text_callback.called or
                    sl.callbacks.error_callback.called):
                break
            time.sleep(0.01)
        sl.stop()
        t.join(timeout=2)

    def test_stt_success_calls_text_callback(self):
        """After STT returns a transcript, text_callback is called."""
        from ovos_simple_listener import SimpleListener

        ww = _make_mock_wakeword(found=True)
        callbacks = MagicMock()
        mic = _make_mock_mic()
        vad = _make_mock_vad(silence=True)  # instant silence → timeout
        stt = _make_mock_stt("hello world")

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=ww, callbacks=callbacks,
                            max_silence_seconds=0.0, min_speech_seconds=0.0)
        self._run_to_utterance(sl)

        callbacks.text_callback.assert_called()
        args = callbacks.text_callback.call_args[0]
        self.assertIn("hello world", args[0])

    def test_stt_failure_calls_error_callback(self):
        """When STT returns empty, error_callback is called instead of text_callback."""
        from ovos_simple_listener import SimpleListener

        ww = _make_mock_wakeword(found=True)
        callbacks = MagicMock()
        mic = _make_mock_mic()
        vad = _make_mock_vad(silence=True)
        stt = _make_mock_stt("")  # empty transcript

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=ww, callbacks=callbacks,
                            max_silence_seconds=0.0, min_speech_seconds=0.0)
        self._run_to_utterance(sl)

        callbacks.error_callback.assert_called()
        callbacks.text_callback.assert_not_called()

    def test_end_listen_callback_called_after_utterance(self):
        """end_listen_callback is called when returning to WAITING_WAKEWORD."""
        from ovos_simple_listener import SimpleListener

        ww = _make_mock_wakeword(found=True)
        callbacks = MagicMock()
        mic = _make_mock_mic()
        vad = _make_mock_vad(silence=True)
        stt = _make_mock_stt("test")

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=ww, callbacks=callbacks,
                            max_silence_seconds=0.0, min_speech_seconds=0.0)
        self._run_to_utterance(sl)

        callbacks.end_listen_callback.assert_called()

    def test_text_stripped_of_surrounding_quotes(self):
        """Text callback receives text with surrounding quotes stripped."""
        from ovos_simple_listener import SimpleListener

        ww = _make_mock_wakeword(found=True)
        callbacks = MagicMock()
        mic = _make_mock_mic()
        vad = _make_mock_vad(silence=True)
        stt = _make_mock_stt('"hello world"')

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=ww, callbacks=callbacks,
                            max_silence_seconds=0.0, min_speech_seconds=0.0)
        self._run_to_utterance(sl)

        args = callbacks.text_callback.call_args[0]
        self.assertEqual(args[0], "hello world")

    def test_text_callback_receives_lang(self):
        """text_callback receives the STT lang as second argument."""
        from ovos_simple_listener import SimpleListener

        ww = _make_mock_wakeword(found=True)
        callbacks = MagicMock()
        mic = _make_mock_mic()
        vad = _make_mock_vad(silence=True)
        stt = _make_mock_stt("bonjour")
        stt.lang = "fr-fr"

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=ww, callbacks=callbacks,
                            max_silence_seconds=0.0, min_speech_seconds=0.0)
        self._run_to_utterance(sl)

        args = callbacks.text_callback.call_args[0]
        self.assertEqual(args[1], "fr-fr")

    def test_state_returns_to_waiting_after_utterance(self):
        """After STT completes, state returns to WAITING_WAKEWORD."""
        from ovos_simple_listener import SimpleListener, State

        ww = _make_mock_wakeword(found=True)
        callbacks = MagicMock()
        mic = _make_mock_mic()
        vad = _make_mock_vad(silence=True)
        stt = _make_mock_stt("hello")

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=ww, callbacks=callbacks,
                            max_silence_seconds=0.0, min_speech_seconds=0.0)
        self._run_to_utterance(sl)

        self.assertEqual(sl.state, State.WAITING_WAKEWORD)


# ---------------------------------------------------------------------------
# Callback exception isolation
# ---------------------------------------------------------------------------

class TestSttNonHappyPathRecovery(unittest.TestCase):
    """A raising or empty STT result must not wedge the loop (regression)."""

    def _run_to_utterance(self, sl, timeout=3.0):
        """Run in a thread; return when text_callback or error_callback fires."""
        t = threading.Thread(target=sl.run, daemon=True)
        t.start()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if (sl.callbacks.text_callback.called or
                    sl.callbacks.error_callback.called):
                break
            time.sleep(0.01)
        return t

    def test_stt_raises_fires_error_callback_and_resets_state(self):
        """A raising transcribe() must not escape the loop unhandled."""
        from ovos_simple_listener import SimpleListener, State

        ww = _make_mock_wakeword(found=True)
        callbacks = MagicMock()
        mic = _make_mock_mic()
        vad = _make_mock_vad(silence=True)
        stt = _make_mock_stt("hello")
        stt.transcribe.side_effect = RuntimeError("network error")

        seen_states = []
        callbacks.end_listen_callback.side_effect = lambda: seen_states.append(sl.state)

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=ww, callbacks=callbacks,
                            max_silence_seconds=0.0, min_speech_seconds=0.0)
        t = self._run_to_utterance(sl)

        callbacks.error_callback.assert_called()
        callbacks.text_callback.assert_not_called()
        callbacks.end_listen_callback.assert_called()
        # state was already reset to WAITING_WAKEWORD by the time end_listen fired
        self.assertEqual(seen_states[0], State.WAITING_WAKEWORD)

        sl.stop()
        t.join(timeout=2)

    def test_stt_raises_recovers_on_next_utterance(self):
        """After a raising STT call, the next utterance transcribes normally."""
        from ovos_simple_listener import SimpleListener, State

        ww = _make_mock_wakeword(found=True)
        callbacks = MagicMock()
        mic = _make_mock_mic()
        vad = _make_mock_vad(silence=True)
        stt = _make_mock_stt("hello world")
        stt.transcribe.side_effect = [RuntimeError("network error"), [("hello world", 0.9)]]

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=ww, callbacks=callbacks,
                            max_silence_seconds=0.0, min_speech_seconds=0.0)
        t = threading.Thread(target=sl.run, daemon=True)
        t.start()

        deadline = time.time() + 3
        while time.time() < deadline and not callbacks.text_callback.called:
            time.sleep(0.01)

        sl.stop()
        t.join(timeout=2)

        callbacks.error_callback.assert_called()
        callbacks.text_callback.assert_called()

    def test_stt_returns_empty_list_fires_error_callback_and_resets_state(self):
        """transcribe() returning [] must not raise IndexError and wedge."""
        from ovos_simple_listener import SimpleListener, State

        ww = _make_mock_wakeword(found=True)
        callbacks = MagicMock()
        mic = _make_mock_mic()
        vad = _make_mock_vad(silence=True)
        stt = _make_mock_stt("hello")
        stt.transcribe.return_value = []

        seen_states = []
        callbacks.end_listen_callback.side_effect = lambda: seen_states.append(sl.state)

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=ww, callbacks=callbacks,
                            max_silence_seconds=0.0, min_speech_seconds=0.0)
        t = self._run_to_utterance(sl)

        callbacks.error_callback.assert_called()
        callbacks.text_callback.assert_not_called()
        callbacks.end_listen_callback.assert_called()
        # state was already reset to WAITING_WAKEWORD by the time end_listen fired
        self.assertEqual(seen_states[0], State.WAITING_WAKEWORD)

        sl.stop()
        t.join(timeout=2)

    def test_stt_returns_empty_list_recovers_on_next_utterance(self):
        """After an empty transcription, the next utterance transcribes normally."""
        from ovos_simple_listener import SimpleListener, State

        ww = _make_mock_wakeword(found=True)
        callbacks = MagicMock()
        mic = _make_mock_mic()
        vad = _make_mock_vad(silence=True)
        stt = _make_mock_stt("hello world")
        stt.transcribe.side_effect = [[], [("hello world", 0.9)]]

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=ww, callbacks=callbacks,
                            max_silence_seconds=0.0, min_speech_seconds=0.0)
        t = threading.Thread(target=sl.run, daemon=True)
        t.start()

        deadline = time.time() + 3
        while time.time() < deadline and not callbacks.text_callback.called:
            time.sleep(0.01)

        sl.stop()
        t.join(timeout=2)

        callbacks.error_callback.assert_called()
        callbacks.text_callback.assert_called()


# ---------------------------------------------------------------------------
# Callback exception isolation
# ---------------------------------------------------------------------------

class TestCallbackExceptionIsolation(unittest.TestCase):
    """A failing callback must not crash the listener loop."""

    def test_listen_callback_exception_does_not_crash(self):
        from ovos_simple_listener import SimpleListener

        callbacks = MagicMock()
        callbacks.listen_callback.side_effect = RuntimeError("boom")
        ww = _make_mock_wakeword(found=True)
        mic = _make_mock_mic()
        vad = _make_mock_vad(silence=True)
        stt = _make_mock_stt("")

        sl = SimpleListener(mic=mic, vad=vad, stt=stt, wakeword=ww, callbacks=callbacks,
                            max_silence_seconds=0.0, min_speech_seconds=0.0)
        t = threading.Thread(target=sl.run, daemon=True)
        t.start()
        time.sleep(0.1)
        sl.stop()
        t.join(timeout=2)
        # No exception propagated — thread completes normally
        self.assertFalse(t.is_alive())


# ---------------------------------------------------------------------------
# OVOSCallbacks
# ---------------------------------------------------------------------------

class TestOVOSCallbacks(unittest.TestCase):
    """Tests for OVOSCallbacks messagebus event emission."""

    def _make_callbacks(self):
        from ovos_simple_listener.__main__ import OVOSCallbacks
        bus = MagicMock()
        OVOSCallbacks.bus = bus
        return OVOSCallbacks, bus

    def test_listen_callback_emits_wakeword(self):
        """listen_callback emits recognizer_loop:wakeword."""
        OVOSCallbacks, bus = self._make_callbacks()
        OVOSCallbacks.listen_callback()
        emitted = [c[0][0].msg_type for c in bus.emit.call_args_list]
        self.assertIn("recognizer_loop:wakeword", emitted)

    def test_listen_callback_emits_record_begin(self):
        """listen_callback emits recognizer_loop:record_begin."""
        OVOSCallbacks, bus = self._make_callbacks()
        OVOSCallbacks.listen_callback()
        emitted = [c[0][0].msg_type for c in bus.emit.call_args_list]
        self.assertIn("recognizer_loop:record_begin", emitted)

    def test_end_listen_callback_emits_record_end(self):
        """end_listen_callback emits recognizer_loop:record_end."""
        OVOSCallbacks, bus = self._make_callbacks()
        OVOSCallbacks.end_listen_callback()
        emitted = [c[0][0].msg_type for c in bus.emit.call_args_list]
        self.assertIn("recognizer_loop:record_end", emitted)

    def test_error_callback_emits_recognition_unknown(self):
        """error_callback emits recognizer_loop:speech.recognition.unknown."""
        OVOSCallbacks, bus = self._make_callbacks()
        audio = sr.AudioData(b"\x00" * 100, SAMPLE_RATE, SAMPLE_WIDTH)
        OVOSCallbacks.error_callback(audio)
        emitted = [c[0][0].msg_type for c in bus.emit.call_args_list]
        self.assertIn("recognizer_loop:speech.recognition.unknown", emitted)

    def test_text_callback_emits_utterance(self):
        """text_callback emits recognizer_loop:utterance with correct payload."""
        OVOSCallbacks, bus = self._make_callbacks()
        OVOSCallbacks.text_callback("hello world", "en-us")
        emitted = {c[0][0].msg_type: c[0][0].data for c in bus.emit.call_args_list}
        self.assertIn("recognizer_loop:utterance", emitted)
        payload = emitted["recognizer_loop:utterance"]
        self.assertEqual(payload["utterances"], ["hello world"])
        self.assertEqual(payload["lang"], "en-us")


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

class TestVersion(unittest.TestCase):
    def test_version_importable(self):
        from ovos_simple_listener.version import __version__
        self.assertIsInstance(__version__, str)
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+")


if __name__ == "__main__":
    unittest.main()
