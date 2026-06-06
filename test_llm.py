import os
import subprocess

MODEL = os.environ.get("RADAR_MODEL", "gemma4:31b-cloud")

def call_llm(prompt: str):
    try:
        result = subprocess.run(
            ["ollama", "run", MODEL, prompt],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

print(f"Using model: {MODEL}")
print(f"Result: {call_llm('What is 2+2? Return only the number.')}")
