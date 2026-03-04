from typing import Set

# File extensions that should be translated
TRANSLATABLE_EXTENSIONS: Set[str] = {'.md', '.markdown'}

# File extensions that should be copied as resources
RESOURCE_EXTENSIONS: Set[str] = {
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp',
    '.css', '.js', '.json', '.pdf', '.ico', '.woff', '.ttf'
}

# Directories to exclude from processing
EXCLUDED_DIRS: Set[str] = {
    '.git', '__pycache__', 'node_modules', '.venv', '.idea', '.vscode', 'site'
}

# OpenAI Model Options
OPENAI_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "claude-3-5-sonnet-20240620",
    "claude-3-opus-20240229",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]

DEFAULT_MODEL = "gpt-4o"
DEFAULT_MAX_CONCURRENCY = 3
DEFAULT_RPM_LIMIT = 60
DEFAULT_TEMPERATURE = 0.3
DEFAULT_REQUEST_TIMEOUT = 60
DEFAULT_RAW_SYSTEM_PROMPT = (
    "You are a technical documentation translator. "
    "Translate the following Markdown content from {current_language} to {target_language}. "
    "Rules:\n"
    "1. Do NOT translate code blocks, inline code, HTML tags, or Front Matter keys.\n"
    "2. Keep original URLs and image paths exactly as they are.\n"
    "3. Maintain the original Markdown structure strictly (headings, lists, tables, emphasis, blockquotes, etc.).\n"
    "4. Translate all visible human-readable text, including headings, table headers/cells, list items, and blockquotes.\n"
    "5. Keep Markdown syntax tokens unchanged (e.g., '#', '-', '>', '|', '```', ':::', '!!!', '???', link/image brackets/parentheses).\n"
    "6. Translate technical terms using standard {target_language} technical terminology where appropriate, "
    "but keep specific library names, function names, or variable names in English.\n"
    "7. If a line is just a symbol, delimiter, or formatting, keep it as is.\n"
    "8. If {current_language} is auto, detect the source language from the content.\n"
    "9. Output ONLY the translated content, no explanations."
)

DEFAULT_STRUCTURED_SYSTEM_PROMPT = (
    "You are a technical documentation translator. "
    "Translate the following Markdown content from {current_language} to {target_language}. "
    "Rules:\n"
    "1. Do NOT translate code blocks, inline code, HTML tags, or Front Matter keys.\n"
    "2. Keep original URLs and image paths exactly as they are.\n"
    "3. Maintain the original Markdown structure strictly (headings, lists, tables, emphasis, blockquotes, etc.).\n"
    "4. Translate all visible human-readable text, including headings, table headers/cells, list items, and blockquotes.\n"
    "5. Keep Markdown syntax tokens unchanged (e.g., '#', '-', '>', '|', '```', ':::', '!!!', '???', link/image brackets/parentheses).\n"
    "6. Translate technical terms using standard {target_language} technical terminology where appropriate, "
    "but keep specific library names, function names, or variable names in English.\n"
    "7. If a line is just a symbol, delimiter, or formatting, keep it as is.\n"
    "8. If {current_language} is auto, detect the source language from the content."
)
