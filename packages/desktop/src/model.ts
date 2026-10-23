export const PROVIDERS = ["openai", "deepseek", "qwen", "kimi", "glm", "ollama"] as const;
export type Provider = (typeof PROVIDERS)[number];

export function canContinue(provider: Provider, apiKey: string): boolean {
  if (provider === "ollama") return true;
  return apiKey.trim().length > 0;
}
