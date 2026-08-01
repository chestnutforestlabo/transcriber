# 実験データ処理 運用ガイド(録音 → 文字起こし → コーディング → 可視化)

sightseeing_AI 実験の録音から分析用データまでの全手順。2026-08-01 時点の構成。

## 全体像

```
録音(DJI 2ch + ボイスメモ)          … 人間
  ↓ フォルダにまとめて arata へ scp   … 人間(準備はここまで)
文字起こし(qwen・話者=チャンネル)     … 自動
コーディング(LLM ラベル付け)          … 自動
可視化(coding_summary.html)          … 自動
  ↓
レビュー(ビューアで確認・修正)        … 人間
可視化の再生成(レビュー反映)          … 1コマンド
インタビュー Q&A 要約                … 1コマンド
```

計算機: **arata**(RTX 4090、主力)/ **yagami-zbox**(RTX 3080、予備)。どちらも同一環境(docker + `/home/<user>/transcriber`)。以下は arata 表記。

---

## 1. 録音の取り方

### 機材と装着(固定ルール)

| 機材 | 装着者 | チャンネル | 出力ラベル |
|---|---|---|---|
| DJI TX1 | **同行者** | Lch | SPEAKER_00 |
| DJI TX2 | **視覚障害者** | Rch | SPEAKER_01 |
| ボイスメモ(mono) | 実験者(インタビュー時) | 第3ch | SPEAKER_02 |

- **RX(受信機)は必ずステレオモード**(TX1→L, TX2→R)。モノミックスだと話者分離が成立しない
- TX のノイズキャンセリングは弱め
- **AI の読み上げはイヤホン(AirPods)で聞く**(録音に混ぜない)
- TX 本体に「1」「2」をテープで明示しておくと取り違えない

### 録音方法

**推奨: Mac + 付属スクリプト**(時刻が自動記録され、後工程が全自動になる):

```bash
cd ~/Desktop/transcriber && ./scripts/record_mac_dji.sh
```

- 引数なしでデバイス一覧 → DJI RX を選択 → Ctrl-C で停止
- `rec_日時.wav`(48kHz/2ch)と **`rec_日時.time.json`(開始時刻 sidecar)** が生成される。この sidecar があればログとの時刻同期は全自動

**ボイスメモで録る場合**(iPhone 等): 録音自体は問題ないが、**開始時刻が残らない**ので、後で `times.json`(ファイル名→開始時刻)を書くか、AI 関与なしの録音(ベースライン等)として扱う。

### インタビューの録音

- ユーザ2人: DJI 2ch(上と同じ)
- 実験者: 自分の iPhone のボイスメモ(モノラル)
- 開始タイミングは揃えなくてよい(後処理の相互相関で自動アライメント)。心配なら開始時に1回手を叩く

### アプリ側

- 操作は不要(ログは自動記録)。設定画面の「実験開始を記録」ボタンは**押せれば理想だが、押し忘れても録音窓フォールバックで処理できる**

### 録音後のチェック(任意だが推奨)

```bash
ffprobe -v error -show_entries stream=channels -of default=nw=1 録音ファイル.m4a
```

調査系は `channels=2`、実験者側は `1` であること。

---

## 2. 文字起こし〜コーディング〜可視化(自動パイプライン)

### 人間の準備

セッションフォルダを作って arata に送る:

```
セッションフォルダ/
├── 調査1.m4a … 調査5.m4a          # 2ch
├── 実験後インタビュー（ユーザ側）.m4a   # 2ch
├── 実験後インタビュー(実験者側).m4a    # 1ch
├── logs/*.jsonl                    # アプリログ(あれば)
└── times.json または *.time.json    # 録音開始時刻(あれば)
```

`times.json` の例:

```json
{"調査2": "2026-07-31T18:22:47+09:00", "調査3": "2026-07-31T18:32:53+09:00"}
```

転送:

```bash
scp -r セッションフォルダ arata:/home/arata/sessions/2026-08-15
```

### 実行(1コマンド)

```bash
ssh arata 'cd /home/arata/transcriber && codex exec --sandbox danger-full-access "$(cat docs/AUTO_PIPELINE_PROMPT.md)

対象セッションフォルダ: /home/arata/sessions/2026-08-15"'
```

これで以下が全部走る(ドライランで実測 約2時間):

1. チャンネル検証・wav 変換
2. **qwen 文字起こし**(調査=2ch 分離、インタビュー=擬似3ch 自動アライメント)
3. **コーディング**(ログ+開始時刻がある調査は AI イベント付き、それ以外は文字起こしのみモード)
4. スキーマ検証・ビューアへの配置
5. **可視化 `outputs/coding/coding_summary.html`** 生成
6. サマリー表の報告(発話数・ラベル分布・警告)

