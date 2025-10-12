# Ollama Setup Guide - Free Local LLM Inference

## What is Ollama?

Ollama lets you run large language models (LLMs) locally on your machine **completely free**. No API keys, no cloud costs, just download and run.

**Benefits:**
- ✅ **FREE** - No API costs, no rate limits
- ✅ **Private** - Data never leaves your machine
- ✅ **Fast** - No network latency (after initial download)
- ✅ **Offline** - Works without internet connection

**Comparable Models to Amazon Nova Pro:**
- Llama 3.1 70B (Meta) - Excellent all-around performance
- Qwen 2.5 72B (Alibaba) - Strong reasoning and medical knowledge
- Mistral Large 123B - Highest quality, slower

## Installation

### Step 1: Install Ollama

#### macOS
```bash
# Download and install from:
https://ollama.ai/download

# Or use Homebrew:
brew install ollama
```

#### Linux
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

#### Windows
Download from: https://ollama.ai/download/windows

### Step 2: Start Ollama Service

```bash
# Start Ollama in the background
ollama serve
```

Leave this running in a terminal window.

### Step 3: Pull a Model

Choose a model based on your needs:

#### Option A: Llama 3.1 70B (Recommended - Best balance)
```bash
ollama pull llama3.1:70b
```
- **Size**: ~40 GB
- **RAM needed**: 48 GB minimum
- **Quality**: Excellent
- **Speed**: Moderate

#### Option B: Qwen 2.5 72B (Best for medical/technical)
```bash
ollama pull qwen2.5:72b
```
- **Size**: ~41 GB
- **RAM needed**: 48 GB minimum
- **Quality**: Excellent for medical text
- **Speed**: Moderate

#### Option C: Llama 3.1 8B (Fastest, lower quality)
```bash
ollama pull llama3.1:8b
```
- **Size**: ~4.7 GB
- **RAM needed**: 8 GB minimum
- **Quality**: Good (not excellent)
- **Speed**: Very fast

#### Option D: Mistral Large 123B (Highest quality)
```bash
ollama pull mistral-large
```
- **Size**: ~70 GB
- **RAM needed**: 80 GB minimum
- **Quality**: Excellent
- **Speed**: Slower

**Recommendation**: Start with `llama3.1:70b` if you have 48+ GB RAM, or `llama3.1:8b` if you have less.

### Step 4: Install Python Package

```bash
pip install ollama
```

## Usage

### Basic Usage (with Ollama)

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction

# Run with Ollama (FREE, no API key needed)
python3 local_llm_extraction_pipeline_with_ollama.py \
    ../brim_workflows_individual_fields/extent_of_resection/patient_config_e4BwD8ZYDBccepXcJ.Ilo3w3.yaml \
    --model ollama \
    --ollama-model llama3.1:70b
```

### Comparing Models

```bash
# High quality, slower (70B parameters)
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml --model ollama --ollama-model llama3.1:70b

# Very fast, lower quality (8B parameters)
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml --model ollama --ollama-model llama3.1:8b

# Best for medical/technical content (72B parameters)
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml --model ollama --ollama-model qwen2.5:72b

# Highest quality, slowest (123B parameters)
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml --model ollama --ollama-model mistral-large
```

### Using Claude API (for comparison)

```bash
# Set API key
export ANTHROPIC_API_KEY='your-key-here'

