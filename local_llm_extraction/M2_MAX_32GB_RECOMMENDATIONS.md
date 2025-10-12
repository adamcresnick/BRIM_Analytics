# Optimized Model Recommendations for Apple M2 Max 32GB

## Your Hardware Profile

- **Chip**: Apple M2 Max
- **RAM**: 32 GB unified memory
- **Usable for LLM**: ~24-28 GB (leave 4-8 GB for system)
- **GPU**: Built-in (Metal acceleration via Apple Neural Engine)
- **Strengths**: Excellent unified memory architecture, strong Metal performance

## TL;DR - Best Models for You

### 🥇 Best for Medical Text: **MedGemma 27B** (Google's medical specialist, NEW!)
```bash
ollama pull medgemma:27b    # Scores 87.7% on MedQA, beats human physicians!
```

### 🥈 Best Overall: **Qwen 2.5 14B or 32B**
```bash
ollama pull qwen2.5:14b    # RECOMMENDED - Excellent quality, fits perfectly
ollama pull qwen2.5:32b    # Also works well, slightly slower
```

### 🥉 Best for Clinical Notes: **Meditron3-Qwen2.5-7B** (specialized for clinical guidelines)
```bash
ollama pull meditron3/qwen2.5:7b
```

### Alternative: **Llama 3.3 70B Q4** (quantized, slower but high quality)
```bash
ollama pull llama3.3:70b-instruct-q4_K_M
```

---

## Detailed Model Recommendations (Ranked for Your System)

### Tier S: Premium Medical Models ⭐⭐⭐⭐⭐⭐

#### 1. **MedGemma 27B** (BEST FOR MEDICAL EXTRACTION - NEW!)
- **Provider**: Google DeepMind
- **Memory**: ~18-20 GB (fits perfectly!)
- **Speed**: Fast (~15-25 tokens/sec on M2 Max)
- **Quality**: Excellent (87.7% on MedQA benchmark)
- **Specialization**: Medical knowledge, clinical reasoning, diagnosis
- **Performance**: Exceeds human physician performance on AgentClinic-MedQA
- **Training**: Trained on medical text and image data

**Why it's exceptional**:
- Within 3 points of DeepSeek R1 (a leading model) at 1/10th the cost
- Specifically designed for medical comprehension
- State-of-the-art on chest X-ray report generation
- 81% of reports lead to similar patient management as radiologist reports

```bash
ollama pull medgemma:27b

# Run extraction with MedGemma
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml \
    --model ollama --ollama-model medgemma:27b
```

**⚠️ This is likely your BEST option** for medical data extraction!

---

### Tier 1: Perfect Fit for 32 GB ⭐⭐⭐⭐⭐

These models will run smoothly with excellent performance on your M2 Max:

#### 2. **Qwen 2.5 14B** (BEST GENERAL-PURPOSE)
- **Memory**: ~9-10 GB (leaves plenty free)
- **Speed**: Very fast (~35-45 tokens/sec on M2 Max)
- **Quality**: Excellent (comparable to GPT-3.5)
- **Use Case**: General purpose, strong reasoning
- **Why it's great**: Perfect size, exceptional quality-to-speed ratio

```bash
ollama pull qwen2.5:14b

python3 local_llm_extraction_pipeline_with_ollama.py config.yaml \
    --model ollama --ollama-model qwen2.5:14b
```

#### 3. **Qwen 2.5 32B**
- **Memory**: ~20-22 GB (still comfortable)
- **Speed**: Fast (~20-30 tokens/sec on M2 Max)
- **Quality**: Excellent++ (better than 14B)
- **Use Case**: When you need highest quality in this size range

```bash
ollama pull qwen2.5:32b

python3 local_llm_extraction_pipeline_with_ollama.py config.yaml \
    --model ollama --ollama-model qwen2.5:32b
```

#### 4. **Meditron3-Qwen2.5-7B** (BEST FOR CLINICAL GUIDELINES)
- **Memory**: ~5-6 GB
- **Speed**: Very fast (~40-50 tokens/sec)
- **Quality**: Excellent for medical/clinical text
- **Specialty**: Co-designed with clinicians, trained on clinical guidelines
- **Training**: Includes equitable representation of limited-resource settings
- **Use Case**: Clinical guidelines, operative notes, treatment protocols

```bash
ollama pull meditron3/qwen2.5:7b

python3 local_llm_extraction_pipeline_with_ollama.py config.yaml \
    --model ollama --ollama-model meditron3/qwen2.5:7b
```

