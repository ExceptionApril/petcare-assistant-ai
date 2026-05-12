import os
import subprocess
import sys
from pathlib import Path
from shutil import which

from llama_index.core import Settings, SimpleDirectoryReader, VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama

# Set Ollama models directory on D: drive
os.environ["OLLAMA_MODELS"] = r"D:\.ollama"
os.environ["OLLAMA_MODEL"] = "llama3.2:1b"


def _find_ollama_executable() -> str:
	"""Find the Ollama executable on Windows or raise a clear setup error."""
	path = which("ollama")
	if path:
		return path

	possible_locations = [
		Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
		Path(os.environ.get("PROGRAMFILES", "")) / "Ollama" / "ollama.exe",
		Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Ollama" / "ollama.exe",
	]
	for candidate in possible_locations:
		if candidate.is_file():
			return str(candidate)

	raise RuntimeError(
		"Ollama is installed, but ollama.exe is not on PATH. "
		"Add Ollama to PATH or set the OLLAMA_EXE environment variable to the full path of ollama.exe."
	)


def _get_installed_ollama_models() -> set[str]:
	"""Return installed Ollama model names, or raise a clear setup error."""
	ollama_exe = os.getenv("OLLAMA_EXE") or _find_ollama_executable()
	try:
		result = subprocess.run(
			[ollama_exe, "list"],
			check=True,
			capture_output=True,
			text=True,
			env=os.environ,
		)
	except FileNotFoundError as exc:
		raise RuntimeError(
			"Ollama executable was not found. Install Ollama from https://ollama.com/download/windows, "
			"or point OLLAMA_EXE to the full path of ollama.exe."
		) from exc
	except subprocess.CalledProcessError as exc:
		raise RuntimeError(
			f"Unable to run 'ollama list'.\nDetails: {exc.stderr or exc.stdout}"
		) from exc

	lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
	if len(lines) <= 1:
		return set()

	models = set()
	for line in lines[1:]:
		name = line.split()[0]
		models.add(name)
		if ":" in name:
			models.add(name.split(":", 1)[0])
	return models


def _select_model(installed_models: set[str]) -> str:
	preferred = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
	if preferred in installed_models:
		return preferred

	if not installed_models:
		raise RuntimeError(
			"No local Ollama models are installed. Run:\n"
			"  ollama pull llama3.2:3b\n"
			"Or set OLLAMA_MODEL to another model you have locally."
		)

	fallback = sorted(installed_models)[0]
	print(
		f"Requested model '{preferred}' is not installed. "
		f"Falling back to '{fallback}'.",
		file=sys.stderr,
	)
	return fallback


def main() -> None:
	# 1) Verify Ollama setup and choose an available model.
	print("Checking Ollama installation...", flush=True)
	installed_models = _get_installed_ollama_models()
	model_name = _select_model(installed_models)
	print(f"Using Ollama model: {model_name}", flush=True)

	# 2) Configure LlamaIndex models.
	Settings.llm = Ollama(model=model_name, request_timeout=360.0)
	Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

	# 3) Build index from data directory.
	print("Loading documents from ./data...", flush=True)
	documents = SimpleDirectoryReader("./data").load_data()
	if not documents:
		raise RuntimeError("No documents found in ./data. Add files, then rerun.")

	print(f"Loaded {len(documents)} document(s). Building index...", flush=True)
	index = VectorStoreIndex.from_documents(documents)
	query_engine = index.as_query_engine()

	# 4) Run a sample query.
	print("Running sample query...", flush=True)
	response = query_engine.query("What is the main topic of this file? Summarize in a few sentences.")
	print(response)


if __name__ == "__main__":
	try:
		main()
	except Exception as exc:
		print(f"Error: {exc}", file=sys.stderr)
		sys.exit(1)