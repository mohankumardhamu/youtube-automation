# Standalone Shorts script generator

Reads URL lists from `input/`, crawls each page, and writes a YouTube Shorts package for **The Tech Voyager** to `output/<date>/`. Each package has a one-paragraph script (about 50 s), a title, a description and hashtags. Everything runs locally through Ollama or colibri. It uses only Python's standard library, so there's nothing to install.

## Use

```bash
# put URLs (one per line, # for comments) in any .txt file under input/
python3 make_scripts.py                          # all input/*.txt, Ollama gemma4:latest
python3 make_scripts.py input/sites.txt          # a single file
python3 make_scripts.py --model gemma4:e2b       # smaller, faster Ollama model
python3 make_scripts.py --engine colibri         # colibri server on :8000 (uses its loaded model)
```

## Output

```
output/2026-11-19/
  01-<title-slug>.md     # title, script, description, hashtags (ready to copy)
  01-<title-slug>.json   # same, machine-readable
  index.json             # source URL -> file, status, errors (the only place the source appears)
```

Running again on the same day appends to that day's folder; numbering continues.

## Behaviour

- **Rules** (from the `youtube-video-generation-prompt` skill): the summary is one paragraph of 110–140 words and ends with a like/share/subscribe call to action for The Tech Voyager. The package also has a catchy title, a brief description, and SEO hashtags that always include #TheTechVoyager, #Shorts and #Tech. The source is never mentioned.
- **Checks:** the script checks word count, the call to action, and any mention of the source's name (taken from the domain and page title). If a check fails, it asks the model to fix the output, up to `--retries` times (default 2). Anything still wrong is listed under `warnings` in `index.json`.
- **Crawling:** a plain HTTP fetch. Pages behind bot protection or that need JavaScript (fewer than 400 characters of text) are marked `failed` and the run continues. Article URLs give better scripts than homepages.
- **Page length:** the first `--max-chars` characters (default 24,000, about 6k tokens) are sent to the model. `index.json` marks pages that were cut with `"truncated": true`. With Ollama, `--num-ctx` (default 16384) must stay large enough for the prompt, because Ollama silently drops anything beyond it.
- **Speed:** on this machine, Ollama `gemma4:latest` took 40–100 s per URL. colibri (Qwen3.6-35B on CPU) is much slower on long pages. Lower `--max-chars` to speed it up, and raise `--timeout` (default 900 s) if calls time out.