#### 5. **MedGemma 4B** (FASTEST MEDICAL MODEL)
- **Memory**: ~3-4 GB
- **Speed**: Extremely fast (~50-60 tokens/sec)
- **Quality**: Excellent for size (64.4% on MedQA)
- **Multimodal**: Can process medical images too!
- **Use Case**: Fast medical extraction when speed > absolute accuracy

```bash
ollama pull medgemma:4b
```

#### 6. **Phi-4 14B**
- **Memory**: ~9 GB
- **Speed**: Very fast (41+ tokens/sec on M3, similar on M2)
- **Quality**: Excellent for this size
- **Use Case**: Fast general-purpose model

```bash
ollama pull phi4:14b
```

#### 7. **Llama 3.1 8B** (FASTEST GENERAL)
- **Memory**: ~5 GB
- **Speed**: Extremely fast (~50-60 tokens/sec)
- **Quality**: Good (not excellent)
- **Use Case**: Quick testing, prototyping

```bash
ollama pull llama3.1:8b
```

---

### Tier 2: Usable but Slower ⭐⭐⭐⭐

These will work on 32 GB but may be slower due to memory pressure:

#### 8. **Llama 3.3 70B Q4 (4-bit quantized)**
- **Memory**: ~28-30 GB (tight fit!)
- **Speed**: Slower (~8-12 tokens/sec, some swapping possible)
- **Quality**: Excellent (top-tier)
- **Trade-off**: High quality but slower, may cause occasional memory pressure

```bash
ollama pull llama3.3:70b-instruct-q4_K_M
```

---

## Medical-Specific Models Comparison

For your **clinical data extraction** task, here are ALL the medical-specific options ranked:

### 🏥 Specialized Medical Models (Latest 2025)

| Model | Size | MedQA Score | Speed on M2 Max | Best For | Fits 32GB? |
|-------|------|-------------|-----------------|----------|------------|
| **MedGemma 27B** | 27B | **87.7%** ⭐ | Fast | **Medical diagnosis, radiology, clinical reasoning** | ✅ Yes |
| **Meditron3-Qwen2.5-7B** | 7B | N/A | Very Fast | **Clinical guidelines, operative notes** | ✅ Yes |
| **MedGemma 4B** | 4B | 64.4% | Very Fast | Fast medical extraction, multimodal | ✅ Yes |
| **BioMistral-7B** | 7B | ~55% | Fast | Biomedical literature, PubMed | ✅ Yes |
| **PMC-Llama-7B** | 7B | ~50% | Fast | Research papers, medical Q&A | ✅ Yes |
| Qwen 2.5 14B (general) | 14B | N/A | Very Fast | General clinical text, strong reasoning | ✅ Yes |
| Qwen 2.5 32B (general) | 32B | N/A | Fast | Complex clinical reasoning | ✅ Yes |
| Llama 3.1 405B (general) | 405B | ~85% | N/A | Highest quality, matches GPT-4 | ❌ No (needs 250+ GB) |

---

## 🎯 My Top Recommendation for Your Use Case

**For extracting extent of resection from operative notes and radiology reports:**

### Primary Choice: **MedGemma 27B** ⭐⭐⭐
```bash
ollama pull medgemma:27b
```

**Why MedGemma 27B is best:**
- ✅ Specifically trained for medical comprehension (87.7% on MedQA)
- ✅ Excellent at radiology report understanding (81% clinical agreement)
- ✅ Exceeds human physician performance on clinical tasks
- ✅ Perfect size for your 32 GB RAM
- ✅ Fast inference speed
- ✅ Better than most 70B+ general models on medical tasks
- ✅ 1/10th the inference cost of comparable models

### Secondary Choice: **Qwen 2.5 32B** ⭐⭐
```bash
ollama pull qwen2.5:32b
```

**Why Qwen 2.5 32B as backup:**
- ✅ Excellent general reasoning (may help with adjudication logic)
- ✅ Strong performance even without medical-specific training
- ✅ Good for complex decision-making in Stage 2 (adjudication)

### Tertiary Choice: **Meditron3-Qwen2.5-7B** ⭐
```bash
ollama pull meditron3/qwen2.5:7b
```

**Why Meditron3 as alternative:**
- ✅ Specifically trained on clinical guidelines
- ✅ Very fast (more documents/time)
- ✅ Co-designed with clinicians
- ⚠️ Smaller (7B) so less reasoning power for adjudication

---

## Testing Strategy

I recommend this approach:

