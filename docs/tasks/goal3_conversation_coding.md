# Goal 3: 実験会話のコーディング(ラベル付け)パイプラインとレビュー用ビューア

## 背景

視覚障害者と同行者(晴眼者)が観光地を歩きながら AI ガイドアプリ(sightseeing_AI)を使う実験を行う。
2人の会話は DJI Mic Mini 2 の 2ch 録音(Goal 2 のチャンネル分離モード)で文字起こしされ、AI の発話・状態はアプリの JSONL ログに記録される。
この2つを突き合わせて、以下のコーディングスキームに従ったラベル付けを LLM(codex)が行い、人間がビューアで音声を聞きながら検証する。

## コーディングスキーム(この表を docs/coding_scheme.md としてリポジトリに保存すること)

| ラベル名 | 種別 | ラベル内容 | 定義・運用ルール |
| --- | --- | --- | --- |
| 会話 | 区間 | 人間同士の会話区間 | 発話に応答があった時点から、発話・呼びかけが3秒以上途切れるまで。相槌も応答に含める。AI宛発話(Q&A)は算入しない |
| 無言 | 区間 | 人間の発話がない区間 | 会話・呼びかけが3秒以上ない時。AI説明中でも人間が無言なら併記 |
| AI説明 | 区間 | AIの自発ナレーション | ログから自動付与。Q&Aへの回答は含めない |
| AI応答 | 区間 | Q&Aに対するAIの回答 | ログから自動付与 |
| 視覚障害者からの話題提示 | イベント | 視覚障害者が新しい話題を出した発話 | 質問形でも新話題なら併記。ガイド発話は除く |
| 同行者からの話題提示 | イベント | 同行者が新しい話題を出した発話 | 同上 |
| 視覚障害者から同行者への質問 | イベント | 同行者への質問 | 新しい話題を開始する場合は話題提示も併記 |
| 同行者から視覚障害者への質問 | イベント | 視覚障害者への質問 | 同上 |
| AI情報の共有 | イベント | AIの発話内容をもとにした話題提示・質問 | AIへの明示言及(「AIが言ってた〜」等)、またはAI発話終了後30秒以内かつ内容が一致する場合。話題提示か質問を必ず併記 |
| 周囲の話題 | タグ | 発話内容が周囲環境についての場合に併記 | 話題提示・質問・AI情報の共有・周囲説明と併用可。ベースライン条件でも付与する。会話量を評価するのに使用する |
| 同行者からの周囲説明 | イベント | 同行者が周囲の視覚情報を説明した発話 | 自発か、視覚障害者の質問への応答かを属性で記録 |
| 応答なし発話 | イベント | 3秒以内に応答(相槌含めて)がなかった発話・呼びかけ | 話題提示・質問がスルーされた場合に付与 |
| ガイド発話 | イベント | 同行者からのナビ・安全のための発話(「段差がある」等) | 観光的会話と分けて集計するため。話題提示には数えない |
| システム停止 | 区間 | 一時停止されていた区間 | ログから自動付与 |

## 入力データの仕様(調査済みの事実)

### 1. 文字起こし JSON(transcriber の出力)

`outputs/<basename>/<basename>.json`: `[{"start": 秒, "end": 秒, "speaker": "SPEAKER_00", "text": "..."}]`
- 話者→役割の対応は実行時引数で与える(例: `--speaker_roles "SPEAKER_00=視覚障害者,SPEAKER_01=同行者"`)。
- AI の読み上げは**イヤホン**で聞くため録音・文字起こしには入らない。文字起こしに現れるのは人間2人の発話のみであり、AI 発話の情報源はアプリログだけである(混入除外の処理は不要)。

### 2. アプリログ JSONL(sightseeing_AI)

- 1行1イベント。`at` は **UTC** の ISO8601(`2026-07-23T05:11:16Z`)。実験は JST(+9)。
- ファイルは最大 75MB。`live_vlm_request` / `qa_vlm_request` / `scene_request` の `frames`(base64画像)が巨大なので、**必ず1行ずつストリーム処理し、`frames` は読み捨てる**こと。全体を json.load しない。
- **ログスキーマ v2(本パイプラインの前提)**: アプリ側(sightseeing_AI リポジトリの docs/tasks/logging_for_experiment_coding.md)で以下が実装される。ファイル先頭の `log_meta` {schema_version: 2, app_version} で判別できる。
  - `speech_start` {at, id, text, kind: "scene"|"qa_answer"|"deepdive"|"tsunagi"|"system"} — AI読み上げ開始(本文・種別つき)
  - `speech_end` {at, id, reason: "finished"|"cancelled"} — AI読み上げ終了。`speech_start` と同じ `id` でペアになる。**区間はこのペアから正確に決まる(推定はしない)**
  - `speech_yield` {at, active: true/false} — 人の話し声検出による読み上げの自動一時停止/再開
  - `experiment_start` / `experiment_end` {at} — 実験者による実験ブラケットの明示マーク
  - `session_start` {at, input, model, prompt_mode} / `session_stop` {at, reason: "user"|"background"|"error"} — ガイドの開始/停止
  - `qa_start` {at, topics} → `qa_heard` → `qa_ask` {topicIndex} → `qa_vlm_request` {question} → `qa_vlm_response` {speech_output} → `qa_result` — Q&A フロー。`question` がユーザーの質問
  - その他(`live_vlm_*`, `prompt_mode_change`, `scene_*`, `startup_liveness`, `explanation_history_reset`)はコーディングには直接使わない
