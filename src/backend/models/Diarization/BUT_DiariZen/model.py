import os
import time
from pathlib import Path
from typing import Any

import soundfile as sf
import toml
import torch
import torch.nn as nn
from huggingface_hub import snapshot_download
from models.base import BaseModel
from pyannote.audio.core.model import Model as PyannoteModel
from pyannote.audio.core.task import Problem, Resolution, Specifications
from pyannote.audio.pipelines import SpeakerDiarization as PyannoteDiarization
from pyannote.audio.utils.powerset import Powerset
from pyannote.core import Annotation
from scipy.ndimage import median_filter

MODEL_ID = "BUT-FIT/diarizen-wavlm-large-s80-md-v2"
EMBEDDING_MODEL_ID = "pyannote/wespeaker-voxceleb-resnet34-LM"


def _build_segmentation_model(model_args: dict[str, Any]) -> PyannoteModel:
    """Build the DiariZen model with pyannote.audio 4 model metadata."""
    try:
        from diarizen.models.eend.model_wavlm_conformer import (
            Model as DiariZenSegmentationModel,
        )
        from diarizen.models.module.conformer import ConformerEncoder
    except ImportError as exc:
        raise ImportError(
            "The diarizen backend requires the `diarizen` package."
        ) from exc

    class CompatibleDiariZenModel(DiariZenSegmentationModel):
        """DiariZen architecture adapted to pyannote.audio 4's Model base."""

        def __init__(
            self,
            wavlm_src: str = "wavlm_base",
            wavlm_layer_num: int = 13,
            wavlm_feat_dim: int = 768,
            attention_in: int = 256,
            ffn_hidden: int = 1024,
            num_head: int = 4,
            num_layer: int = 4,
            kernel_size: int = 31,
            dropout: float = 0.1,
            use_posi: bool = False,
            output_activate_function: bool = False,
            max_speakers_per_chunk: int = 4,
            max_speakers_per_frame: int = 2,
            chunk_size: int = 5,
            num_channels: int = 8,
            selected_channel: int = 0,
            sample_rate: int = 16000,
        ):
            # Upstream DiariZen embeds a pyannote.audio 3.1 fork whose Model
            # constructor differs from pyannote.audio 4. Keep the architecture
            # unchanged while providing current pyannote model metadata.
            PyannoteModel.__init__(
                self,
                sample_rate=sample_rate,
                num_channels=1,
            )
            self.specifications = Specifications(
                problem=Problem.MONO_LABEL_CLASSIFICATION,
                resolution=Resolution.FRAME,
                duration=chunk_size,
                min_duration=min(5, chunk_size),
                warm_up=(0.0, 0.0),
                classes=[
                    f"speaker#{index + 1}" for index in range(max_speakers_per_chunk)
                ],
                powerset_max_classes=max_speakers_per_frame,
                permutation_invariant=True,
            )
            self.powerset = Powerset(
                len(self.specifications.classes),
                self.specifications.powerset_max_classes,
            )

            self.num_channels = num_channels
            self.sample_rate = sample_rate
            self.chunk_size = chunk_size
            self.selected_channel = selected_channel

            self.wavlm_model = self.load_wavlm(wavlm_src)
            self.weight_sum = nn.Linear(wavlm_layer_num, 1, bias=False)
            self.proj = nn.Linear(wavlm_feat_dim, attention_in)
            self.lnorm = nn.LayerNorm(attention_in)
            self.conformer = ConformerEncoder(
                attention_in=attention_in,
                ffn_hidden=ffn_hidden,
                num_head=num_head,
                num_layer=num_layer,
                kernel_size=kernel_size,
                dropout=dropout,
                use_posi=use_posi,
                output_activate_function=output_activate_function,
            )
            self.classifier = nn.Linear(attention_in, self.dimension)
            self.activation = self.default_activation()

    return CompatibleDiariZenModel(**model_args)


class DiariZenPipeline(PyannoteDiarization):
    """Pyannote 4 pipeline retaining DiariZen's median-filtering stage."""

    def __init__(self, *args, apply_median_filtering: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_median_filtering = apply_median_filtering

    def get_segmentations(self, file, hook=None):
        segmentations = super().get_segmentations(file, hook=hook)
        if self.apply_median_filtering:
            segmentations.data = median_filter(
                segmentations.data,
                size=(1, 11, 1),
                mode="reflect",
            )
        return segmentations


class SpeechDiarization(BaseModel):
    """DiariZen WavLM-Large EEND + VBx diarization backend."""

    def setup_model(self) -> DiariZenPipeline:
        os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
        torch.serialization.add_safe_globals([Specifications])

        token = os.environ.get("HF_TOKEN")
        cache_dir = os.environ.get("HF_HOME", "./models")
        model_dir = Path(
            snapshot_download(
                repo_id=MODEL_ID,
                token=token,
                cache_dir=cache_dir,
                allow_patterns=[
                    "config.toml",
                    "pytorch_model.bin",
                    "plda/*.npz",
                ],
            )
        )

        config = toml.load(model_dir / "config.toml")
        inference_config = config["inference"]["args"]
        clustering_config = config["clustering"]["args"]

        segmentation_model = _build_segmentation_model(config["model"]["args"])
        state_dict = torch.load(
            model_dir / "pytorch_model.bin",
            map_location="cpu",
            weights_only=True,
        )
        segmentation_model.load_state_dict(state_dict, strict=True)
        segmentation_model.eval()

        if clustering_config["method"] != "VBxClustering":
            raise ValueError(
                "This backend currently supports DiariZen VBx checkpoints only."
            )

        pipeline = DiariZenPipeline(
            segmentation=segmentation_model,
            segmentation_step=inference_config["segmentation_step"],
            embedding=EMBEDDING_MODEL_ID,
            embedding_exclude_overlap=True,
            plda={
                "checkpoint": str(model_dir),
                "subfolder": "plda",
            },
            clustering="VBxClustering",
            embedding_batch_size=inference_config["batch_size"],
            segmentation_batch_size=inference_config["batch_size"],
            token=token,
            cache_dir=cache_dir,
            apply_median_filtering=inference_config["apply_median_filtering"],
        )
        pipeline.instantiate(
            {
                "segmentation": {"min_duration_off": 0.0},
                "clustering": {
                    "threshold": clustering_config["ahc_threshold"],
                    "Fa": clustering_config["Fa"],
                    "Fb": clustering_config["Fb"],
                },
            }
        )
        return pipeline

    def inference(self, audio_source: str) -> tuple[Any, float]:
        print("==============Start Diarization (DiariZen)==============")
        start_time = time.time()

        waveform, sample_rate = sf.read(
            audio_source,
            always_2d=True,
            dtype="float32",
        )
        # The selected DiariZen checkpoint is trained for channel 0.
        waveform = torch.from_numpy(waveform[:, :1].T)
        output = self.model(
            {
                "uri": audio_source,
                "waveform": waveform,
                "sample_rate": sample_rate,
            },
            num_speakers=self.args.num_speakers,
        )
        return output, start_time

    def parse_output(self, output: Any, start_time: float) -> Annotation:
        print(output)
        print(
            "==============Diarization done in "
            f"{time.time() - start_time:.2f} seconds.=============="
        )

        if getattr(self.args, "use_exclusive_diarization", True):
            exclusive = getattr(output, "exclusive_speaker_diarization", None)
            if exclusive is not None:
                return exclusive

        diarization = getattr(output, "speaker_diarization", None)
        if diarization is not None:
            return diarization
        return output
