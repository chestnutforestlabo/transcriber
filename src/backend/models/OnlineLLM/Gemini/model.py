from __future__ import annotations

import os
import re
import time
import importlib
from typing import Any, List, Tuple

from pyannote.core import Segment

from models.OnlineLLM.Gemini.prompt import prompt
from models.base import BaseModel


class OnlineLLMTranscription(BaseModel):
	def setup_model(self) -> dict[str, Any]:
		api_key = os.environ.get("GEMINI_API_KEY")
		if not api_key:
			raise EnvironmentError("GEMINI_API_KEY is not set.")

		try:
			from google import genai as genai_sdk

			return {
				"provider": "google_genai",
				"client": genai_sdk.Client(api_key=api_key),
			}
		except ImportError:
			pass

		try:
			genai_legacy = importlib.import_module("google.generativeai")

			genai_legacy.configure(api_key=api_key)
			return {
				"provider": "google_generativeai",
				"module": genai_legacy,
			}
		except ImportError as exc:
			raise ImportError(
				"Gemini SDK not found. Install `google-genai` (preferred) or "
				"`google-generativeai`."
			) from exc

	@staticmethod
	def _timestamp_to_seconds(ts_str: str) -> int | None:
		try:
			ts_str = ts_str.split(".")[0]
			parts = list(map(int, ts_str.split(":")))
			if len(parts) == 3:
				h, m, s = parts
				return h * 3600 + m * 60 + s
			if len(parts) == 2:
				m, s = parts
				return m * 60 + s
			return None
		except (ValueError, AttributeError, IndexError):
			return None

	@staticmethod
	def _seconds_to_timestamp(total_seconds: int | None) -> str:
		if total_seconds is None or total_seconds < 0:
			total_seconds = 0
		hours, remainder = divmod(total_seconds, 3600)
		minutes, seconds = divmod(remainder, 60)
		return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

	@classmethod
	def _process_transcript(cls, input_text: str, max_segment_duration: int = 30) -> str:
		lines = input_text.strip().splitlines()
		output_lines = []

		current_segment_start_ts_str = None
		current_segment_start_seconds = None
		current_speaker = None
		current_text_parts = []

		line_regex = re.compile(r"^\[((?:\d{2}:)?\d{2}:\d{2}(?:\.\d+)?)\]\s*([^:]+?):\s*(.*)$")

		for i, line in enumerate(lines):
			line = line.strip()
			if not line:
				continue

			match = line_regex.match(line)

			if not match:
				if current_speaker is not None:
					segment_text = " ".join(filter(None, current_text_parts))
					output_lines.append(
						f"[{current_segment_start_ts_str}] {current_speaker}: {segment_text}"
					)
					current_speaker = None
					current_text_parts = []
					current_segment_start_ts_str = None
					current_segment_start_seconds = None
				output_lines.append(line)
				continue

			ts_str, speaker, text = match.groups()
			speaker = speaker.strip()
			text = text.strip()
			current_seconds = cls._timestamp_to_seconds(ts_str)

			if current_seconds is None:
				print(
					f"Warning: Skipping line {i + 1} due to invalid timestamp format: {line}"
				)
				continue

			start_new_segment = False
			if current_speaker is None:
				start_new_segment = True
			elif speaker != current_speaker:
				start_new_segment = True
			elif (
				current_segment_start_seconds is not None
				and current_seconds - current_segment_start_seconds > max_segment_duration
			):
				start_new_segment = True

			if start_new_segment:
				if current_speaker is not None:
					segment_text = " ".join(filter(None, current_text_parts))
					output_lines.append(
						f"[{current_segment_start_ts_str}] {current_speaker}: {segment_text}"
					)
				current_segment_start_ts_str = cls._seconds_to_timestamp(current_seconds)
				current_segment_start_seconds = current_seconds
				current_speaker = speaker
				current_text_parts = [text]
			else:
				if text:
					current_text_parts.append(text)

		if current_speaker is not None:
			segment_text = " ".join(filter(None, current_text_parts))
			output_lines.append(f"[{current_segment_start_ts_str}] {current_speaker}: {segment_text}")

		return "\n".join(output_lines)

	@classmethod
	def _structured_segments(
		cls, transcript: str
	) -> List[Tuple[Segment, str, str]]:
		dialogue_regex = re.compile(
			r"^\[((?:\d{2}:)?\d{2}:\d{2}(?:\.\d+)?)\]\s*([^:]+?):\s*(.*)$"
		)
		non_dialogue_regex = re.compile(r"^\[((?:\d{2}:)?\d{2}:\d{2}(?:\.\d+)?)\]\s*(.*)$")

		parsed_rows: List[tuple[int, str, str]] = []
		for line in transcript.splitlines():
			stripped = line.strip()
			if not stripped or stripped == "[END]":
				continue

			matched = dialogue_regex.match(stripped)
			if matched:
				ts_str, speaker, text = matched.groups()
				start = cls._timestamp_to_seconds(ts_str)
				if start is None:
					continue
				parsed_rows.append((start, speaker.strip(), text.strip()))
				continue

			generic = non_dialogue_regex.match(stripped)
			if generic:
				ts_str, text = generic.groups()
				start = cls._timestamp_to_seconds(ts_str)
				if start is None:
					continue
				parsed_rows.append((start, "SOUND", text.strip()))

		if not parsed_rows:
			return []

		output: List[Tuple[Segment, str, str]] = []
		for idx, (start, speaker, text) in enumerate(parsed_rows):
			if idx + 1 < len(parsed_rows):
				end = parsed_rows[idx + 1][0]
				if end <= start:
					end = start + 1
			else:
				end = start + 2
			output.append((Segment(float(start), float(end)), speaker, text))
		return output

	def inference(self, audio: Any) -> Any:
		print("==============Start Online LLM (Gemini) ASR + Diarization==============")
		start_time = time.time()

		if not isinstance(audio, str):
			raise TypeError("OnlineLLMTranscription expects an audio file path as input.")

		if self.model["provider"] == "google_genai":
			client = self.model["client"]
			uploaded_file = client.files.upload(file=audio)
			response = client.models.generate_content(
				model="gemini-2.5-pro",
				contents=[prompt, uploaded_file],
			)
			return (response.text or ""), start_time

		genai_legacy = self.model["module"]
		uploaded_file = genai_legacy.upload_file(path=audio)
		model = genai_legacy.GenerativeModel("gemini-2.5-pro")
		response = model.generate_content([prompt, uploaded_file])
		return (getattr(response, "text", "") or ""), start_time

	def parse_output(self, raw_output: Any, start_time: float) -> List[Tuple[Segment, str, str]]:
		processed_transcript = self._process_transcript(raw_output, max_segment_duration=30)
		structured = self._structured_segments(processed_transcript)
		print(f"==============Online LLM done in {time.time() - start_time:.2f}s.==============")
		return structured