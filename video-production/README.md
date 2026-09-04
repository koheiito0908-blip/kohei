# video-production

YouTube動画の編集構造をGemini APIで分析し、その構造(テンポ、テロップ、カット割り、
音の入れ方など)を再利用してオリジナル動画を制作するための作業環境です。

## セットアップ

```bash
cd video-production
npm install
cp .env.example .env
# .env を開いて GEMINI_API_KEY にGoogle AI Studioで取得したキーを設定
npm run test:gemini
```

## 動画分析

```bash
npm run analyze -- "https://www.youtube.com/shorts/xxxxxxxxxxx" analysis/video-analysis.json
```

GeminiにYouTube URLを直接渡して分析します(動画ファイルを手元にダウンロードする必要は
ありません)。結果は `video_specific`(動画固有の内容)と `editing_rules`(他の動画にも
転用できる編集ルール)に分けて `analysis/` 以下にJSONで保存されます。

## ディレクトリ構成

```
video-production/
  scripts/
    test-gemini.mjs      # APIキーの疎通確認
    analyze-video.mjs     # YouTube動画をGeminiで分析しJSON保存
  analysis/                # Geminiの分析結果(JSON)
  output/                  # 生成した検証動画・完成動画の出力先
```

## 注意

- `.env` はコミットしないでください。
- 元動画の台本・素材・ナレーション・固有表現をそのまま複製すると著作権上の問題に
  つながる可能性があります。参考にするのはあくまで編集構造(タイミングやリズムの
  ルール)です。