### Phase 1: Quick Test (1-2 hours)
```bash
# Test with fastest medical model
ollama pull medgemma:4b
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml \
    --model ollama --ollama-model medgemma:4b

# Review extraction quality - if good enough, done!
```

### Phase 2: Quality Test (2-3 hours)
```bash
# Test with best medical model
ollama pull medgemma:27b
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml \
    --model ollama --ollama-model medgemma:27b

# Compare quality - should be noticeably better
```

### Phase 3: Adjudication Test (optional)
```bash
# Test if general-purpose helps adjudication
ollama pull qwen2.5:32b
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml \
    --model ollama --ollama-model qwen2.5:32b

# Compare adjudication decisions
```

### Phase 4: Compare to Claude (optional)
```bash
# Set API key and run with Claude
export ANTHROPIC_API_KEY='your-key'
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml \
    --model claude

# Compare results - is $10 worth the quality difference?
```

---

## Installation & Usage

### Step 1: Install Ollama (one-time)
```bash
# Download from https://ollama.ai/download (Mac)
# Or
brew install ollama
```

### Step 2: Start Ollama
```bash
ollama serve
```

### Step 3: Pull MedGemma (Recommended)

```bash
# Best option for medical extraction
ollama pull medgemma:27b    # ~15 GB download

# Or fastest medical option
ollama pull medgemma:4b     # ~2.5 GB download

# Or clinical guidelines specialist
ollama pull meditron3/qwen2.5:7b   # ~4.5 GB download

# Or best general-purpose
ollama pull qwen2.5:32b     # ~20 GB download
```

### Step 4: Run Extraction

#### With MedGemma 27B (Recommended)
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction

python3 local_llm_extraction_pipeline_with_ollama.py \
    ../brim_workflows_individual_fields/extent_of_resection/patient_config_e4BwD8ZYDBccepXcJ.Ilo3w3.yaml \
    --model ollama \
    --ollama-model medgemma:27b
