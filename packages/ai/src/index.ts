export interface AiRunContract<Input, Output> {
  name: string;
  promptVersion: string;
  timeoutMs: number;
  parseInput: (value: unknown) => Input;
  parseOutput: (value: unknown) => Output;
}

export interface RedactedAiTrace {
  contractName: string;
  promptVersion: string;
  provider: string;
  latencyMs: number;
  validation: "passed" | "failed";
}

export const createTrace = (trace: RedactedAiTrace): RedactedAiTrace => trace;
