"""Namespace bus-message tests.

The utterance entry topic is emitted on the OVOS-AUDIO-IN-1 §5 spec namespace
(``ovos.utterance.handle``). The MessageBusClient namespace migration
transparently also-emits the legacy ``recognizer_loop:utterance`` counterpart,
so peers on the old namespace keep working.
"""
import unittest
from unittest.mock import MagicMock

from ovos_spec_tools import SpecMessage

from ovos_simple_listener.__main__ import OVOSCallbacks


class TestUtteranceEntryNamespace(unittest.TestCase):

    def setUp(self):
        self.bus = MagicMock()
        OVOSCallbacks.bus = self.bus

    def _topics(self):
        return [c.args[0].msg_type for c in self.bus.emit.call_args_list]

    def _payloads(self):
        return {c.args[0].msg_type: c.args[0].data for c in self.bus.emit.call_args_list}

    def test_emits_spec_utterance_topic(self):
        OVOSCallbacks.text_callback("hello world", "en-US")
        self.assertIn(SpecMessage.UTTERANCE, self._topics())
        self.assertEqual(self._payloads()[SpecMessage.UTTERANCE],
                         {"utterances": ["hello world"], "lang": "en-US"})


if __name__ == "__main__":
    unittest.main()