- kind → ラベルの対応: `scene` → AI説明、`qa_answer`・`deepdive` → AI応答、`system`・`tsunagi` → どちらにも含めない(参考情報として ai_events に残す)
- **レガシーログ(v1、2026-07-23 のパイロットデータ等、log_meta も speech_end も無い)**: `--legacy` フラグを明示した場合のみ処理を許可し、終了時刻を文字数 ÷ 6.5文字/秒で推定して `estimated_end: true` を付ける。デフォルト(v2)では推定コードパスを一切通らないこと。v1 では本文が `live_vlm_response.raw_output` の `new_information[].text` / `qa_vlm_response.speech_output` にしかないので、直後(≦1秒)の `speech_start` と時刻対応させる。

### 3. 録音時刻との同期と実験ブラケット

- AI 音声は録音に入らないため、同期アンカーは**実験プロトコル**で作る: 実験者は録音開始と同時にアプリの実験開始操作(`experiment_start` がログに記録される)を行い、**同時に「スタート」と声に出す**。この発声は録音に入る。終了時も `experiment_end` +「ストップ」発声。
- 同期指定: `--sync "audio=12.5,log=experiment_start"`(録音内の「スタート」発声時刻と `experiment_start` イベントを対応付ける)。フォールバックとして `--recording_start "2026-07-23T14:11:20+09:00"`(絶対時刻指定)も受け付ける。
- 「システム停止」区間は **`experiment_start`〜`experiment_end` の間**の `session_stop`(reason: "user")→`session_start` の間隙から導出する。実験ブラケット外のログイベントは全て無視する(実験外のシステム停止を含めないため)。`experiment_start` 時点でセッションが停止中なら、その時点からの「システム停止」区間を生成する。
- レガシーログ(`--legacy`)では実験ブラケットが無いので、録音窓([0, 音声長])でのクリップにフォールバックする。

## 実装してほしいもの

### A. 前処理スクリプト `src/backend/coding/prepare_ai_events.py`

- 入力: ログ JSONL ファイル(複数可、時刻でマージ)、同期情報(上記)、音声ファイルパス(長さ取得用。soundfile 使用)
- 出力: `outputs/coding/<basename>/ai_events.json`
  ```json
  {
    "meta": {"schema_version": 2, "sync": {...}, "duration_sec": 3600.0, "log_files": ["..."],
             "experiment": {"start": 0.0, "end": 3550.0}},
    "ai_utterances": [{"start": 123.4, "end": 130.2, "kind": "scene|qa_answer|deepdive|system|tsunagi",
                       "text": "...", "end_reason": "finished|cancelled", "estimated_end": false}],
    "speech_yields": [{"start": 130.5, "end": 133.0}],
    "qa_interactions": [{"qa_start": 100.0, "question_heard": 103.0, "question": "...", "answer_start": 108.0, "answer_text": "..."}],
    "system_stops": [{"start": 200.0, "end": 260.0}],
    "prompt_modes": [{"time": 0.0, "mode": "atmosphere"}]
  }
  ```
- 全て音声相対秒に変換済み。タイムゾーン変換(UTC→録音基準)はここで完結させる。
- `estimated_end` は `--legacy` 時のみ true になりうる。v2 では speech_start/speech_end ペアの実測値のみ。
- 純粋な Python(LLM 不使用・決定論的)。pytest 対象。

### B. コーディング実行スクリプト `scripts/code_conversation.sh` + `src/backend/coding/build_coding_prompt.py`

- 入力: 文字起こし JSON、ai_events.json、話者役割対応
- `build_coding_prompt.py` が以下を行う:
  1. 決定論的に計算できるラベルを先に生成(スキャフォールド): 「AI説明」「AI応答」「システム停止」区間(ai_events から)、「会話」「無言」の候補区間(文字起こしの発話ギャップ3秒ルールから機械的に)
  2. docs/coding_scheme.md + スキャフォールド + 文字起こし(話者役割変換済み)+ ai_events を1つのプロンプト(テキストファイル)にまとめる。LLM への指示: 意味的判断が必要なラベル(話題提示/質問/AI情報の共有/周囲の話題/周囲説明/ガイド発話/応答なし発話/相槌判定による会話区間の確定/AI宛発話(Q&A)の会話区間からの除外)を付与し、下記スキーマの JSON **のみ**を出力せよ
- `code_conversation.sh` が `codex exec --sandbox workspace-write` にプロンプトファイルを渡して実行し、出力 JSON を `outputs/coding/<basename>/coding.json` に保存、スキーマ検証(下記 C)を行い、検証済みなら `src/frontend/public/coding/<basename>.json` にもコピーする。
- 長時間録音でプロンプトが大きくなりすぎる場合に備え、`--chunk_minutes N`(デフォルト無効)で時間窓分割+境界60秒オーバーラップ+マージのオプションを用意する。

