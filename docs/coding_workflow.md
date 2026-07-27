# 実験会話コーディングの運用手順

## 1. 実験時の同期プロトコル

録音開始と同時に sightseeing_AI の実験開始操作を行い、
`experiment_start` を記録します。同じ瞬間に実験者が「スタート」と発声し、
録音にも同期点を残してください。

終了時も同様に、アプリの実験終了操作で `experiment_end` を記録すると同時に
「ストップ」と発声します。後処理では、文字起こしまたは波形で確認した
「スタート」の録音内時刻を同期アンカーに使います。

## 2. アプリログの転送

Mac から実行環境へ JSONL ログを転送します。

```bash
scp logs/*.jsonl arata:/home/arata/transcriber/coding_inputs/
```

ログは最大75 MBになるため、前処理は行単位で読み込みます。
`live_vlm_request`、`qa_vlm_request`、`scene_request` の `frames` は
JSONデコード前に読み捨てます。

## 3. 2ch録音の文字起こし

DJI Mic Mini 2 のRXをステレオ（TX1→L、TX2→R）にして録音し、
WAVを `audios/num_speakers_2/` に配置します。Goal 2 のチャンネル分離モードで
文字起こしします。

```bash
uv run src/backend/transcribe.py \
  --audio_dir audios/num_speakers_2 \
  --audio_files walk01.wav \
  --asr_model_name openai \
  --channel_mode
```

出力は `outputs/walk01/walk01.json`、レビュー用音声は
`src/frontend/public/audios/walk01.wav` に保存されます。

## 4. AIイベントの前処理

録音内の「スタート」発声が12.5秒の場合は、次のようにv2ログを前処理します。
ログは複数指定でき、UTC時刻順にマージされます。

```bash
python src/backend/coding/prepare_ai_events.py \
  coding_inputs/app-part1.jsonl coding_inputs/app-part2.jsonl \
  --audio src/frontend/public/audios/walk01.wav \
  --sync "audio=12.5,log=experiment_start"
```

絶対録音開始時刻が分かる場合は、同期アンカーの代わりに
`--recording_start "2026-07-23T14:11:20+09:00"` も指定できます。
結果は既定で `outputs/coding/walk01/ai_events.json` に保存されます。

`log_meta` や `speech_end` がないv1ログは自動判定しません。パイロットデータを
処理するときだけ `--legacy` を明示してください。この場合に限り、
AI発話の終了時刻を6.5文字/秒で推定します。

## 5. Codexによるコーディング

話者と実験上の役割を指定して実行します。

```bash
bash scripts/code_conversation.sh \
  --transcript outputs/walk01/walk01.json \
  --ai_events outputs/coding/walk01/ai_events.json \
  --speaker_roles "SPEAKER_00=視覚障害者,SPEAKER_01=同行者"
```

スクリプトは決定論的なスキャフォールドを含むプロンプトを作り、
`codex exec --sandbox workspace-write` を実行します。結果をスキーマ検証してから
`outputs/coding/walk01/coding.json` と
`src/frontend/public/coding/walk01.json` に保存します。検証に失敗した場合は
Codexの生出力と検証エラーを表示し、フロントエンドへコピーせず終了します。

長時間録音を分割するときは、たとえば30分単位を指定します。

```bash
bash scripts/code_conversation.sh \
  --transcript outputs/walk01/walk01.json \
  --ai_events outputs/coding/walk01/ai_events.json \
  --speaker_roles "SPEAKER_00=視覚障害者,SPEAKER_01=同行者" \
  --chunk_minutes 30
```

隣接する参照窓は境界部分を合計60秒重複させ、検証済みJSONを中核時間窓で
切り出して時刻順にマージします。

## 6. フロントエンドでの検証とエクスポート

```bash
bash scripts/frontend.sh
```

対象音声を選ぶと、対応する `public/coding/<basename>.json` がある場合だけ
波形下のコーディングレーンとレビュー一覧が表示されます。区間バンド、
イベントマーカー、または一覧項目をクリックすると該当時刻へ移動します。

各項目について、ラベルと開始・終了時刻を調整し、「✓確認」または
「✗要修正」を選び、必要に応じてメモを記入します。「エクスポート」を押すと、
各区間・イベントに `review` を追加した `<basename>.review.json` を
ブラウザからダウンロードできます。
