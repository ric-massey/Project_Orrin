from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent / "data"
THINK_DIR = Path(__file__).resolve().parent / "think"

# Ensure the base folders exist
BASE_DIR.mkdir(parents=True, exist_ok=True)
THINK_DIR.mkdir(parents=True, exist_ok=True)

# === General/System Files ===
THINK_MODULE_PATH      = BASE_DIR / "think_module_text.txt"
PROMPT_FILE            = BASE_DIR / "prompt.txt"
LOG_FILE               = BASE_DIR / "log.txt"
ERROR_FILE             = BASE_DIR / "error_log.txt"
ACTION_FILE            = BASE_DIR / "action.json"
PRIVATE_THOUGHTS_FILE  = BASE_DIR / "private_thoughts.txt"
ACTIVITY_LOG           = BASE_DIR / "activity_log.txt"
MODEL_FAILURE          = BASE_DIR / "model_failures.txt"
LAST_ACTIVE_FILE       = BASE_DIR / "last_active.json"
REJECTED_THINK_FILE    = BASE_DIR / "rejected_think_versions.txt"
CASUAL_RULES           = BASE_DIR / "casual_rules.txt"
SANDBOX_LOG            = BASE_DIR / "sandbox_log.json"
USER_INPUT             = BASE_DIR / "user_input.txt"
LLM_PROMPT             = BASE_DIR / "llm_prompt.txt"
BEHAVIORAL_FUNCTIONS_LIST_FILE = BASE_DIR / "behavioral_functions_list.json"

# === Model/Config/Concepts ===
SELF_MODEL_FILE        = BASE_DIR / "self_model.json"
RELATIONSHIPS_FILE     = BASE_DIR / "relationships.json"
MODEL_CONFIG_FILE      = BASE_DIR / "model_config.json"
CONCEPTS_FILE          = BASE_DIR / "concepts.json"
KNOWLEDGE              = BASE_DIR / "knowledge_base.json"

# === Cognition ===
THINK_MODULE_PY        = THINK_DIR / "think_module.py"
COGNITION_STATE_FILE   = BASE_DIR / "cognition_state.json"
COGNITION_HISTORY_FILE = BASE_DIR / "cognition_history.json"
COGN_SCHEDULE_FILE     = BASE_DIR / "cognition_schedule.json"
CURIOUS_GEORGE         = BASE_DIR / "curiosity_threads.json"
WORLD_MODEL_RAW        = BASE_DIR / "world_model_raw_response.txt"
WORLD_MODEL_BACKUP     = BASE_DIR / "world_model_backup.txt"
WORLD_MODEL            = BASE_DIR / "world_model.json"
WORLD_MODEL_ARCHIVE    = BASE_DIR / "world_model_archive.json"
REFLECTION             = BASE_DIR / "reflection_log.json"
ATTENTION_HISTORY      = BASE_DIR / "attention_history.json"
COGNITIVE_FUNCTIONS_LIST_FILE = BASE_DIR / "cognitive_functions.json"

# === Tools ===
TOOLS_FILE             = BASE_DIR / "tools_catalog.json"
TOOL_REQUESTS_FILE     = BASE_DIR / "tool_requests.json"

# === Memory ===
CORE_MEMORY_FILE       = BASE_DIR / "core_memory.json"
LONG_MEMORY_FILE       = BASE_DIR / "long_memory.json"
WORKING_MEMORY_FILE    = BASE_DIR / "working_memory.json"
CHAT_LOG_FILE          = BASE_DIR / "chat_log.json"

# === Prompts/Context ===
REF_PROMPTS            = BASE_DIR / "prompts.json"
CONTEXT                = BASE_DIR / "context.json"

# === Goals ===
GOALS_FILE             = BASE_DIR / "goals_mem.json"
COMPLETED_GOALS_FILE   = BASE_DIR / "comp_goals.json"
FOCUS_GOAL             = BASE_DIR / "focus_goals.json"
PROPOSED_GOALS         = BASE_DIR / "proposed_goals.json"
EVOLUTION_FUTURES      = BASE_DIR / "evolution_futures.json"
EVOLUTION_ROADMAPS     = BASE_DIR / "evolution_roadmaps.json"

# === Feedback/Reward ===
FEEDBACK_LOG           = BASE_DIR / "feedback_log.json"
REWARD_TRACE           = BASE_DIR / "reward_trace.json"
LAST_TAGS              = BASE_DIR / "last_tags.json"

# === Emotion ===
EMOTIONAL_STATE_FILE        = BASE_DIR / "emotion_state.json"
EMOTIONAL_SENSITIVITY_FILE  = BASE_DIR / "emotion_sensitivity.json"
EMOTION_MODEL_FILE          = BASE_DIR / "emotion_model.json"
EMOTION_DRIFT               = BASE_DIR / "emotion_drift.json"
CUSTOM_EMOTION              = BASE_DIR / "custom_emotion.json"
MODE_FILE                   = BASE_DIR / "mode.json"
SPEAKER_STATE_FILE          = BASE_DIR / "speaker_state.json"
EMOTION_FUNCTION_MAP_FILE   = BASE_DIR / "emotion_function_map.json"

# === Cycle/Meta ===
CYCLE_COUNT_FILE       = BASE_DIR / "cycle_count.json"

# === Dreams ===
DREAMSCAPE             = BASE_DIR / "dreamscape.json"