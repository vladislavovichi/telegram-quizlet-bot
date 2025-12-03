from __future__ import annotations

import asyncio
import os
import re
from typing import List

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

HF_HOME = os.getenv("HF_HOME", "/cache/huggingface")
TORCH_HOME = os.getenv("TORCH_HOME", "/cache/torch")
TORCH_KERNEL_CACHE_PATH = os.getenv("TORCH_KERNEL_CACHE_PATH", "/cache/torch_kernels")
MODEL_PATH = os.getenv("MODEL_PATH", "Qwen/Qwen2-0.5B-Instruct")

os.environ["HF_HOME"] = HF_HOME
os.environ["TORCH_HOME"] = TORCH_HOME
os.environ["TORCH_KERNEL_CACHE_PATH"] = TORCH_KERNEL_CACHE_PATH

app = FastAPI(title="NeuralNet service", version="1.0.0")

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, cache_dir=HF_HOME)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    cache_dir=HF_HOME,
    device_map="auto",
    torch_dtype=torch.float16,
)

generation_config = model.generation_config
generation_config.temperature = float(os.getenv("GEN_TEMPERATURE", "0.3"))
generation_config.top_p = float(os.getenv("GEN_TOP_P", "0.67"))
generation_config.do_sample = True
generation_config.pad_token_id = tokenizer.eos_token_id
generation_config.max_new_tokens = int(os.getenv("GEN_MAX_NEW_TOKENS", "45"))


def clean_response(text: str) -> str:
    text = text.strip().strip("\"'“”«»„“")
    cjk_pattern = r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]"

    if re.search(cjk_pattern, text):
        text = re.split(cjk_pattern, text)[0].strip()

    if not text:
        return "Подсказка недоступна."

    text = text.strip().strip("\"'“”«»„“")

    return text


def generate_hint_sync(
    question: str, answer: str, prev_hints: List[str] | None = None
) -> str:
    prev_hints = prev_hints or []

    prompt = (
        "ТЫ НЕ ДОЛЖЕН ИСПОЛЬЗОВАТЬ ИЕРОГЛИФЫ. "
        "Ты — помощник, который даёт краткие и аккуратные ПОДСКАЗКИ, "
        "а не готовые ответы. Ты не должен раскрывать решение полностью. "
        "Используй только русский язык и не используй иероглифы.\n\n"
        "Вот ВОПРОС пользователя:\n"
        f"{question}\n\n"
        "Вот ПРАВИЛЬНЫЙ ОТВЕТ (не раскрывай его полностью):\n"
        f"{answer}\n\n"
        "Сформулируй такую подсказку, которая мягко направит пользователя "
        "к правильному ответу, но не подскажет его напрямую."
    )

    messages = [{"role": "user", "content": prompt}]

    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    outputs = model.generate(
        input_ids=inputs.input_ids,
        attention_mask=inputs.attention_mask,
        generation_config=generation_config,
    )
    response = tokenizer.decode(
        outputs[0][inputs.input_ids.shape[1] :], skip_special_tokens=True
    )
    return clean_response(response)


class HintRequest(BaseModel):
    question: str
    answer: str
    prev_hints: list[str] = []


class HintResponse(BaseModel):
    hint: str


@app.post("/neuralnet/model", response_model=HintResponse)
async def neuralnet_model_endpoint(req: HintRequest) -> HintResponse:
    try:
        loop = asyncio.get_running_loop()
        hint = await loop.run_in_executor(
            None, generate_hint_sync, req.question, req.answer, req.prev_hints
        )
        return HintResponse(hint=hint)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"model error: {e!s}")
