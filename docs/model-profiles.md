# Local Model Profiles

Last updated: 2026-07-17

TestData Factory should start with local, open-weight model support. The project should not require paid models for V1.

The model is used for analysis and contract validation, not for deterministic data generation during normal test execution.

## 1. Provider Strategy

Required V1 providers:

- Ollama provider using the local Ollama API.
- OpenAI-compatible local endpoint provider.
- llama.cpp/llama-server compatible provider through an OpenAI-compatible endpoint.

Why:

- Ollama is simple for individual users.
- OpenAI-compatible endpoints make the project work with many local servers.
- llama.cpp support keeps CPU and consumer GPU paths available.

## 2. Profiles

### 2.1 Light

Goal:

- Run on typical developer laptops.
- Fast enough for contract drafts.
- Lower accuracy and more human review expected.

Recommended examples:

- `qwen3:4b`
- `gemma3n:e4b`
- `llama3.2:3b`
- `phi4-mini`

Expected hardware:

- Modern laptop CPU, preferably with 16 GB RAM.
- GPU optional.
- Good for small forms and simple schemas.

User-facing note:

> Light profile is optimized for low hardware requirements. It may misclassify business field types and should be reviewed carefully before committing contracts.

### 2.2 Balanced

Goal:

- Stronger field inference and scenario generation.
- Reasonable for automation engineers with better laptops or modest GPUs.

Recommended examples:

- `qwen3:14b`
- `mistral-nemo`
- `phi4-reasoning`
- `gemma3:12b`
- `deepseek-r1:14b`

Expected hardware:

- 32 GB system RAM for CPU/unified-memory use.
- Consumer GPU helpful.
- Better for multi-field forms, ambiguous labels, and richer validation feedback.

User-facing note:

> Balanced profile is the recommended default when hardware allows it. It provides better business-type inference than light models while remaining realistic for individual users.

### 2.3 Strong

Goal:

- Highest default local accuracy for complex pages, long contracts, and ambiguous fields.
- Still realistic for individual users with strong consumer hardware.

Recommended examples:

- `qwen3:32b`
- `deepseek-r1:32b`
- `gemma3:27b`

Expected hardware:

- Strong consumer GPU or high unified memory machine.
- Quantized models are expected for most users.
- Not expected to require H100/H200-class infrastructure.

User-facing note:

> Strong profile gives the best local inference quality, but requires significantly more memory and a stronger GPU or high unified memory system. It is not required for day-to-day deterministic test execution.

## 3. Excluded By Default

The default docs and setup should avoid recommending models that require data-center-only hardware.

Examples to avoid as default recommendations:

- Very large 70B+ dense models unless clearly marked advanced.
- MoE or coder models requiring hundreds of GB of memory.
- Any path that makes an individual user feel they need H100/H200-class GPUs.

These models can be supported through custom configuration, but not positioned as required.

## 4. Model Responsibilities

The model may:

- Infer business field types.
- Propose constraints.
- Propose scenario definitions.
- Validate a generated contract draft.
- Explain inference signals.

The model should not:

- Generate test data during every test execution by default.
- Be required in CI test execution after contracts are approved.
- Be the only validator.
- Override deterministic contract rules without explicit user action.

## 5. Model Output Requirements

All model responses used by the engine must be requested as structured JSON.

The engine must validate model output against JSON Schema before accepting it.

If model output is invalid:

- Retry with stricter instructions.
- Fall back to deterministic heuristics.
- Mark the contract as `needs_review`.

## 6. Accuracy Labels

The UI/CLI/docs should communicate profile tradeoffs plainly:

- Light: low hardware, lower accuracy.
- Balanced: recommended default, medium-to-good accuracy.
- Strong: best local accuracy, high hardware needs.

Avoid implying exact accuracy percentages unless backed by project-owned benchmarks.

## 7. Benchmark Requirement

Before public release, create a small benchmark suite:

- At least 50 sample forms.
- English labels for V1.
- Arabic labels when multilingual inference enters the roadmap implementation phase.
- Common signup/login/profile/payment/address forms.
- Expected `businessType` labels.
- Expected scenario coverage.

Benchmark metrics:

- Field detection recall.
- Business type accuracy.
- Required/optional detection accuracy.
- Scenario coverage.
- Invalid JSON rate from model.
- Time to analyze.

The benchmark should compare light, balanced, and strong profiles.

## 8. Current Source Notes

Useful upstream references checked while drafting:

- Ollama exposes a local API for chat/generate requests.
- Ollama lists Qwen, Gemma, Llama, Phi, Mistral, and DeepSeek model families in multiple local sizes.
- llama-cpp-python and llama.cpp can expose OpenAI-compatible local servers.

Concrete model recommendations should be re-checked before release because local model quality and availability change quickly.
