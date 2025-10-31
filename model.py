import os
import re

os.environ["HF_HOME"] = "D:/huggingface_cache"
os.environ["TORCH_HOME"] = "D:/torch_cache"
os.environ["TORCH_KERNEL_CACHE_PATH"] = "D:/torch_kernels"

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

device = "cuda" if torch.cuda.is_available() else "cpu"
print(device)

model_name = r"D:\models\Qwen2-7B-Instruct"
cache_dir = "D:/huggingface_cache"

os.makedirs(cache_dir, exist_ok=True)

tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
model = AutoModelForCausalLM.from_pretrained(
    model_name, cache_dir=cache_dir, device_map="auto", dtype=torch.float16
)

generation_config = model.generation_config
generation_config.temperature = 0.3
generation_config.top_p = 0.67
generation_config.do_sample = True
generation_config.pad_token_id = tokenizer.eos_token_id
generation_config.max_new_tokens = 45


def clean_response(text):
    if re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text):
        text = re.split(r"[\u4e00-\u9fff]", text)[0].strip()
        if not text:
            text = "Подсказка недоступна."
    return text


def generate_hint(question):
    prompt = (
        "ТЫ НЕ ДОЛЖЕН ИСПОЛЬЗОВАТЬ ИЕРОГЛИФЫ. ты должен дать ПОДСКАЗКУ, а не ответ по вопросу, чтобы пользователь сам догадался: "
        + question
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
    response = clean_response(response)
    return response.strip()