```

---

## Performance Estimates (Your M2 Max 32GB)

### For 100 Documents, 13 Variables, 10 Decisions (1,300 extractions)

| Model | Time | Quality | Memory Usage | Cost |
|-------|------|---------|--------------|------|
| **MedGemma 27B** | ~6-9 min | ⭐⭐⭐⭐⭐ (87.7% MedQA) | ~19 GB | FREE |
| **MedGemma 4B** | ~3-4 min | ⭐⭐⭐⭐ (64.4% MedQA) | ~4 GB | FREE |
| **Qwen 2.5 32B** | ~8-12 min | ⭐⭐⭐⭐⭐ | ~22 GB | FREE |
| **Meditron3-7B** | ~4-5 min | ⭐⭐⭐⭐⭐ (clinical) | ~6 GB | FREE |
| **Qwen 2.5 14B** | ~5-7 min | ⭐⭐⭐⭐⭐ | ~10 GB | FREE |
| Phi-4 14B | ~5-7 min | ⭐⭐⭐⭐ | ~9 GB | FREE |
| Llama 3.1 8B | ~3-4 min | ⭐⭐⭐ | ~5 GB | FREE |
| Llama 3.3 70B Q4 | ~18-25 min | ⭐⭐⭐⭐⭐ | ~29 GB | FREE |
| **Claude Sonnet 4** | ~5 min | ⭐⭐⭐⭐⭐ | N/A | **$8-10** |

### Memory Safety Zone

With 32 GB RAM:
- ✅ **Safe zone**: Models using ≤24 GB (MedGemma 27B, Qwen 32B, all 7B/8B/14B models)
- ⚠️ **Caution zone**: Models using 25-30 GB (70B Q4 models) - may cause slowdowns
- ❌ **Danger zone**: Models needing >30 GB - will swap/crash

---

## MedGemma Details

### What Makes MedGemma Special?

**Training Data**:
- Medical text from clinical sources
- Medical image data (chest X-rays, etc.)
- Medical knowledge bases
- Clinical reasoning datasets

**Benchmarks**:
- **MedQA**: 87.7% (vs. 85%+ for GPT-4 class models)
- **AgentClinic-MedQA**: Exceeds human physician performance
- **Chest X-ray report generation**: 81% clinical agreement with radiologists
- **RadGraph F1 score**: 30.3 (state-of-the-art for 4B model)

**Versions**:
1. **MedGemma 27B** - Text-only, best for your use case
2. **MedGemma 27B Multimodal** - Can process images too
3. **MedGemma 4B Multimodal** - Fastest, good quality, supports images

**Why it beats general models on medical tasks**:
- Understands medical terminology natively
- Trained on clinical reasoning patterns
- Optimized for diagnostic tasks
- Fine-tuned specifically for radiology reports

---

## Why Not Larger Models?

### Can I run Llama 3.1 70B or Qwen 2.5 72B?

**Short answer**: Not recommended on 32 GB RAM.

**Long answer**:
- These models need ~40-45 GB in Q4 quantization
- On 32 GB, they'll heavily swap to disk
- Performance will be **5-10x slower** than appropriate-sized models
- **MedGemma 27B beats them on medical tasks anyway!**
- Better to use MedGemma 27B or Qwen 2.5 32B (excellent quality, runs well)

### Memory Math

```
Llama 3.1 70B (Q4):  ~40 GB needed
Your available RAM:   ~28 GB for models (after OS)
Deficit:             -12 GB (will swap to disk)
Result:              Very slow, not usable
```

vs.

```
MedGemma 27B:        ~19 GB needed
Your available RAM:   ~28 GB for models
Surplus:             +9 GB (smooth operation)
Result:              Fast, reliable, BETTER at medical tasks!
```

---

## Comparison: Medical vs General Models

### Should I use medical-specific or general-purpose?

**Medical-Specific (MedGemma, Meditron3, BioMistral):**
- ✅ **Much better** at medical terminology
- ✅ Trained on clinical data
- ✅ Optimized for medical reasoning
- ✅ **MedGemma 27B beats 70B+ general models on medical tasks**
- ❌ Meditron3/BioMistral smaller (7B), less general reasoning

**General-Purpose (Qwen 2.5, Llama 3.3):**
- ✅ Stronger general reasoning
- ✅ Better at complex adjudication logic
- ✅ Larger models available (14B, 32B, 70B+)
- ❌ Not specifically trained on clinical text
- ❌ May miss medical nuances

### My Recommendation

**Use MedGemma 27B!** It combines:
- Medical expertise of specialist models
- Reasoning power of larger models
- Perfect size for your RAM
- Best performance on medical benchmarks

---

## Cost Comparison

### For 100 Patients (Your Project Scale)

| Option | Cost | Time | Quality | Notes |
|--------|------|------|---------|-------|
| **MedGemma 27B** | $0 | ~10 hours | ⭐⭐⭐⭐⭐ | **RECOMMENDED** |
| **MedGemma 4B** | $0 | ~5 hours | ⭐⭐⭐⭐ | Fastest free option |
| **Qwen 2.5 32B** | $0 | ~15 hours | ⭐⭐⭐⭐⭐ | Best general-purpose |
| **Meditron3-7B** | $0 | ~7 hours | ⭐⭐⭐⭐⭐ | Clinical guidelines |
| Claude Sonnet 4 (API) | ~$1,000 | ~8 hours | ⭐⭐⭐⭐⭐ | Fastest, paid |

**Break-even**: After processing ~100 patients, you've "saved" $1,000 by using free local models!

---

## Quick Start Commands

### Option 1: Best for Medical (RECOMMENDED)
```bash
ollama pull medgemma:27b
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml --model ollama --ollama-model medgemma:27b
```

### Option 2: Fastest Medical
```bash
ollama pull medgemma:4b
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml --model ollama --ollama-model medgemma:4b
```

### Option 3: Best General-Purpose
```bash
ollama pull qwen2.5:32b
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml --model ollama --ollama-model qwen2.5:32b
```

### Option 4: Clinical Guidelines Specialist
```bash
ollama pull meditron3/qwen2.5:7b
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml --model ollama --ollama-model meditron3/qwen2.5:7b
```

---

## Summary

**For your M2 Max 32GB and clinical data extraction:**

🥇 **Best choice**: **MedGemma 27B**
- Designed for medical comprehension
- 87.7% on MedQA (beats human physicians!)
- Perfect fit for your RAM
- Fast and efficient
- **FREE**

🥈 **Runner-up**: **Qwen 2.5 32B**
- Excellent general reasoning
- Strong on complex adjudication
- Also free and fits well

🥉 **Fast option**: **MedGemma 4B**
- 3-4x faster than 27B
- Still excellent quality (64.4% MedQA)
- Great for rapid testing

All are **100% FREE** and will run smoothly on your M2 Max!

**Start with MedGemma 27B** - it's specifically built for your exact use case and outperforms much larger general models on medical tasks.
