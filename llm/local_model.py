"""Runs a small language model fully offline using llama.cpp."""
from pathlib import Path

from llm.prompts import SYSTEM_PROMPT, build_user_prompt

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
_llm = None   # loaded once, then reused (loading is slow)


def find_model():
    """Use the first .gguf file found in the models/ folder."""
    files = sorted(MODELS_DIR.glob("*.gguf"))
    return files[0] if files else None


def model_available():
    try:
        import llama_cpp  # noqa: F401
    except ImportError:
        return False
    return find_model() is not None


def get_llm():
    global _llm
    if _llm is None:
        from llama_cpp import Llama
        _llm = Llama(
            model_path=str(find_model()),
            n_ctx=2048,        # how much text the model can read at once
            n_threads=2,       # matches the "two ARM cores" constraint
            verbose=False,
        )
    return _llm


def generate_answer(question, facts_text):
    llm = get_llm()
    out = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(question, facts_text)},
        ],
        max_tokens=150,        # shorter answers = faster
        temperature=0.2,       # low = more factual, less creative
    )
    return out["choices"][0]["message"]["content"].strip()