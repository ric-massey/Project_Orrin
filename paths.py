# paths.py
from pathlib import Path
from typing import Iterable

# ===== Base directories =====
ROOT_DIR  = Path(__file__).resolve().parent
DATA_DIR  = ROOT_DIR / "data"
THINK_DIR = ROOT_DIR / "think"
LOGS_DIR  = ROOT_DIR / "logs"
TESTS_DIR = ROOT_DIR / "tests"

# Ensure folders exist
for d in (DATA_DIR, THINK_DIR, LOGS_DIR, TESTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ===== Events & Outcome Log =====
EVENTS_FILE = DATA_DIR / "events.jsonl"
# NOTE: original code had a typo "evnets.json". We keep it for compatibility and add a fixed variant.
EVENTS_LOG = DATA_DIR / "evnets.json"     # legacy filename (typo preserved)
EVENTS_LOG_FIXED = DATA_DIR / "events.json"

# ===== General/System Files =====
THINK_MODULE_PATH = DATA_DIR / "think_module_text.txt"
PROMPT_FILE = DATA_DIR / "prompt.txt"
LOG_FILE = DATA_DIR / "log.txt"
ERROR_FILE = DATA_DIR / "error_log.txt"
ACTION_FILE = DATA_DIR / "action.json"
PRIVATE_THOUGHTS_FILE = DATA_DIR / "private_thoughts.txt"
ACTIVITY_LOG = DATA_DIR / "activity_log.txt"
MODEL_FAILURE = DATA_DIR / "model_failures.txt"
LAST_ACTIVE_FILE = DATA_DIR / "last_active.json"
REJECTED_THINK_FILE = DATA_DIR / "rejected_think_versions.txt"
CASUAL_RULES = DATA_DIR / "casual_rules.txt"
SANDBOX_LOG = DATA_DIR / "sandbox_log.json"
USER_INPUT = DATA_DIR / "user_input.txt"
LLM_PROMPT = DATA_DIR / "llm_prompt.txt"
BEHAVIORAL_FUNCTIONS_LIST_FILE = DATA_DIR / "behavioral_functions_list.json"
CONTRADICTIONS_FILE = DATA_DIR / "contradictions.json"

# ===== Model/Config/Concepts =====
SELF_MODEL_FILE = DATA_DIR / "self_model.json"
RELATIONSHIPS_FILE = DATA_DIR / "relationships.json"
MODEL_CONFIG_FILE = DATA_DIR / "model_config.json"
CONCEPTS_FILE = DATA_DIR / "concepts.json"
KNOWLEDGE = DATA_DIR / "knowledge_base.json"

# ===== Cognition =====
THINK_MODULE_PY = THINK_DIR / "think_module.py"
COGNITION_STATE_FILE = DATA_DIR / "cognition_state.json"
COGNITION_HISTORY_FILE = DATA_DIR / "cognition_history.json"
COGN_SCHEDULE_FILE = DATA_DIR / "cognition_schedule.json"
CURIOUS_GEORGE = DATA_DIR / "curiosity_threads.json"
WORLD_MODEL_RAW = DATA_DIR / "world_model_raw_response.txt"
WORLD_MODEL_BACKUP = DATA_DIR / "world_model_backup.txt"
WORLD_MODEL = DATA_DIR / "world_model.json"
WORLD_MODEL_ARCHIVE = DATA_DIR / "world_model_archive.json"
REFLECTION = DATA_DIR / "reflection_log.json"
ATTENTION_HISTORY = DATA_DIR / "attention_history.json"
COGNITIVE_FUNCTIONS_LIST_FILE = DATA_DIR / "cognitive_functions.json"

# ===== Tools =====
TOOLS_FILE = DATA_DIR / "tools_catalog.json"
TOOL_REQUESTS_FILE = DATA_DIR / "tool_requests.json"

# ===== Memory =====
CORE_MEMORY_FILE = DATA_DIR / "core_memory.json"
LONG_MEMORY_FILE = DATA_DIR / "long_memory.json"
WORKING_MEMORY_FILE = DATA_DIR / "working_memory.json"
CHAT_LOG_FILE = DATA_DIR / "chat_log.json"

# ===== Prompts/Context =====
REF_PROMPTS = DATA_DIR / "prompts.json"
CONTEXT = DATA_DIR / "context.json"

# ===== Goals =====
GOALS_FILE = DATA_DIR / "goals_mem.json"
COMPLETED_GOALS_FILE = DATA_DIR / "comp_goals.json"
FOCUS_GOAL = DATA_DIR / "focus_goals.json"
PROPOSED_GOALS = DATA_DIR / "proposed_goals.json"
EVOLUTION_FUTURES = DATA_DIR / "evolution_futures.json"
EVOLUTION_ROADMAPS = DATA_DIR / "evolution_roadmaps.json"

# ===== Feedback/Reward =====
FEEDBACK_LOG = DATA_DIR / "feedback_log.json"
REWARD_TRACE = DATA_DIR / "reward_trace.json"
LAST_TAGS = DATA_DIR / "last_tags.json"

# ===== Emotion =====
EMOTIONAL_STATE_FILE = DATA_DIR / "emotion_state.json"
EMOTIONAL_SENSITIVITY_FILE = DATA_DIR / "emotion_sensitivity.json"
EMOTION_MODEL_FILE = DATA_DIR / "emotion_model.json"
EMOTION_DRIFT = DATA_DIR / "emotion_drift.json"
CUSTOM_EMOTION = DATA_DIR / "custom_emotion.json"
MODE_FILE = DATA_DIR / "mode.json"
SPEAKER_STATE_FILE = DATA_DIR / "speaker_state.json"
EMOTION_FUNCTION_MAP_FILE = DATA_DIR / "emotion_function_map.json"

# ===== Cycle/Meta =====
CYCLE_COUNT_FILE = DATA_DIR / "cycle_count.json"

# ===== Dreams =====
DREAMSCAPE = DATA_DIR / "dreamscape.json"

# ===== Bandit / Learning =====
BANDIT_STATE_FILE = DATA_DIR / "bandit_state.json"

# ======= Additional paths from the os.path section (compat kept) =======
# Some use different names/casing; preserved to avoid breaking imports.
EMOTIONAL_STATE_JSON = DATA_DIR / "Emotional_state.json"     # note capital E as in original
COMPETENCE_JSON = DATA_DIR / "competence.json"
OUTCOMES_JSON = DATA_DIR / "Outcomes.json"
FEEDBACK_LOG_JSON = DATA_DIR / "feedback_log.json"
NEUTRAL_REFLECTION_COUNT_JSON = DATA_DIR / "neutral_reflection_count.json"
REWARD_TRACE_JSON = DATA_DIR / "reward_trace.json"
DEBUG_FAILED_GOAL_RESPONSE_JSON = ROOT_DIR / "debug_failed_goal_response.json"
FUNCTION_BANDIT_JSON = ROOT_DIR / "function_bandit.json"
GOAL_TRAJECTORY_LOG_JSON = DATA_DIR / "goal_trajectory_log.json"
MODEL_FAILURES_JSON = LOGS_DIR / "model_failures.json"
LONG_JSON = ROOT_DIR / "long.json"
PROMPTS_BACKUP_JSON = ROOT_DIR / "prompts_backup.json"
PROPOSED_TOOLS_JSON = ROOT_DIR / "proposed_tools.json"
SELF_MODEL_BACKUP_JSON = ROOT_DIR / "self_model_backup.json"
TOOL_CATALOG_JSON = ROOT_DIR / "tool_catalog.json"
TOOL_EVALUATIONS_JSON = ROOT_DIR / "tool_evaluations.json"
WORKING_JSON = ROOT_DIR / "working.json"
WORKING_TEST_JSON = TESTS_DIR / "working.json"
LONG_TEST_JSON = TESTS_DIR / "long.json"
BANDIT_STATE_JSON = DATA_DIR / "bandit_state.json"
CONTRADICTIONS_JSON = DATA_DIR / "contradictions.json"
EVOLUTION_ROADMAPS_JSON = DATA_DIR / "evolution_roadmaps.json"
CHAT_LOG_JSON = TESTS_DIR / "chat_log.json"
LONG_MEMORY_JSON = TESTS_DIR / "long_memory.json"
EMOTION_SENSITIVITY_JSON = DATA_DIR / "emotion_sensitivity.json"
STATE_SNAPSHOT_FILE = DATA_DIR / "state_snapshot.json"
MODEL_FAILURES_FILE = DATA_DIR / "model_failures.jsonl"
INCIDENTS_FILE = DATA_DIR / "incidents.jsonl"


# ===== Templates kept for format() call sites that expect strings =====
# If some legacy code does: BANDIT_JSON_TEMPLATE.format(ctx='x'), leave these as strings.
BANDIT_JSON_TEMPLATE = str(DATA_DIR / "bandit_{ctx}.json")
CACHE_JSON_TEMPLATE = str(DATA_DIR / "{k}.json")

# ===== Dynamic builders =====
def json_glob_path(pattern: str = "*.json") -> list[Path]:
    """Return all matching JSON files in DATA_DIR."""
    return list(DATA_DIR.glob(pattern))

def json_glob_all() -> list[Path]:
    """Convenience alias for all .json files in ROOT_DIR (legacy behavior used BASE_DIR)."""
    return list(ROOT_DIR.glob("*.json"))

def bandit_path(ctx: str) -> Path:
    """Path to bandit file for a given context."""
    return DATA_DIR / f"bandit_{ctx}.json"

def cache_file(k: str) -> Path:
    """Path to a cache file for a given key."""
    return DATA_DIR / f"{k}.json"

# ===== Optional helpers =====
def ensure_files(paths: Iterable[Path]) -> None:
    """Create empty files if they don't exist."""
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.touch()