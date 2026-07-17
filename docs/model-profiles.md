# Model Profiles

TestData Factory exposes local model profile metadata so users can see the supported local setup names and tradeoffs. The deterministic generation path implemented today does not require a model call, a paid API key, or a hosted cloud service.

Inspect the profiles supported by the current engine:

```bash
tdf models doctor
```

When the API server is running, the same profile metadata is available over HTTP:

```bash
curl http://127.0.0.1:8000/v1/model-profiles
```

## Profiles

| Profile | Accuracy label | Hardware label | Example local models |
| --- | --- | --- | --- |
| `light` | lower | low | `qwen3:4b`, `llama3.2:3b`, `phi4-mini` |
| `balanced` | medium | moderate | `qwen3:14b`, `mistral-nemo`, `gemma3:12b` |
| `strong` | high | high | `qwen3:32b`, `deepseek-r1:32b`, `gemma3:27b` |

Use `balanced` as the starting point when your machine can run it comfortably. Use `light` for laptops or fast drafts, and `strong` for larger or more ambiguous forms when you have enough local memory or GPU capacity.

## Local Config

Create a starter config:

```bash
tdf init --output tdf.config.json
```

The generated file uses the `balanced` profile and an Ollama-style local endpoint:

```json
{
  "modelProfile": "balanced",
  "provider": {
    "type": "ollama",
    "baseUrl": "http://localhost:11434",
    "model": "qwen3:14b"
  },
  "generation": {
    "defaultSeed": "local",
    "includeMetadata": false
  }
}
```

Provider config parsing supports `ollama` and `openai_compatible` provider types. Direct provider requests are not implemented in the current source, so contract validation and data generation should be treated as the stable local workflow for this release.

## How Profiles Fit The Workflow

- Use form scanning, JSON Schema import, or OpenAPI import to draft a contract.
- Review the generated `.tdf.json` contract and commit it with your tests.
- Generate data from the committed contract using CLI, API, or Python SDK.
- Run CI without requiring live model access.

This keeps test execution deterministic and local-first, separate from any model-assisted contract drafting or review.
