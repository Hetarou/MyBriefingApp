// Cloudflare Pages Function: POST /api/generate-questions
//
// Proxies a quiz-question request to the Gemini API. The API key lives only
// in this server-side environment (Cloudflare Pages "Environment variables"),
// never in client code. The client sends a fixed topic id (not free text),
// so there is no user-controlled text in the prompt at all.
//
// Rate limiting is layered (per-IP hourly + global daily) via a KV
// namespace bound as QUIZ_KV, to keep a public, unauthenticated endpoint
// from running up API usage if the URL is ever found by someone else.

const ALLOWED_TOPICS = ["英単語", "世界史", "数学", "プログラミング", "生物"];
const MODEL = "gemini-3.6-flash";
const IP_HOURLY_LIMIT = 20;
const GLOBAL_DAILY_LIMIT = 100;

function jsonError(message, status) {
  return Response.json({ error: message }, { status });
}

async function checkAndIncrement(kv, key, limit, ttlSeconds) {
  const current = parseInt((await kv.get(key)) || "0", 10);
  if (current >= limit) return false;
  await kv.put(key, String(current + 1), { expirationTtl: ttlSeconds });
  return true;
}

function buildPrompt(topic) {
  return (
    `日本語の学習アプリ向けに、「${topic}」というジャンルの一問一答クイズを3問作成してください。\n` +
    "条件:\n" +
    "- question は1文の簡潔な問題文\n" +
    "- answer は簡潔な解答（1〜2文程度）\n" +
    "- 難易度は高校生〜一般教養レベル\n" +
    "- 指定されたJSONスキーマの形式で出力すること"
  );
}

export async function onRequestPost(context) {
  const { request, env } = context;

  if (!env.GEMINI_API_KEY || !env.QUIZ_KV) {
    return jsonError("サーバー設定エラー", 500);
  }

  let body;
  try {
    body = await request.json();
  } catch (e) {
    return jsonError("リクエストの形式が正しくありません", 400);
  }

  const topic = body && body.topic;
  if (typeof topic !== "string" || !ALLOWED_TOPICS.includes(topic)) {
    return jsonError("不正なトピックです", 400);
  }

  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const now = new Date();
  const hourKey = `rate:ip:${ip}:${now.toISOString().slice(0, 13)}`;
  const dayKey = `rate:global:${now.toISOString().slice(0, 10)}`;

  const ipOk = await checkAndIncrement(env.QUIZ_KV, hourKey, IP_HOURLY_LIMIT, 3600);
  if (!ipOk) return jsonError("しばらく時間をおいてから試してください", 429);

  const globalOk = await checkAndIncrement(env.QUIZ_KV, dayKey, GLOBAL_DAILY_LIMIT, 60 * 60 * 24 * 2);
  if (!globalOk) return jsonError("本日の生成回数の上限に達しました", 429);

  const requestBody = {
    contents: [{ role: "user", parts: [{ text: buildPrompt(topic) }] }],
    generationConfig: {
      responseMimeType: "application/json",
      responseSchema: {
        type: "object",
        properties: {
          questions: {
            type: "array",
            items: {
              type: "object",
              properties: {
                question: { type: "string" },
                answer: { type: "string" },
              },
              required: ["question", "answer"],
            },
          },
        },
        required: ["questions"],
      },
      temperature: 0.9,
      maxOutputTokens: 800,
    },
  };

  let geminiRes;
  try {
    geminiRes = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${env.GEMINI_API_KEY}`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(requestBody),
      }
    );
  } catch (e) {
    return jsonError("生成に失敗しました", 502);
  }

  if (!geminiRes.ok) {
    return jsonError("生成に失敗しました", 502);
  }

  let data;
  try {
    data = await geminiRes.json();
  } catch (e) {
    return jsonError("生成結果の解析に失敗しました", 502);
  }

  let questions;
  try {
    const text = data.candidates[0].content.parts[0].text;
    questions = JSON.parse(text).questions;
  } catch (e) {
    return jsonError("生成結果の形式が不正です", 502);
  }

  if (!Array.isArray(questions)) {
    return jsonError("生成結果の形式が不正です", 502);
  }

  const clean = questions
    .filter((q) => q && typeof q.question === "string" && typeof q.answer === "string")
    .slice(0, 3)
    .map((q) => ({ topic, question: q.question.trim(), answer: q.answer.trim() }));

  if (clean.length === 0) {
    return jsonError("生成結果が空でした", 502);
  }

  return Response.json({ questions: clean });
}
