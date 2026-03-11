
# ovos-simple-listener — Audit Report

## Config Key Cross-check vs canonical mycroft.conf

### Keys read — present in canonical mycroft.conf ✅

| Key | Default | Source |
|---|---|---|
| `listener.wake_word` | `"hey_mycroft"` | `__main__.py:49` |

### Keys used as constructor params — absent from canonical conf ⚠️

These are passed as constructor arguments to `SimpleListener` but are not
read from `Configuration()`. They cannot currently be set via `mycroft.conf`.

| Key (proposed) | Default | Source | Notes |
|---|---|---|---|
| `listener.max_silence_seconds` | `1.5` | `__init__.py:50` | Silence duration before utterance ends |
| `listener.min_speech_seconds` | `1` | `__init__.py:51` | Min speech before timeout can trigger |
| `listener.max_speech_seconds` | `8` | `__init__.py:52` | Hard cut-off for recording |

**Action needed**: `main()` should read these from `Configuration().get("listener", {})`
and pass them to `SimpleListener.__init__()`. Then add them to canonical mycroft.conf.

## Resolved Issues (2026-03-11)

- ✅ Unit tests added: `test/unittests/test_simple_listener.py` — 30 tests passing
- ✅ All CI workflows added: `build-tests`, `coverage`, `lint`, `pip_audit`,
  `repo-health`, `release-preview`, `license_check`, `python-support`
- ✅ Stale `release_workflow.yml` replaced with canonical `@dev` version
- ✅ Duplicate `conventional-label.yaml` removed (kept `.yml`)
- ✅ FAQ.md paths corrected (`-e .`, `test/`)

## Remaining Technical Debt

- `[MINOR]` `main()` hardcodes timing params — not configurable via mycroft.conf
- `[MINOR]` `OVOSCallbacks.bus` is a class variable — not safe for multiple instances
- `[MINOR]` `SpeechRecognition` dependency (`sr.AudioData`) — lightweight wrapper
  only; consider using `ovos_plugin_manager.utils.audio.AudioData` for consistency