# Run with Claude (costs ~$8-10 per patient)
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml --model claude
```

## Performance Comparison

### Llama 3.1 70B (via Ollama) vs Claude Sonnet 4

| Metric | Llama 3.1 70B | Claude Sonnet 4 |
|--------|---------------|-----------------|
| **Cost per patient** | $0 (FREE) | ~$8-10 |
| **Speed (100 docs)** | ~8-12 minutes* | ~4-5 minutes |
| **Quality** | Excellent | Excellent |
| **Privacy** | 100% local | Sent to Anthropic |
| **Requirements** | 48 GB RAM | API key |
| **Internet needed** | No (after download) | Yes |

*Speed depends on your hardware. With Apple M3 Max or NVIDIA RTX 4090, it can be 2-3x faster.

### Hardware Requirements

**Minimum specs for Llama 3.1 70B:**
- **RAM**: 48 GB (64 GB recommended)
- **Storage**: 45 GB free space
- **CPU**: Modern multi-core (Apple Silicon M-series, or Intel/AMD with AVX2)
- **GPU**: Optional but helps (NVIDIA, AMD, or Apple Metal)

**Minimum specs for Llama 3.1 8B (smaller model):**
- **RAM**: 8 GB
- **Storage**: 5 GB free space
- **CPU**: Any modern processor

**Your system (if Apple Silicon):**
- M1 Max/M2 Max/M3 Max: Can run 70B models well
- M1/M2/M3: Can run 8B-13B models well, 70B will be slower

## Model Quality Comparison

Based on medical text extraction tasks:

### Tier 1: Excellent Quality
- **Claude Sonnet 4** (Anthropic, API, paid)
- **Llama 3.1 70B** (Meta, Ollama, free)
- **Qwen 2.5 72B** (Alibaba, Ollama, free)
- **Mistral Large 123B** (Mistral AI, Ollama, free)

### Tier 2: Good Quality
- **Llama 3.1 8B** (Meta, Ollama, free)
- **Amazon Nova Pro** (AWS Bedrock, API, paid)

### Recommendation

For **BRIM-style extraction on medical data**:
1. **Best Free Option**: `qwen2.5:72b` - Excellent for medical/technical text
2. **Best Paid Option**: Claude Sonnet 4 - Slightly faster, great support
3. **Fastest Free Option**: `llama3.1:8b` - Good enough for many tasks

## Troubleshooting

### Error: "Ollama is not running"

**Solution**: Start Ollama service:
```bash
ollama serve
```

### Error: "Model not found"

**Solution**: Pull the model first:
```bash
ollama pull llama3.1:70b
```

### Error: "Out of memory"

**Solution**: Use a smaller model:
```bash
# Instead of 70B, use 8B
ollama pull llama3.1:8b

# Then run with smaller model
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml --model ollama --ollama-model llama3.1:8b
```

### Slow Performance

**Solutions**:
1. **Use GPU acceleration**: Ollama automatically uses GPU if available (NVIDIA CUDA, AMD ROCm, or Apple Metal)
2. **Use smaller model**: Switch to `llama3.1:8b` for 5-10x speed boost
3. **Close other apps**: Free up RAM for the model
4. **Upgrade hardware**: More RAM = faster inference

### Check Available Models

```bash
# List models you've downloaded
ollama list

# Check model details
ollama show llama3.1:70b
```

## Cost Analysis

### For 1 Patient (100 documents)

| Model | Cost | Time | RAM Needed |
|-------|------|------|------------|
| **Llama 3.1 70B** (Ollama) | $0 | ~10 min | 48 GB |
| **Claude Sonnet 4** (API) | ~$8-10 | ~5 min | N/A |
| **Llama 3.1 8B** (Ollama) | $0 | ~3 min | 8 GB |

### For 100 Patients

| Model | Cost | Time | Hardware Investment |
|-------|------|------|---------------------|
| **Llama 3.1 70B** (Ollama) | $0 | ~17 hours | $0 (if you have RAM) |
| **Claude Sonnet 4** (API) | ~$800-1000 | ~8 hours | $0 |
| **Llama 3.1 8B** (Ollama) | $0 | ~5 hours | $0 |

**Break-even point**: After ~100 patients, the free local models save significant money compared to API costs.

## Advanced: GPU Acceleration

### NVIDIA GPU (Linux/Windows)

Ollama automatically uses CUDA if NVIDIA drivers are installed.

Check GPU usage:
```bash
nvidia-smi
```

### Apple Silicon (Mac)

Ollama automatically uses Metal API on M1/M2/M3 chips. No setup needed.

Check performance:
```bash
# Monitor GPU usage
sudo powermetrics --samplers gpu_power -i 1000
```

### AMD GPU (Linux)

Ollama supports ROCm for AMD GPUs.

Install ROCm:
```bash
# See: https://rocm.docs.amd.com/
```

## Additional Resources

- **Ollama Documentation**: https://github.com/ollama/ollama
- **Model Library**: https://ollama.ai/library
- **Llama 3.1 Info**: https://ai.meta.com/llama/
- **Qwen 2.5 Info**: https://qwenlm.github.io/

## Getting Help

1. Check Ollama logs: `ollama logs`
2. Test model: `ollama run llama3.1:70b "Hello"`
3. Check this guide's Troubleshooting section
4. Ollama GitHub Issues: https://github.com/ollama/ollama/issues
