# VehicleGPT Offline SLM Models

This directory stores offline GGUF model weights for the on-device SLM assistant.

### Recommended Model
- **Model**: `qwen2.5-0.5b-instruct-q4_k_m.gguf` (~491.4 MB)
- **Source**: [Qwen/Qwen2.5-0.5B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF)
- **Quantization**: `q4_k_m`
- **Memory Footprint**: ~560 MB active RSS on 2 threads (meets < 2.0 GB embedded budget)

### Installation
Place the `.gguf` file in this directory:
```bash
# Example via curl / huggingface-cli
curl -L -o models/qwen2.5-0.5b-instruct-q4_k_m.gguf https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf
```
*Note: Large `.gguf` binary weights are excluded from Git repository commits via `.gitignore` per GitHub's 100 MB file limit.*
