# Transcriber 📝🎙️

A toolkit that **automatically transcribes multi‑speaker meetings/interviews** with  
**Whisper v3** (ASR) + **Pyannote** (speaker diarization) and lets you review  
the result in a React front‑end with waveform‑synchronised captions.

![Screenshot of Transcriber UI](images/screenshot.png)

```bash
Project structure
├─ audios/num_speakers_N/ # Input audio files (N = max number of speakers)
├─ models # this is where the models will be saved as
├─ outputs # this is where the transcriptions will be saved at
├─ environments
│   ├─ .env
│   ├─ envs.env #you need to make this by yourelf
│   ├─ DockerfileBackend
│   ├─ DockerfileFrontend
│   └─ docker-compose.yaml
├─ scripts/ # Shell scripts
└─ src
    ├─ backend/ # Inference scripts & model wrappers
    └─ frontend/ # Vite + React web app
```

---

## 0. Prerequisites

| Requirement           | Recommended | Notes                                   |
|-----------------------|-------------|-----------------------------------------|
| Python                | 3.10+       | We use UV for dependency handling   |
| CUDA‑enabled GPU      | optional    | CPU works but will be slow              |
| Docker / Docker Compose| 23.x / v2  | For launching the front‑end container   |
| Hugging Face token or Gemini API key    | required    | *Read* scope is enough                  |

---


### ✅ Environment Variable Setup

🔧 Save Host UID and GID

Create a script to detect and persist your user and group IDs:

```bash
id -u  # e.g., 1000
id -g  # e.g., 1000
```

Edit your shell config file:

```bash
vim ~/.bash_profile  # Or ~/.bashrc, depending on your shell
```

Add the following lines:

```bash
export HOST_UID=1000  # Replace with output from id -u
export HOST_GID=1000  # Replace with output from id -g
```

Apply changes:

```bash
source ~/.bash_profile
```

🔐 Hugging Face Token

Before proceeding, create an environment file:

```bash
vim environments/envs.env
```

Add your Hugging Face token or Gemini API key inside the file:

```bash
HF_TOKEN=hf_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
GEMINI_API_KEY=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

📎 Note:
Then, navigate to the Hugging Face webpage of [whisper-large-v3](https://huggingface.co/openai/whisper-large-v3), [Kotoba_whisper_v2](https://huggingface.co/kotoba-tech/kotoba-whisper-v2.0), [Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) and [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) to get access to these models. In particular, [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) requires agreement to the terms of service on HuggingFace.

## 1. Add your audios
Put .wav files (16 kHz recommended) under the folder that encodes the
maximum number of different speakers in the recording, e.g.
audios/num_speakers=2/ for a two‑speaker conversation.

```bash
# exsample
audios/
├─ num_speakers=1/
├─ num_speakers=2/
│   ├─ sample1.wav
│   └─ sample2.wav
└─ num_speakers=3/
```

## 2. Setteung models
Specify the model to use in `environments/transcribe.env` before creating the Docker container.

## 3. Run transcription
Run the transcription script:

```bash
# Activate docker container
bash scripts/docker.sh

# Transcribe your audios
bash scripts/transcribe.sh

#  If you want to use the online LLMs for transcription, add `online=True` to the command line.
bash scripts/transcribe.sh online=True

# If you want to transcribe only specific audio files, add the paths to those files as command-line arguments.
bash scripts/transcribe.sh /path/to/your/audio                  # Using offline models
bash scripts/transcribe.sh online=True /path/to/your/audio      # Using online LLMs
```

Transcription results will be saved to:

output/<file>.json
frontend/public/transcripts/<file>.json
The original audio is also copied to frontend/public/audios/, and index.json is auto‑updated for front‑end use.

### DJI Mic Mini 2 のチャンネル分離モード

2TX + 1RX で2人を録音する場合は、RX の録音モードを「ステレオ」にして
TX1 を Lch、TX2 を Rch に分離してください。モノミックスされた WAV では
チャンネル分離モードを使用できません。トランスミッター側のノイズ
キャンセリングは、ASR に必要な音声成分を損なわないよう弱めを推奨します。

取り込み後の WAV は `audios/num_speakers_2/` に置き、次のように実行します。

```bash
uv run src/backend/transcribe.py \
  --audio_dir audios/num_speakers_2 \
  --asr_model_name openai \
  --channel_mode
