# 実験セッション自動処理プロンプト(codex 用)

あなたは実験データ処理の実行者です。以下の手順を**指定されたセッションフォルダ**に対して最後まで自動で実行してください。作業ディレクトリは transcriber リポジトリのルート(例: /home/arata/transcriber)です。

## 入力(セッションフォルダの内容 — 人間が準備済み)

- `調査1` 〜 `調査5`(拡張子 .m4a / .mp4 / .wav のいずれか): 2人歩行の 2ch 録音。TX1=Lch=同行者、TX2=Rch=視覚障害者
- `実験後インタビュー（ユーザ側）.*`: 2ch 録音(Lch=同行者、Rch=視覚障害者)
- `実験後インタビュー(実験者側).*`: モノラル録音(実験者の第3チャンネル)
- 任意 `logs/*.jsonl`: アプリログ(schema v2)。あれば AI イベント付きコーディングに使う
- 任意 各録音の `<名前>.time.json`({"recording_start": "ISO8601"})または `times.json`(ファイル名→録音開始時刻のマップ)。record_mac_dji.sh の sidecar と同形式

## 実行手順

### 1. 検証と変換

- 各ファイルを ffprobe で確認: 調査1〜5 とユーザ側は `channels=2`、実験者側は `channels=1` であること。違うファイルは**スキップして理由を最終報告に記載**(処理は続行)
- ffmpeg で wav 化(必ず `-vn -ac 2 -c:a pcm_s16le`。実験者側のみ `-ac 1`):
  - 調査N → `audios/num_speakers_2/chosaN.wav`
  - ユーザ側 → `audios/num_speakers_3/interview.wav`、実験者側 → リポジトリ直下 `interview_aux.wav`
- ffmpeg/ffprobe はコンテナ内にある: `cd environments && docker compose exec -T backend <cmd>`

### 2. qwen 文字起こし(ローカルモデルのみ使用)

- 調査1〜5:
  `docker compose exec -T backend uv run src/backend/transcribe.py --audio_dir audios/num_speakers_2 --audio_files chosa1.wav chosa2.wav chosa3.wav chosa4.wav chosa5.wav --asr_model_name qwen --channel_mode`
- インタビュー(擬似3ch):
  `docker compose exec -T backend uv run src/backend/transcribe.py --audio_dir audios/num_speakers_3 --asr_model_name qwen --channel_mode --aux_audio interview_aux.wav`
- 出力は `outputs/<basename>/<basename>.json`。インタビューのアライメント警告(correlation ambiguous 等)は最終報告に転記

### 3. コーディング(ラベル付け)

ラベル定義は `docs/coding_scheme.md`(変更しないこと)。

- **AI イベント付き**(条件: `logs/` があり、かつその調査の録音開始時刻が time.json / times.json で与えられている場合):
  1. `docker compose exec -T backend bash -c "uv run src/backend/coding/prepare_ai_events.py <セッションフォルダのlogs>/*.jsonl --audio audios/num_speakers_2/chosaN.wav --recording_start '<ISO8601>' --output outputs/coding/chosaN/ai_events.json"`
     - ブラケット欠落の WARNING はそのまま許容(録音窓フォールバックが正常動作)
     - ai_utterances が 0 件なら AI 非関与と判断し、文字起こしのみへ切り替え
  2. `bash scripts/code_conversation.sh --transcript outputs/chosaN/chosaN.json --ai_events outputs/coding/chosaN/ai_events.json --speaker_roles "SPEAKER_00=同行者,SPEAKER_01=視覚障害者" --output outputs/coding/chosaN/coding.json`
- **文字起こしのみ**(上記条件を満たさない調査、およびインタビュー):
  `bash scripts/code_conversation.sh --transcript <transcript.json> --speaker_roles "SPEAKER_00=同行者,SPEAKER_01=視覚障害者" --output outputs/coding/<name>/coding.json`
  - インタビューは `--speaker_roles "SPEAKER_00=同行者,SPEAKER_01=視覚障害者,SPEAKER_02=実験者" --chunk_minutes 10`
- `code_conversation.sh` はホスト側で実行する(codex CLI を使うため)。ホストに `python` コマンドが無い場合は python3 へのシムを PATH に用意する
- 各実行で `Validation succeeded` が出ることを確認。失敗したらエラー内容を報告し、他のファイルの処理は続行

### 4. 可視化・成果物の配置と報告

- **可視化レポートを生成する**(コーディングが1件でも成功した場合は必須):
  `docker compose exec -T backend uv run src/backend/coding/visualize_coding.py --coding "調査1=outputs/coding/chosa1/coding.json" ...(成功した全ファイルを表示順に) "インタビュー=outputs/coding/interview/coding.json" --audio "調査1=audios/num_speakers_2/chosa1.wav" ...(あるもののみ) --subtitle "<セッション名と日付>" --output outputs/coding/coding_summary.html`
  - 各録音の区間ラベル時間(録音時間比)とイベント件数ヒートマップの HTML が生成される。最終報告にこのパスを必ず記載する
- 各 coding.json のフロントエンドコピー(スクリプトが自動配置)を確認
- **最終報告**(これが成果物)を以下の表形式でまとめる:
  - ファイルごと: 発話数 / コーディングモード(AI付き・文字起こしのみ) / 区間ラベル分布 / イベントラベル分布 / 警告(チャンネル異常・アライメント低信頼・ブラケット欠落・検証エラー)
- リポジトリへのコミットはしないこと

## 注意

- すべてローカルモデル(qwen)を使う。Gemini などの外部 ASR は使わない
- 既存の `outputs/` に同名の結果がある場合は上書きしてよい
- 途中で1ファイルが失敗しても止まらず、残りを処理して失敗を報告する
