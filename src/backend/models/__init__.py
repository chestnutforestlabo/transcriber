def get_sd_model(args):
    # Pyannote/speaker-dialization-community-1
    if args.diarization_model_name == "community":
        from models.Diarization.pyannote_speaker_dialization_community.model import SpeechDiarization
        sd_model = SpeechDiarization(args)
    # Pyannote/speaker-dialization-precision-2
    elif args.diarization_model_name == "precision":
        pass
    return sd_model

def get_asr_model(args):
    # Whisper-large-v3
    if args.asr_model_name == "openai":
        from models.Recognition.OpenAI_Whisper_large_v3.model import AutomaticSpeechRecognition
        asr_model = AutomaticSpeechRecognition(args)
    # Qwen3-ASR-1.7B
    elif args.asr_model_name == "qwen":
        from models.Recognition.Qwen_Qwen3_ASR.model import AutomaticSpeechRecognition
        asr_model = AutomaticSpeechRecognition(args)
    # Kotoba-Whisper-v2
    elif args.asr_model_name == "kotoba":
        from models.Recognition.KotobaTech_Kotoba_whisper_v2.model import AutomaticSpeechRecognition
        asr_model = AutomaticSpeechRecognition(args)
    return asr_model


def get_online_llm_model(args):
    if args.online_llm_model == "gemini":
        from models.OnlineLLM.Gemini.model import OnlineLLMTranscription

        return OnlineLLMTranscription(args)
    raise ValueError(f"Unsupported online LLM model: {args.online_llm_model}")
