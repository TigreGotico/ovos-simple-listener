"""Namespace bus-message tests.

The utterance entry topic is emitted in exactly one namespace, chosen by the
``legacy_namespace`` config (default True): the legacy
``recognizer_loop:utterance`` or the OVOS-AUDIO-IN-1 §5 ``ovos.utterance.handle``.
Both modes are covered here.
"""
import unittest
from unittest.mock import MagicMock

from ovos_config.config import Configuration

from ovos_simple_listener.__main__ import OVOSCallbacks


class TestUtteranceEntryNamespace(unittest.TestCase):

    def setUp(self):
        self.bus = MagicMock()
        OVOSCallbacks.bus = self.bus
        self._orig_legacy_ns = Configuration().get("legacy_namespace", True)

    def tearDown(self):
        Configuration()["legacy_namespace"] = self._orig_legacy_ns

    def _topics(self):
        return [c.args[0].msg_type for c in self.bus.emit.call_args_list]

    def _payloads(self):
        return {c.args[0].msg_type: c.args[0].data for c in self.bus.emit.call_args_list}

    def test_legacy_namespace_emits_only_legacy_topic(self):
        Configuration()["legacy_namespace"] = True
        OVOSCallbacks.text_callback("hello world", "en-US")
        self.assertIn("recognizer_loop:utterance", self._topics())
        self.assertNotIn("ovos.utterance.handle", self._topics())
        self.assertEqual(self._payloads()["recognizer_loop:utterance"],
                         {"utterances": ["hello world"], "lang": "en-US"})

    def test_spec_namespace_emits_only_spec_topic(self):
        Configuration()["legacy_namespace"] = False
        OVOSCallbacks.text_callback("hello world", "en-US")
        self.assertIn("ovos.utterance.handle", self._topics())
        self.assertNotIn("recognizer_loop:utterance", self._topics())
        self.assertEqual(self._payloads()["ovos.utterance.handle"],
                         {"utterances": ["hello world"], "lang": "en-US"})


if __name__ == "__main__":
    unittest.main()