```

OpenAI Whisper は既定で beam size 5 を使用します。固有名詞や収録時の語彙を
補助したい場合は、次のように初期プロンプトも指定できます。

```bash
uv run src/backend/transcribe.py \
  --audio_dir audios/num_speakers_2 \
  --asr_model_name openai \
  --channel_mode \
  --asr_beam_size 5 \
  --asr_initial_prompt "銀座、ルイ・ヴィトン、シャネル、ピンマイク、文字起こし"
```

Lch は `SPEAKER_00`、Rch は `SPEAKER_01` として出力されます。このモードでは
ダイアライゼーションモデルを使用せず、各チャンネルを Silero VAD と短時間
RMS 比でゲーティングして、相手話者の小さな漏れ込みを除外してから個別に
ASR を実行します。同時発話のように両チャンネルが同程度の音量なら、両方を
残します。

漏れ込み判定は既定で「自チャンネルが相手より 6 dB 以上小さい場合」です。
録音ゲインやマイク位置に応じて、たとえば
`--channel_crosstalk_threshold_db -9` のように調整できます。値は負の dB で
指定してください。

DJI Mic Mini 2 の 48 kHz / 24 bit WAV は、既存パイプラインが 16 kHz に
リサンプルするため変換せずに配置して構いません。1ch WAV を指定した場合は
エラーになるので、通常の1マイク録音は `--channel_mode` なしで実行して
ください。

### 擬似3チャンネル（Mac 2ch + iPhone 1ch）

DJI Mic Mini 2 の2本に iPhone + AirPods を加えると、3人を1人1マイクで
収録できます。Mac と iPhone の録音開始時刻が違っていても、会話の前後に
全マイクへ聞こえるクラップを入れることで自動的に時刻を合わせます。

```text
話者A ─ DJI TX1 ─┐
                  ├─ DJI RX ─ USB ─ Mac ─ 2ch WAV
話者B ─ DJI TX2 ─┘                    ├─ Lch: SPEAKER_00
                                      └─ Rch: SPEAKER_01

話者C ─ AirPods ─ Bluetooth ─ iPhone ボイスメモ ─ mono m4a
                                                    └─ SPEAKER_02
```

Mac 側は次のスクリプトで録音できます。引数なしでは AVFoundation の
デバイス一覧を表示した後、DJI RX のデバイス名または番号を対話入力します。
第1引数でデバイス、第2引数で出力先ディレクトリを直接指定することも
できます。出力は `rec_YYYYMMDD_HHMMSS.wav`（48 kHz / 16 bit / 2ch）です。

```bash
scripts/record_mac_dji.sh
# または
scripts/record_mac_dji.sh "DJI MIC MINI" audios/num_speakers_3
```

録音手順は次のとおりです。

1. Mac で `record_mac_dji.sh`、iPhone でボイスメモを開始します。順不同で、
   厳密に同時である必要はありません。
2. 全マイクに聞こえる位置で手を1回叩きます。
3. 会話を収録します。
4. 終了直前にもう1回手を叩き、両方の録音を停止します。
5. iPhone の m4a を AirDrop などで Mac へ転送し、Mac の WAV と同じ
   プロジェクト内へ置きます。

メイン WAV が1つだけ入ったディレクトリを指定して実行します。

```bash
uv run src/backend/transcribe.py \
  --audio_dir audios/num_speakers_3 \
  --asr_model_name openai \
  --channel_mode \
  --aux_audio aux/speakerC.m4a
```

先頭と末尾の各120秒から onset 強度の相互相関を取り、開始オフセットと
クロックドリフトを推定します。推定値と相関信頼度はコンソール、および
文字起こし JSON の `meta.channel_alignment` に保存されます。信頼度警告が
出た場合は波形を確認し、必要なら aux の開始位置がメイン時刻軸の何秒に
当たるかを手動指定してください。擬似3チャンネルの JSON はトップレベルに
`meta` と `transcripts` を持ち、従来モードの配列形式は変更しません。

```bash
uv run src/backend/transcribe.py \
  --audio_dir audios/num_speakers_3 \
  --asr_model_name openai \
  --channel_mode \
  --aux_audio aux/speakerC.m4a \
  --aux_offset 1.7