### C. コーディング結果スキーマと検証 `src/backend/coding/schema.py`

```json
{
  "version": 1,
  "audio": "<basename>.wav",
  "intervals": [
    {"id": "iv-0001", "label": "会話|無言|AI説明|AI応答|システム停止",
     "start": 12.3, "end": 45.6, "source": "auto|llm", "note": ""}
  ],
  "events": [
    {"id": "ev-0001",
     "label": "視覚障害者からの話題提示|同行者からの話題提示|視覚障害者から同行者への質問|同行者から視覚障害者への質問|AI情報の共有|同行者からの周囲説明|応答なし発話|ガイド発話",
     "time": 34.5, "end": 37.2,
     "speaker": "視覚障害者|同行者",
     "tags": ["周囲の話題"],
     "attrs": {"co_labels": ["話題提示"], "response_type": "自発|質問応答", "ai_reference": "explicit|within_30s"},
     "text": "該当発話テキスト", "note": ""}
  ]
}
```
- `schema.py` に検証関数(必須キー・ラベル語彙・時刻の単調性・区間の start<end)を実装し、`code_conversation.sh` から呼ぶ。検証失敗時は codex の出力と共にエラー表示して exit 1。
- ルール表現の注意: 「AI情報の共有」には話題提示か質問の併記が必須(`attrs.co_labels`)。「同行者からの周囲説明」は `response_type` 必須。

### D. フロントエンド(既存 Vite+React)にレビュー用ビューを追加

既存の波形同期文字起こしビューを壊さずに拡張する:

1. 音声選択時に `public/coding/<basename>.json` が存在すればコーディングレーンを表示
2. 波形タイムライン上に、区間ラベルを色分けバンド(会話=緑系、無言=灰、AI説明=青系、AI応答=水色、システム停止=赤系)、イベントをマーカーで表示。クリックでその時刻にシーク
3. 右側(または下部)に時系列リスト: 時刻・ラベル・話者・該当発話テキスト。クリックでシーク、再生中の項目をハイライト。ラベル種別でのフィルタ
4. 人間の検証用: 各項目に「✓確認」「✗要修正」トグルとメモ欄。ラベルの付け替え(セレクトボックス)と時刻の微調整(数値入力)も可能にする
5. 「エクスポート」ボタンで検証状態を含む JSON(`review` フィールドを各項目に追加したもの)をダウンロード

### E. テストとドキュメント

- pytest: 合成ログ JSONL(小さな手書きフィクスチャ)で prepare_ai_events の (a) タイムゾーン変換と --sync アンカー同期 (b) システム停止区間の導出(実験ブラケットでのクリップ、experiment_start 時に停止中のケース) (c) speech_start/speech_end ペアリング(cancelled 含む)と、--legacy 時のみ推定が使われること (d) frames 読み捨てのストリーム処理、をそれぞれ検証
- pytest: schema.py の検証ロジック
- pytest: build_coding_prompt のスキャフォールド(会話/無言の3秒ルール)
- README(または docs/coding_workflow.md)に運用手順を日本語で記載:
  1. 実験時プロトコル: 録音開始と同時にアプリの実験開始操作(experiment_start)+「スタート」と発声。終了時も experiment_end +「ストップ」発声
  2. Mac から `scp logs/*.jsonl arata:/home/arata/transcriber/coding_inputs/` でログを送る
  3. transcriber で 2ch 録音を文字起こし(Goal 2 のチャンネルモード)
  4. `prepare_ai_events.py`(--sync で「スタート」発声時刻を指定)→ `code_conversation.sh` を実行
  5. フロントエンドで音声を聞きながら検証、エクスポート

## 制約

- GPU 不要の作業のみ(LLM 呼び出しは codex CLI、それ以外は純 Python/TS)
- 既存の transcribe フロー・フロントエンド表示の後方互換を維持
- コミットはしないこと(レビュー後に人間がコミットする)
- 変更ファイル一覧と実現できなかった項目を最後に報告すること

## 追補(2026-08-01): 文字起こしのみモード

- ユースケース: ベースライン条件(AI なし)やインタビュー・議論など、アプリログが存在しない/不要な録音のコーディング。
- `build_coding_prompt.py` の ai_events 入力をオプションにする。省略時:
  - スキャフォールドは文字起こし由来の「会話」「無言」候補(3秒ルール)のみ生成
  - プロンプトには「この録音に AI は関与しない。AI説明/AI応答/システム停止/AI情報の共有 は付与対象外」と明記し、人間側ラベル(話題提示・質問・周囲説明・応答なし発話・ガイド発話・周囲の話題タグ・相槌判定による会話区間確定)に集中させる
- `code_conversation.sh` も ai_events 引数を省略可能にする(省略時は prepare をスキップ)。
- スキーマ・ビューアは変更不要(AI 系ラベルが現れないだけ)。
- pytest: ai_events なしでのプロンプト生成と、生成プロンプトに AI 対象外の明記が含まれることを検証。
