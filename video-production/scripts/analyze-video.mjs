import "dotenv/config";
import { writeFile } from "node:fs/promises";
import { GoogleGenAI } from "@google/genai";

const apiKey = process.env.GEMINI_API_KEY;
const model = process.env.GEMINI_MODEL || "gemini-3.8-flash";
const youtubeUrl = process.argv[2];
const outPath = process.argv[3] || "analysis/video-analysis.json";

if (!apiKey) {
  console.error(
    "GEMINI_API_KEY が設定されていません。.env.example を .env にコピーしてキーを設定してください。"
  );
  process.exit(1);
}

if (!youtubeUrl) {
  console.error("使い方: npm run analyze -- <YouTube URL> [出力パス]");
  process.exit(1);
}

const prompt = `以下のYouTube Shorts動画を、映像・音声の両方から詳細に分析してください。
出力は必ず次のキーを持つJSONのみとし、それ以外のテキストは含めないでください。

{
  "video_specific": {
    // この動画固有の内容(セリフ、テロップの文言、登場する固有名詞など)
  },
  "editing_rules": {
    // 他の動画にも転用できる、再利用可能な編集ルール
    // (カット割りのタイミング、テロップの出現/消去パターン、
    //  カメラ/要素の動き、BGM・効果音の入れ方、テンポの変化など)
  },
  "timeline": [
    // 開始秒・終了秒ごとのシーン単位の分解
  ]
}`;

const ai = new GoogleGenAI({ apiKey });

const response = await ai.models.generateContent({
  model,
  contents: [
    {
      role: "user",
      parts: [
        { fileData: { fileUri: youtubeUrl } },
        { text: prompt },
      ],
    },
  ],
});

const raw = response.text.trim();
const jsonText = raw.replace(/^```json\s*/i, "").replace(/```\s*$/, "");

let parsed;
try {
  parsed = JSON.parse(jsonText);
} catch (err) {
  console.error("Geminiの応答をJSONとして解析できませんでした。生の応答を保存します。");
  parsed = { raw_response: raw };
}

await writeFile(outPath, JSON.stringify(parsed, null, 2), "utf-8");
console.log(`分析結果を ${outPath} に保存しました。`);