```

補助音声を複数指定すると、指定順に `SPEAKER_02`、`SPEAKER_03` …となります。
その場合、手動オフセットも補助音声と同じ順・同じ個数で指定します。
ボイスメモはモノラルを前提とし、ステレオなど複数チャンネルだった場合は
ch0 だけを使い、その旨をログへ表示します。AirPods の Bluetooth HFP 音声は
帯域が狭く実質16 kHz程度ですが、Whisper も入力を16 kHzへ変換するため影響は
限定的です。iOS のショートカットを使えば、ボイスメモの開始・停止も
自動化できます。

### Diarization backends

ローカルパイプラインでは次の話者識別バックエンドを選択できます。

| CLI value | Model | 用途 |
|---|---|---|
| `community` | `pyannote/speaker-diarization-community-1` | 既定値。exclusive diarization を使って重複話者を排他化 |
| `pyannote_ja` | pyannote 3.1 + CALLHOME 日本語 fine-tune segmentation | 日本語会話向け |
| `diarizen` | `BUT-FIT/diarizen-wavlm-large-s80-md-v2` | WavLM-Large EEND + VBx |

例:

```bash
uv run src/backend/transcribe.py \
  --audio_dir audios/num_speakers_3 \
  --diarization_model_name diarizen
```

`community` などが exclusive diarization を返す場合は既定でそちらを
使用します。従来の重複を含む diarization を使う場合は
`--no-use_exclusive_diarization` を指定してください。

OpenAI Whisper では word-level timestamp を取得し、1つの ASR セグメント内に
有意な話者交代がある場合に単語単位で話者を割り当てます。単語 timestamp を
返さない ASR (`kotoba` など) は従来どおり、重なり時間が最大の話者へ
フォールバックします。短い相槌は主話者の発話として保持します。

#### モデル利用条件と依存関係

- `pyannote_ja` の利用前に Hugging Face で
  `pyannote/segmentation-3.0` と `pyannote/speaker-diarization-3.1`
  の利用条件へ同意し、`HF_TOKEN` を設定してください。
- **DiariZen の学習済み重みは CC BY-NC 4.0 で、非商用利用に限定されます。**
  商用用途には使用しないでください。
- DiariZen 本家は同梱版 pyannote.audio 3.1.1 と NumPy 1.26.4、Torch
  2.1.1 を案内していますが、これらは既存の community-1 が必要とする
  pyannote.audio 4.0.1 と衝突します。本プロジェクトは DiariZen のモデル
  構造を pyannote.audio 4.0.1 の VBx/PLDA パイプラインへ載せる互換
  アダプターを使用し、既存の Torch 2.8.0 / CUDA 12.x 構成を維持します。
  `diarizen` と `diarizers` は再現性のため Git commit を固定しています。

依存関係を反映するには次を実行してください。

```bash
uv sync
```

3バックエンドを同じ音声で目視比較するには、`num_speakers_N` ディレクトリ内の
WAVを指定します。

```bash
bash scripts/compare_diarization.sh audios/num_speakers_3/sample.wav
```

結果は
`outputs/comparison/<basename>/{community,pyannote_ja,diarizen}.txt`
に保存されます。


## 4. Start the front‑end
Open http://localhost:5173 in your browser.
You should see the waveform, speaker‑coloured captions, and you can seek by
clicking either the text or the waveform.

```bash
# Activate frontend Docker container and Activate local server
bash scripts/frontend.sh
```

# Contributors
- **Project Lead/Engineer**: [@chestnutforestlabo](https://github.com/chestnutforestlabo)
- **Project Engineer**: [@Shinceliry](https://github.com/Shinceliry)

**🪂 This project is based on [cvpaperchallenge/Ascender](https://github.com/cvpaperchallenge/Ascender).**
