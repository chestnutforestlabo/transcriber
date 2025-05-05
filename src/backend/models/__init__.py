def get_sd_model(args):
    if args.diarization_time:
        # pyannote/embedding：発話区間時刻を入力として使用し、それに基づいて埋め込みを抽出して話者分類を行う
        from models.Diarization.pyannote_embedding.model import SpeechDiarization
        sd_model = SpeechDiarization(args)
    else:
        # pyannote/speaker-diarization-3.1：発話区間時刻も推論して話者分類を行う
        from models.Diarization.pyannote_speaker_diarization.model import SpeechDiarization
        sd_model = SpeechDiarization(args)
    
    return sd_model

def get_asr_model(args):
    # whisper-large-v3
    if args.asr_model_name == "whisper-large-v3":
        from models.Recognition.whisper_large_v3.model import AutomaticSpeechRecognition
        asr_model = AutomaticSpeechRecognition(args)
    else:
        pass
    
    return asr_model