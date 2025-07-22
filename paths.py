import os

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
THINK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "think")

# === General/System Files ===
THINK_MODULE_PATH    = os.path.join(BASE_DIR, "think_module_text.txt")
PROMPT_FILE          = os.path.join(BASE_DIR, "prompt.txt")
LOG_FILE             = os.path.join(BASE_DIR, "log.txt")
ERROR_FILE           = os.path.join(BASE_DIR, "error_log.txt")
ACTION_FILE          = os.path.join(BASE_DIR, "action.json")
PRIVATE_THOUGHTS_FILE= os.path.join(BASE_DIR, "private_thoughts.txt")
ACTIVITY_LOG         = os.path.join(BASE_DIR, "activity_log.txt")
MODEL_FAILURE        = os.path.join(BASE_DIR, "model_failures.txt")
LAST_ACTIVE_FILE     = os.path.join(BASE_DIR, "last_active.json")
REJECTED_THINK_FILE  = os.path.join(BASE_DIR, "rejected_think_versions.txt")
CASUAL_RULES         = os.path.join(BASE_DIR, "casual_rules.txt")
SANDBOX_LOG          = os.path.join(BASE_DIR, "sandbox_log.json")
USER_INPUT           = os.path.join(BASE_DIR, "user_input.txt")
LLM_PROMPT           = os.path.join(BASE_DIR, "llm_prompt.txt")

# === Model/Config/Concepts ===
SELF_MODEL_FILE      = os.path.join(BASE_DIR, "self_model.json")
RELATIONSHIPS_FILE   = os.path.join(BASE_DIR, "relationships.json")
MODEL_CONFIG_FILE    = os.path.join(BASE_DIR, "model_config.json")
CONCEPTS_FILE        = os.path.join(BASE_DIR, "concepts.json")
KNOWLEDGE            = os.path.join(BASE_DIR, "knowledge_base.json")

# === Cognition ===
THINK_MODULE_PY        = os.path.join(THINK, "think_module.py")
COGNITION_STATE_FILE   = os.path.join(BASE_DIR, "cognition_state.json")
COGNITION_HISTORY_FILE = os.path.join(BASE_DIR, "cognition_history.json")
COGN_SCHEDULE_FILE     = os.path.join(BASE_DIR, "cognition_schedule.json")
CURIOUS_GEORGE         = os.path.join(BASE_DIR, "curiosity_threads.json")
WORLD_MODEL_RAW        = os.path.join(BASE_DIR, "world_model_raw_response.txt")
WORLD_MODEL_BACKUP     = os.path.join(BASE_DIR, "world_model_backup.txt")
WORLD_MODEL            = os.path.join(BASE_DIR, "world_model.json")
WORLD_MODEL_ARCHIVE    = os.path.join(BASE_DIR, "world_model_archive.json")
REFLECTION             = os.path.join(BASE_DIR, "reflection_log.json")
ATTENTION_HISTORY      = os.path.join(BASE_DIR, "attention_history.json")

# === Tools ===
TOOLS_FILE         = os.path.join(BASE_DIR, "tools_catalog.json")
TOOL_REQUESTS_FILE = os.path.join(BASE_DIR, "tool_requests.json")

# === Memory ===
CORE_MEMORY_FILE      = os.path.join(BASE_DIR, "core_memory.json")
LONG_MEMORY_FILE      = os.path.join(BASE_DIR, "long_memory.json")
WORKING_MEMORY_FILE   = os.path.join(BASE_DIR, "working_memory.json")
CHAT_LOG_FILE         = os.path.join(BASE_DIR, "chat_log.json")

# === Prompts/Context ===
REF_PROMPTS           = os.path.join(BASE_DIR, "prompts.json")
CONTEXT               = os.path.join(BASE_DIR, "context.json")

# === Goals ===
GOALS_FILE            = os.path.join(BASE_DIR, "goals_mem.json")
COMPLETED_GOALS_FILE  = os.path.join(BASE_DIR, "comp_goals.json")
FOCUS_GOAL            = os.path.join(BASE_DIR, "focus_goals.json")
PROPOSED_GOALS        = os.path.join(BASE_DIR, "proposed_goals.json")

# === Feedback/Reward ===
FEEDBACK_LOG          = os.path.join(BASE_DIR, "feedback_log.json")
REWARD_TRACE          = os.path.join(BASE_DIR, "reward_trace.json")
LAST_TAGS             = os.path.join(BASE_DIR, "last_tags.json")

# === Emotion ===
EMOTIONAL_STATE_FILE        = os.path.join(BASE_DIR, "emotion_state.json")
EMOTIONAL_SENSITIVITY_FILE  = os.path.join(BASE_DIR, "emotion_sensitivity.json")
EMOTION_MODEL_FILE          = os.path.join(BASE_DIR, "emotion_model.json")
EMOTION_DRIFT               = os.path.join(BASE_DIR, "emotion_drift.json")
CUSTOM_EMOTION              = os.path.join(BASE_DIR, "custom_emotion.json")
MODE_FILE                   = os.path.join(BASE_DIR, "mode.json")
SPEAKER_STATE_FILE          = os.path.join(BASE_DIR, "speaker_state.json")

# === Cycle/Meta ===
CYCLE_COUNT_FILE      = os.path.join(BASE_DIR, "cycle_count.json")

# === Dreams ===
DREAMSCAPE            = os.path.join(BASE_DIR, "dreamscape.json")