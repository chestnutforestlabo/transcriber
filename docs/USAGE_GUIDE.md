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

計算機: **arata**(RTX 4090、主力)

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
- 各行に **区間 / イベント** のバッジが付く。区間=時間帯のラベル(会話・無言など)、イベント=発話単位のラベル
- 各項目で: ラベル付け替え / 開始・終了時刻の修正 / **✓確認** / **✗要修正** / メモ
- イベント行では**タグチップ**(周囲の話題)と**属性チップ**(周囲説明の自発/質問応答)をクリックで付け外しできる
  - 1つの発話に複数ラベルが該当する場合(新話題を開く質問、AI情報の共有など)は、**同じ時刻範囲のイベントを複数付与**する(「ラベル追加」で行を足す)。旧「併記」(attrs.co_labels)方式は廃止
- **AIが拾わなかった箇所へのラベル追加**: ヘッダー下の「ラベル追加」で種別(イベント/区間)・ラベル・話者を選び、音声を該当位置まで再生して「◯:◯◯ に追加」を押す
  - 追加行には「手動」バッジが付き、`source: "human"` で記録される(LLM 付与分と区別可能)
  - 手動行は発話内容をその場で入力でき、ゴミ箱ボタンで削除できる(LLM 行の取り消しは ✗要修正 で)
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

反映ルール: **✗要修正の項目は集計から除外**、ラベル・時刻の修正値と手動追加行はそのまま反映、各録音に「レビュー済み n 件・要修正除外 m 件・手動追加 k 件」が注記される。複数ラベルの発話は複数イベントとして各ラベルの件数へ直接カウントされる。区間はサマリーでは 会話/無言/AI応答(Q&A使用窓)のみ集計(システム停止はタイムライン表示専用)。

### 参加者横断の条件比較(箱ひげ図)

複数参加者ぶんの結果が揃ったら、**同じ指標を条件(調査1〜5)間で比較する**箱ひげ図レポートを生成できる(箱=参加者間の分布、○=各参加者、◆=平均、μ/σ² 表示、指標はプルダウン切替)。

- **退避は自動**: 全自動パイプラインが完了時に `outputs/participants/<参加者ID>/` へ結果をコピーする。参加者IDはセッションフォルダ名(プロンプト末尾に「参加者ID: P01」を書けばそちらが優先)。同じ参加者の再実行は旧アーカイブを置き換える
- **レビューを反映したい場合**: その参加者の review.json を `outputs/participants/<ID>/reviewed/` に置く(ファイル名は任意、中の audio 名で chosaN に自動対応付け)。置いたものが coding.json より優先される
- 生成:
   ```bash
   ssh arata 'cd ~/transcriber/environments && docker compose exec -T backend uv run src/backend/coding/visualize_conditions.py --auto outputs/participants --output outputs/coding/conditions_summary.html'
   ```

指標: 各イベントラベルの件数(8種)/周囲の話題タグ件数/会話・無言・AI応答の時間(秒)/会話時間の割合(%)。条件の提示順を参加者間でカウンターバランスする場合は、調査N=条件の対応表を別途管理すること(現状は調査N軸のまま表示)。

---

## 5. アプリログの確認(LogViewer)

アプリの JSONL ログ(セッション開始/停止、AI 発話、Q&A、フレーム送受信、送信画像)を GUI で確認できる。
場所: **sightseeing_AI リポジトリの `Tools/LogViewer`**(Mac で実行、依存なし)。

### 起動

```bash
cd ~/Desktop/sightseeing_AI/Tools/LogViewer
python3 server.py ~/Desktop/ドライラン/logs --open
```

引数はログファイルまたはフォルダ(再帰検索)。`--open` でブラウザが自動で開く(既定ポート 8765、`--port` で変更可)。

### 使い方

- **単一ログ**: ファイル名をクリック → セッションの詳細(VLM リクエスト/レスポンス本文、送信フレーム画像、Q&A の質問と回答、レイテンシ、エラー)を確認できる
- **統合タイムライン**: チェックボックスで複数ログを選択(「全選択」/ Shift+クリックで範囲選択)→「統合タイムライン」に切り替え
  - ログごとのレーンにイベントが色分け表示(SESSION / SPEECH / Q&A / LIVE VLM / EXPERIMENT)
  - **ログ間・ログ内の空白が「停止 ◯分◯秒」の斜線バンド**で見える(実験中の一時停止の把握に)
  - イベントをクリックすると既存の詳細カードへ飛ぶ
- **時間軸の原点指定**: 原点入力欄に録音開始時刻(例 `18:32:53`)を入れて「適用」→ 全イベントが「**録音開始からの経過時間**」表示になり、**文字起こしのタイムスタンプと直接読み合わせられる**。「先頭時刻にリセット」で絶対時刻(JST)表示へ戻る

### コツ

- **1実験分(同日)のログだけ選ぶ**と見やすい。日をまたぐログを混ぜると夜間の巨大な停止バンドに軸が圧縮される(実害はない)
- コーディング結果の検証で「この AI 発話は本当にこの時刻か?」を確かめたいときは、原点に該当録音の開始時刻を入れて、ビューア(transcriber 側)の文字起こし時刻と突き合わせるのが早い

---

## 補足・トラブルシューティング

- **LLM コーディングは実行ごとに数件揺れる**。論文等の確定値は必ずレビュー後の値を使う
- **実験開始ボタンの押し忘れ**: 問題ない(録音窓フォールバック+sidecar/times.json で同期)
- **録音開始時刻が全く分からない**: ログ内 Q&A の質問文と文字起こしの内容マッチングで±1秒まで復元可能(Claude に依頼)
- **相手の発言が二重に文字起こしされる**: `--channel_crosstalk_threshold_db -9`(除去強め)。逆に小声が消えるなら `-3`
- **インタビューなど至近距離の録音**はクロストークが強いので `-9` 推奨
- ASR モデルは qwen(Qwen3-ASR)が既定。whisper 使用時は `--asr_model_name openai --asr_beam_size 5 --asr_initial_prompt "固有名詞リスト"`
- 実験用アプリ「観光AI実験」: シングルタップ=開始/停止、アクションボタン=Q&A、プロンプトはブランド補足付き店舗説明で固定
