# Quick Start - One Command Solutions

## 🚀 I Just Want to Run It NOW!

### Option 1: FREE (No API Key Needed!)

```bash
# 1. Install Ollama (one-time, ~2 minutes)
curl -fsSL https://ollama.ai/install.sh | sh   # Linux
# OR download from https://ollama.ai/download   # macOS/Windows

# 2. Start Ollama (keep running in background)
ollama serve &

# 3. Pull model (one-time, ~5 minutes, ~5 GB download)
ollama pull llama3.1:8b

# 4. Install Python package (one-time, ~30 seconds)
pip install ollama pandas pyyaml

# 5. Run extraction (FREE!)
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction
python3 local_llm_extraction_pipeline_with_ollama.py \
    ../brim_workflows_individual_fields/extent_of_resection/patient_config_e4BwD8ZYDBccepXcJ.Ilo3w3.yaml \
    --model ollama \
    --ollama-model llama3.1:8b
```

**Done!** Results will be in the staging_files directory.

---

### Option 2: Paid but Fast

```bash
# 1. Get API key from https://console.anthropic.com/ (~2 minutes)

# 2. Install packages (one-time, ~30 seconds)
pip install anthropic pandas pyyaml

# 3. Set API key
export ANTHROPIC_API_KEY='your-key-here'

# 4. Run extraction (~5 minutes, costs ~$10)
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction
python3 local_llm_extraction_pipeline_with_ollama.py \
    ../brim_workflows_individual_fields/extent_of_resection/patient_config_e4BwD8ZYDBccepXcJ.Ilo3w3.yaml \
    --model claude
```

**Done!** Results will be in the staging_files directory.

---

## 📊 Which Option Should I Choose?

### Choose FREE (Ollama) if:
- ✅ You have 8+ GB RAM
- ✅ You want to save money
- ✅ You'll run this multiple times
- ✅ You care about data privacy

### Choose PAID (Claude) if:
- ✅ You only have 1-5 patients
- ✅ You want fastest results
- ✅ You don't mind $8-10 cost per patient

---

## 🎯 Want Better Quality? (FREE)

Upgrade to the 70B model for excellent quality (requires 48 GB RAM):

```bash
# Pull larger model (one-time, ~15 minutes, ~40 GB download)
ollama pull llama3.1:70b

# OR use Qwen for best medical text quality
ollama pull qwen2.5:72b

# Then run with the better model
python3 local_llm_extraction_pipeline_with_ollama.py config.yaml \
    --model ollama \
    --ollama-model llama3.1:70b
```

---

## 📁 Where Are My Results?

After running, look in:
```
staging_files/e4BwD8ZYDBccepXcJ.Ilo3w3/
├── extraction_results_e4BwD8ZYDBccepXcJ.Ilo3w3.csv    # Detailed extractions
├── adjudication_results_e4BwD8ZYDBccepXcJ.Ilo3w3.csv  # Final decisions
└── extraction_summary_e4BwD8ZYDBccepXcJ.Ilo3w3.csv    # Summary (best for analysis)
```

**Use the `extraction_summary_*.csv` file** - it has one row with all your extracted variables!

---

## ❓ Troubleshooting

### "Ollama is not running"
```bash
ollama serve &
```

### "Model not found"
```bash
ollama pull llama3.1:8b
```

### "Out of memory"
Use smaller model:
```bash
ollama pull llama3.1:8b    # Only needs 8 GB RAM
```

### "ANTHROPIC_API_KEY not set"
```bash
export ANTHROPIC_API_KEY='your-key-here'
```

### Still stuck?
Read the full guides:
- [OLLAMA_SETUP.md](OLLAMA_SETUP.md) - Complete Ollama setup
- [MODEL_COMPARISON.md](MODEL_COMPARISON.md) - Which model to choose
- [README.md](README.md) - Full documentation

---

## 🎓 Next Steps

Once you have results:

1. **Check quality**: Open `extraction_summary_*.csv` in Excel/Numbers
2. **Compare to BRIM**: When BRIM is back online, compare results
3. **Refine prompts**: Edit `variables.csv` to improve extraction
4. **Process more patients**: Just change the config file path!

---

## 💡 Pro Tips

**Save money**: If you'll process 10+ patients, use Ollama (saves $80-100)

**Save time**: Use `llama3.1:8b` for testing, then re-run with `llama3.1:70b` for final results

**Best quality**: Use `qwen2.5:72b` - it's FREE and excellent for medical text

**Fastest**: Use Claude API - it's 2x faster than local models (but costs money)

---

## Need Help?

1. Check [README.md](README.md) for full documentation
2. Check [OLLAMA_SETUP.md](OLLAMA_SETUP.md) for Ollama issues
3. Check [MODEL_COMPARISON.md](MODEL_COMPARISON.md) to choose the right model
4. Ask on GitHub Issues (if this is a public repo)
