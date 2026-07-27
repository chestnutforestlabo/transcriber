# BUT DiariZen

`BUT-FIT/diarizen-wavlm-large-s80-md-v2` を使うダイアライゼーション
バックエンドです。モデル重みのライセンスは **CC BY-NC 4.0** であり、
非商用利用に限定されます。

DiariZen 本家が同梱する pyannote.audio 3.1.1 は、既存の
`pyannote/speaker-diarization-community-1` が必要とする pyannote.audio 4
と共存できません。このバックエンドは DiariZen のモデル構造を読み込み、
pyannote.audio 4 の VBx/PLDA パイプラインで実行する互換アダプターを使用します。
これにより既存 community バックエンドと同じ環境で利用できます。
