# Goal 1: 日本語話者識別(ダイアライゼーション)の精度向上

## 背景とユースケース

- 3人の日本語会話を1本のマイクで録音し、文字起こし+話者識別する。
- 実行環境はローカルの RTX 4090 (24GB VRAM)。クラウドAPIは使わない(既存の Gemini online_llm モードは残すが、今回の改善対象はローカルパイプライン)。
- 現状は `pyannote/speaker-diarization-community-1` を使用(`src/backend/models/Diarization/pyannote_speaker_dialization_community/model.py`)。

## 現状の問題点(コードを読んで確認済み)

1. `src/backend/utils.py` の `add_speaker_info_to_text` は、ASRセグメント全体を「重なり時間が最大の1話者」に割り当てる多数決方式。日本語会話特有の相槌・短い話者交代・オーバーラップで誤割当が起きやすい。
2. ASRセグメント境界と話者交代境界がずれていても、セグメントを分割しないため、1発話に2人の発言が混ざる。
3. community-1 パイプラインが返す `exclusive_speaker_diarization`(オーバーラップを排他化したもの)を活用していない。`parse_output` は `speaker_diarization` をそのまま返すだけ。
4. `data.py` の `_shrink_long_silences` で無音を圧縮した音声をダイアライゼーションに渡しており、タイムスタンプは圧縮後タイムライン基準になっている(これは仕様として維持してよい)。

## 実装してほしいこと

### 1. DiariZen バックエンドの追加(最優先)

- `BUT-FIT/diarizen-wavlm-large-s80-md-v2`(WavLM-Large ベース EEND + クラスタリング、2025-2026 の公開ベンチマークで pyannote community-1 を上回る)を新しいダイアライゼーションバックエンドとして追加する。
- `pip install diarizen` 相当(`diarizen` パッケージ、リポジトリ: https://github.com/BUTSpeechFIT/DiariZen)を `pyproject.toml` に追加。依存が既存の torch==2.8.0 / pyannote-audio==4.0.1 と衝突する場合は、衝突内容を README に記録した上で実現可能な範囲で調整する(torch のバージョン変更は可、CUDA 12.x 対応を維持)。
- 新ディレクトリ: `src/backend/models/Diarization/BUT_DiariZen/model.py`。既存の `BaseModel`(setup_model / inference / parse_output)に従い、`parse_output` は pyannote の `Annotation` 互換(`(Segment, track, label)` を itertracks できる形)で返して `utils.diarize_text` がそのまま動くようにする。
- `transcribe.py` の `--diarization_model_name` に choice `diarizen` を追加し、`models/__init__.py` の `get_sd_model` に分岐を追加。
- `num_speakers` 指定(既存の `args.num_speakers`)をサポートする。DiariZen 側で指定できない場合はクラスタリング後の話者数制約で対応。
- ライセンス注意: DiariZen のモデルは CC BY-NC 4.0(非商用)。README に明記すること。

### 2. 日本語 fine-tune 版 pyannote バックエンドの追加

- `--diarization_model_name pyannote_ja` を追加: `pyannote/speaker-diarization-3.1` パイプラインをロードし、segmentation モデルだけを `diarizers-community/speaker-segmentation-fine-tuned-callhome-jpn`(CALLHOME 日本語で fine-tune 済み)に差し替えたもの。
- 実装参考: huggingface `diarizers` の README にある「pyannote pipeline の `_segmentation.model` を差し替える」方法。`diarizers` パッケージ自体への依存は必須ではない(transformers/pyannote だけで差し替え可能ならそれでよい)。

### 3. community-1 の exclusive diarization の活用

- `pyannote_speaker_dialization_community/model.py` の `parse_output` で、`exclusive_speaker_diarization` が利用可能なら、それを既定で使うオプションを追加(`--use_exclusive_diarization`, default True)。これによりオーバーラップ区間の二重割当を防ぐ。

### 4. ASR-ダイアライゼーション統合の改善(全バックエンド共通で効く)

- `utils.py` に「話者交代境界での ASR セグメント分割」を実装する:
  - ASRセグメントとダイアライゼーション区間の重なりを調べ、1つのASRセグメント内に複数話者が有意に(例: 各0.5秒以上 or 30%以上)含まれる場合、そのASRセグメントを話者境界で時間比例分割するのではなく、**word-level timestamps を使って単語ごとに話者を割り当てる**。
  - openai-whisper は `transcribe(word_timestamps=True)` で単語タイムスタンプを返せる。`OpenAI_Whisper_large_v3/model.py` に `word_timestamps=True` を追加し、parse_output で単語列も保持する(戻り値の互換性に注意: 既存の `(Segment, text)` タプルのリスト形式は維持しつつ、単語情報を第3要素 or 別構造で渡す設計はお任せする。kotoba / qwen で単語タイムスタンプが取れない場合は従来の多数決にフォールバック)。
  - 相槌対策: 0.6秒未満の他話者区間がASRセグメント内に挟まる場合は分割せず主話者に残す、等のヒューリスティックを入れ、閾値は定数として utils.py 冒頭にまとめる。

### 5. バックエンド比較スクリプト

- `scripts/compare_diarization.sh` を追加: 指定した1つの音声ファイルに対し `community` / `pyannote_ja` / `diarizen` を順に実行し、`outputs/comparison/<basename>/<backend>.txt` に保存して目視比較できるようにする。既存の transcribe.py を `--diarization_model_name` を変えて呼ぶだけの薄いラッパーでよい。

## 制約・受け入れ基準

- 既存の CLI(`scripts/transcribe.sh`、`--diarization_model_name community`)と出力 JSON フォーマット(`save_transcripts_json` の start/end/speaker/text)は後方互換を維持。フロントエンドは変更しない。
- **GPU は現在ドライバ不調で使えないため、GPU 実行での動作確認は不要**。代わりに:
  - 合成データ(numpy で作ったダミー波形、モックした diarization Annotation / ASR 出力)で `utils.py` の新しい割当ロジックをテストする pytest を `tests/` に追加し、`uv run pytest`(または `python -m pytest`)が通ること。
  - モデルのダウンロードが必要な統合テストは書かない(コードパスの静的確認とモックテストまで)。
- `pyproject.toml` を更新した場合、`uv lock` が通ること(ネットワークが使えない場合は README に「要 uv lock」と記録)。
- README.md に新バックエンドの使い方・ライセンス注意・精度改善の狙いを追記(日本語でよい)。
- 変更はすべて現在のブランチにコミットせず、ワーキングツリーに残すこと(レビュー後に人間がコミットする)。
