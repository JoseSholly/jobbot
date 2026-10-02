/** Gemini REST client (Google AI Studio free tier). */
export class GeminiClient {
  constructor(
    private readonly apiKey: string,
    private readonly model = "gemini-2.5-flash",
    private readonly fetchFn: typeof fetch = fetch,
  ) {}

  async generate(prompt: string, temperature = 0.4): Promise<string> {
    // Call fetch detached from `this`: Workers throw "Illegal invocation" otherwise.
    const doFetch = this.fetchFn;
    const res = await doFetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${this.model}:generateContent`,
      {
        method: "POST",
        headers: { "content-type": "application/json", "x-goog-api-key": this.apiKey },
        body: JSON.stringify({
          contents: [{ role: "user", parts: [{ text: prompt }] }],
          generationConfig: { temperature },
        }),
      },
    );
    if (!res.ok) throw new Error(`gemini ${res.status}: ${(await res.text()).slice(0, 200)}`);
    const data = (await res.json()) as {
      candidates?: { content?: { parts?: { text?: string }[] } }[];
    };
    const text = data.candidates?.[0]?.content?.parts?.map((p) => p.text ?? "").join("") ?? "";
    if (!text.trim()) throw new Error("gemini returned no text");
    return text.trim();
  }
}
