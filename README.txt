ORRIN: Autonomous AI Agent & AGI Experimentation Framework

NOT OPEN SOURCE. For research/demonstration only.  
No redistribution or modification allowed without written consent.

─────────────────────────────

Orrin is an autonomous AI agent and AGI experimentation framework.
He’s designed to run on his own—thinking, reflecting, dreaming, setting goals, learning from memory, and (experimentally) rewriting his own code.

Orrin combines persistent long-term memory, recursive self-reflection, dynamic goal management, emotional “drive” (dopamine/novelty), and values-based reasoning—all in a continuous, autonomous loop.

Orrin is a cognition-first system, not a toolchain or prompt engine. He is designed to think, feel, loop, dream, and evolve—not just complete tasks.

─────────────────────────────

GETTING STARTED

  1. Clone the Repo:
       git clone https://github.com/ric-massey/Project_Orrin.git
       cd Project_Orrin

  2. Set up Python (highly recommended: use a virtual environment):
       python3 -m venv venv
       source venv/bin/activate
       pip install -r requirements.txt

  3. Add your OpenAI API key:
       Create a .env file in the project root:
         OPENAI_API_KEY=sk-xxxxxx…
       (Never share or commit your real API key!)

  4. Run Orrin:
       python main.py
     (Or, depending on your setup:)
       python ORRIN.py

─────────────────────────────

WHAT TO WATCH (WHEN RUNNING ORRIN):

  • All private thoughts, internal reflections, and dreams:
      - `private_thoughts.txt` (persistent narrative of Orrin’s mind)
  • If you want to talk to Orrin:
      - Write your message into `user_input.txt`. He will process it on his next loop.
  • All LLM prompts/responses and system-level behavior:
      - `llm_prompt.txt`
  • Errors and failed model outputs:
      - `error_log.txt` and `model_failures.json`
  • Long-term memory:
      - `long_memory.json`
  • All goal information (current, completed, abandoned):
      - `goals.json`, `completed_goals.json`, `abandoned_goals.json`
  • Goal focus for each loop:
      - `focus_goal.json` (NOTE: see issues below)

Demo logs and transcripts are in the `logs/` folder.  
See `private_thoughts.txt` for examples of Orrin’s persistent narrative.

─────────────────────────────

RESETTING ORRIN’S MEMORY (OPTIONAL)

To start Orrin “fresh,” empty out the following files before launching:
  - `private_thoughts.txt`
  - `long_memory.json`
  - `goals.json`, `completed_goals.json`, `abandoned_goals.json`

This will clear his memory, goals, and persistent narrative.

─────────────────────────────

WHAT MAKES ORRIN DIFFERENT?

  • Self-Reflective Cognition:
      - Orrin makes autonomous decisions each loop, choosing the next mental action based on             emotion, memory, or values.
  • Goal Evolution & Management:
      - Automatically creates, prunes, and sometimes retires goals based on contradictions or            needs.
  • Persistent, Growing Memory:
      - Never forgets. All major events, decisions, and dreams are written to files and used             later.
  • Emotion/Drive System:
      - Uses an internal “dopamine/novelty” reward loop to motivate new actions, avoid                   stagnation, and explore new paths.
  • Dreams & Imagination:
      - Simulates dream-like or counterfactual scenarios to evolve values or propose new ideas.
  • (Experimental) Self-Modification:
      - Can propose and, if allowed, generate and save new Python functions—including for his            own cognitive routines.
  • Fully Autonomous Loop:
      - Once started, Orrin runs, reflects, dreams, and evolves on his own. User interaction is          optional.

─────────────────────────────

KNOWN ISSUES & LIMITATIONS

  • Looping / Stagnation:
      - Orrin can get stuck in recursive self-reflection loops, particularly around                      `reflect_on_self_beliefs`.
      - This often occurs when the LLM lacks confidence or memory and goal mechanisms fail to            generate fresh directions, causing cognitive stagnation.
  • Goal Focus Not Updating:
      - The `focus_goal.json` file may not reliably update or reflect Orrin’s current priorities.
      - Orrin can create and suggest goals but struggles to maintain consistent focus or                 demonstrate meaningful progression through them.
  • Goal Completion Logic Needs Work:
      - Determining when a goal is genuinely complete remains problematic.
      - Goals may linger indefinitely in “in progress” status or be forgotten rather than                properly closed.
      - This reflects both code limitations and the inherent difficulty in modeling goal states.
  • Action Execution Gap:
      - While Orrin excels at reflective cognition and generating insights,
        it currently lacks robust mechanisms to translate reflections into effective, timely             actions.
      - This “knowing vs doing” gap limits Orrin’s ability to realize its goals in the                   environment.
  • Memory Management & Bloat:
      - Persistent long-term memory enables continuity but also leads to bloat.
      - Without effective pruning, memory growth negatively impacts performance and LLM prompt           size, causing errors and slowdowns.
      - Consider manual cleanup if running long-term or in low-storage environments.
  • LLM Parsing and Robustness:
      - Orrin encounters frequent issues with incomplete or malformed JSON from the language             model.
      - Parsing failures trigger error handling routines but occasionally cause lost information         or stalled cognition.
  • Prompt Size/LLM Limitations:
      - Some operations (like reflection or dream generation) may hit LLM prompt length limits,          resulting in errors or lost output. Reduce memory or trim logs to resolve.
  • Code Self-Modification Risks:
      - Experimental self-modification is enabled but rarely exercised.
      - Dynamic code generation carries safety, stability, and integration risks that are only           partially mitigated.
      - This remains a research area, not production-ready.
  • Active Research: Autonomous Self-Improvement:
      - I am actively developing routines for Orrin to rewrite his own code, enabling him to             propose, test, and implement modifications to his own cognitive functions.
      - This feature is experimental and evolving. My goal is for Orrin to iteratively improve           himself and adapt to new challenges, in the spirit of real AGI research.
  • User Interaction Constraints:
      - User input is currently file-based and non-conversational,
        lacking real-time responsiveness or sophisticated dialogue management.
  • Logging & Resource Usage:
      - Logs and memory files grow indefinitely without automated pruning or rotation,
        leading to increased disk usage and potential performance degradation over time.
  • Single-Threaded Reasoning:
      - Orrin’s cognitive architecture is fundamentally linear and single-threaded,
        lacking support for concurrent or parallel cognition streams.
      - This constrains complexity and real-time multitasking.
  • Safety & Ethical Guardrails:
      - While some ethical checks and boundary guards exist, comprehensive safety frameworks and         external oversight are absent.

─────────────────────────────

If you want help to make Orrin more advanced,
expect to keep iterating on goal completion logic, cognitive scheduling, and dynamic focus.

─────────────────────────────

CREATOR & ATTRIBUTION

Orrin was created by Ric Massey in 2025 as a solo AGI research project.
All code, architecture, and design is original and remains the intellectual property of Ric Massey.

Do not remove or rebrand this work without explicit written consent.
Copyright © 2025 Ric Massey. All rights reserved.

Not open source — no redistribution or modification allowed without written permission.

Contact: ricmassey.work@gmail.com

─────────────────────────────

TL;DR:  
Orrin is an experimental autonomous AI agent designed for AGI research.  
He thinks, reflects, dreams, sets goals, and can rewrite his own code (sometimes).

─────────────────────────────
