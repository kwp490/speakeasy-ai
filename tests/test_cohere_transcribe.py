"""Targeted tests for the Cohere transcription engine."""

import unittest

import numpy as np
import torch

from dictator.engine.cohere_transcribe import CohereTranscribeEngine


class _FakeProcessor:
    def __init__(self):
        self.calls = []

    def __call__(self, audio_16k, sampling_rate, return_tensors, language, punctuation):
        self.calls.append(
            {
                "audio_len": len(audio_16k),
                "sampling_rate": sampling_rate,
                "return_tensors": return_tensors,
                "language": language,
                "punctuation": punctuation,
            }
        )
        return {
            "input_features": torch.ones((1, 4, 8), dtype=torch.float32),
            "attention_mask": torch.ones((1, 8), dtype=torch.long),
        }

    def decode(self, output_ids, skip_special_tokens=True):
        return ["ok"]


class _FakeModel:
    def __init__(self):
        self.device = torch.device("cpu")
        self.dtype = torch.float16
        self.generate_kwargs = None

    def generate(self, **kwargs):
        self.generate_kwargs = kwargs
        return torch.tensor([[1, 2, 3]], dtype=torch.long)


class TestCohereTranscribeEngine(unittest.TestCase):
    def test_transcribe_casts_floating_inputs_to_model_dtype(self):
        engine = CohereTranscribeEngine()
        engine._processor = _FakeProcessor()
        engine._model = _FakeModel()

        result = engine._transcribe_impl(
            np.zeros(16000, dtype=np.float32),
            "en",
            punctuation=True,
            timeout=30.0,
        )

        self.assertEqual(result, "ok")
        self.assertIsNotNone(engine._model.generate_kwargs)
        self.assertEqual(
            engine._model.generate_kwargs["input_features"].dtype,
            torch.float16,
        )
        self.assertEqual(
            engine._model.generate_kwargs["attention_mask"].dtype,
            torch.long,
        )


if __name__ == "__main__":
    unittest.main()