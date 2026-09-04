import "dotenv/config";
import { GoogleGenAI } from "@google/genai";

const apiKey = process.env.GEMINI_API_KEY;
const model = process.env.GEMINI_MODEL || "gemini-3.8-flash";

if (!apiKey) {
  console.error(
    "GEMINI_API_KEY が設定されていません。.env.example を .env にコピーしてキーを設定してください。"
  );
  process.exit(1);
}

const ai = new GoogleGenAI({ apiKey });

const response = await ai.models.generateContent({
  model,
  contents: "この接続テストに一言だけ日本語で応答してください。",
});

console.log(`[model: ${model}] 応答:`, response.text);