### 個別に手動実行したい場合

```bash
# 文字起こし(2ch)
docker compose exec -T backend uv run src/backend/transcribe.py \
  --audio_dir audios/num_speakers_2 --asr_model_name qwen --channel_mode
# 文字起こし(擬似3ch)
docker compose exec -T backend uv run src/backend/transcribe.py \
  --audio_dir audios/num_speakers_3 --asr_model_name qwen --channel_mode --aux_audio interview_aux.wav
# AIイベント抽出(ログ+開始時刻があるとき)
docker compose exec -T backend uv run src/backend/coding/prepare_ai_events.py logs/*.jsonl \
  --audio audios/num_speakers_2/chosa3.wav --recording_start "2026-07-31T18:32:53+09:00" \
  --output outputs/coding/chosa3/ai_events.json
# コーディング(--ai_events は任意)
bash scripts/code_conversation.sh --transcript outputs/chosa3/chosa3.json \
  --ai_events outputs/coding/chosa3/ai_events.json \
  --speaker_roles "SPEAKER_00=同行者,SPEAKER_01=視覚障害者" \
  --output outputs/coding/chosa3/coding.json
# 可視化
docker compose exec -T backend uv run src/backend/coding/visualize_coding.py \
  --auto outputs/coding --output outputs/coding/coding_summary.html
```

---

## 3. インタビューの Q&A 要約(codex)

実験者の各質問に2人がどう答えたかの Markdown レポートを生成:

```bash
ssh arata 'cd /home/arata/transcriber && codex exec --sandbox workspace-write "$(cat docs/INTERVIEW_SUMMARY_PROMPT.md)

入力の文字起こし JSON: outputs/interview/interview.json
出力パス: outputs/interview_summary.md"'
```

- 質問ごとに: 実験者の発話 / 同行者の回答 / 視覚障害者の回答 / 特記(時刻付き引用)
- SUS 等の評定値は数値のまま記録。不確実な箇所は明示される

---

## 4. コーディングの確認と可視化の更新

### レビュー(ビューア)

```bash
ssh -N -L 5175:localhost:5173 arata
```

を実行したまま、ブラウザで http://localhost:5175 を開く
(初回のみ arata 側で `cd ~/transcriber/environments && docker compose up -d frontend`)。

- 音声を選ぶと、波形+文字起こし+**コーディングレーン**(会話/無言/AI説明/AI応答/システム停止/イベント)が表示される
- 各項目で: ラベル付け替え / 開始・終了時刻の修正 / **✓確認** / **✗要修正** / メモ
- 終わったら「**エクスポート**」→ `<名前>.review.json` がダウンロードされる

### 可視化への反映

1. エクスポートした review.json を arata の `~/transcriber/outputs/coding/reviewed/` に置く(ファイル名は任意、自動対応付け):
   ```bash
   scp ~/Downloads/調査1.review.json arata:/home/arata/transcriber/outputs/coding/reviewed/
   ```
2. 再生成:
   ```bash
   ssh arata 'cd ~/transcriber/environments && docker compose exec -T backend uv run src/backend/coding/visualize_coding.py --auto outputs/coding --reviewed outputs/coding/reviewed --output outputs/coding/coding_summary.html'
   ```

反映ルール: **✗要修正の項目は集計から除外**、ラベル・時刻の修正値はそのまま反映、各録音に「レビュー済み n 件・要修正除外 m 件」が注記される。

---

## 補足・トラブルシューティング

- **LLM コーディングは実行ごとに数件揺れる**。論文等の確定値は必ずレビュー後の値を使う
- **実験開始ボタンの押し忘れ**: 問題ない(録音窓フォールバック+sidecar/times.json で同期)
- **録音開始時刻が全く分からない**: ログ内 Q&A の質問文と文字起こしの内容マッチングで±1秒まで復元可能(Claude に依頼)
- **相手の発言が二重に文字起こしされる**: `--channel_crosstalk_threshold_db -9`(除去強め)。逆に小声が消えるなら `-3`
- **インタビューなど至近距離の録音**はクロストークが強いので `-9` 推奨
- ASR モデルは qwen(Qwen3-ASR)が既定。whisper 使用時は `--asr_model_name openai --asr_beam_size 5 --asr_initial_prompt "固有名詞リスト"`
- アプリログの複数ファイルを俯瞰したいとき: sightseeing_AI 側の `Tools/LogViewer`(`python3 server.py <logsフォルダ> --open`)で統合タイムライン表示
- 実験用アプリ「観光AI実験」: シングルタップ=開始/停止、アクションボタン=Q&A、プロンプトはブランド補足付き店舗説明で固定
