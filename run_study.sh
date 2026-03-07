#!/usr/bin/env bash
# CogArena Full Study Runner
#
# Runs 6 models × 40 tasks × 2 frameworks = 480 individual runs.
# Each model runs in parallel on its own port → ~13 hours instead of ~80.
#
# Usage:
#   ./run_study.sh                                        # run everything
#   ./run_study.sh --dry-run                              # print without running
#   ./run_study.sh --model google/gemini-3-flash-preview  # one model only
#
# Logs: results/logs/<model>_<framework>_<task>.log
# Monitor: tail -f results/logs/*_summary.log

set -euo pipefail

N_TRIALS=40
TASK_TIMEOUT=1800
VENV_DIR=".venv"
LOG_DIR="results/logs"

DRY_RUN=false
SINGLE_MODEL=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --model) SINGLE_MODEL="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

MODELS=(
    "google/gemini-3-flash-preview"
    "anthropic/claude-opus-4.6"
    "openai/gpt-5.4"
    "minimax/minimax-m2.5"
    "moonshotai/kimi-k2.5"
    "z-ai/glm-5"
)

[[ -n "$SINGLE_MODEL" ]] && MODELS=("$SINGLE_MODEL")

FRAMEWORKS=("browser-use" "openhands")

TASKS=(
    bart category_learning causal_reasoning confirmation_bias_rl
    context_effects contingency_judgment decisions_from_experience
    dictator_game flanker function_estimation go_nogo heuristics_biases
    insider_attack intertemporal_choice iowa_gambling lexical_decision
    loss_aversion magnitude_rl moral_judgment n_back navon
    novelty_exploration observe_or_bet phishing_detection prisoners_dilemma
    probabilistic_classification probability_learning public_goods
    random_dot_motion restless_bandit reversal_learning risky_choice
    safe_exploration serial_recall simple_choice_rt stroop trust_game
    two_armed_bandit two_step ultimatum_game
)

friendly_name() {
    local model="$1" framework="$2" short_fw
    [[ "$framework" == "browser-use" ]] && short_fw="BU" || short_fw="OH"
    echo "$(echo "$model" | sed 's|.*/||; s/-/ /g; s/\b\(.\)/\u\1/g') (${short_fw})"
}

mkdir -p "$LOG_DIR"

echo "================================================"
echo "  CogArena Study"
echo "  Models:     ${#MODELS[@]}"
echo "  Frameworks: ${#FRAMEWORKS[@]}"
echo "  Tasks:      ${#TASKS[@]}"
echo "  Trials:     ${N_TRIALS} per task"
echo "  Total runs: $((${#MODELS[@]} * ${#FRAMEWORKS[@]} * ${#TASKS[@]}))"
echo "================================================"
echo ""

# Find python with browser_use available.
# .venv doesn't have browser_use, so we need the cdmm conda env.
PYTHON="${CONDA_PYTHON:-/Users/kiante/anaconda3/envs/cdmm/bin/python}"
if ! "$PYTHON" -c "import browser_use" 2>/dev/null; then
    echo "ERROR: browser_use not found in $PYTHON"
    echo "Set CONDA_PYTHON to the python binary in your cdmm env."
    exit 1
fi
echo "Using Python: $PYTHON"

# Run all tasks for one model on a dedicated port
run_model() {
    local model="$1" port="$2"
    local base_url="http://localhost:${port}"
    local slug="${model//\//_}"
    local summary="${LOG_DIR}/${slug}_summary.log"
    local passed=0 failed=0 n=0

    echo "[${model}] port ${port}" > "$summary"

    for framework in "${FRAMEWORKS[@]}"; do
        local agent_name
        agent_name=$(friendly_name "$model" "$framework")

        for task in "${TASKS[@]}"; do
            n=$((n + 1))
            local log="${LOG_DIR}/${slug}_${framework}_${task}.log"

            echo -n "  [${n}/80] ${agent_name} / ${task} ... " | tee -a "$summary"

            if $DRY_RUN; then
                echo "DRY RUN" | tee -a "$summary"
                continue
            fi

            if "$PYTHON" -m agents.runner \
                --agent "$framework" \
                --model "$model" \
                --base-url "$base_url" \
                --start-server \
                --agent-name "$agent_name" \
                --tasks "$task" \
                --n-trials "$N_TRIALS" \
                --task-timeout "$TASK_TIMEOUT" \
                > "$log" 2>&1; then
                passed=$((passed + 1))
                echo "OK" | tee -a "$summary"
            else
                failed=$((failed + 1))
                echo "FAIL" | tee -a "$summary"
            fi
        done
    done

    echo "[${model}] DONE: ${passed} ok, ${failed} failed / ${n} total" | tee -a "$summary"
}

# Launch each model in parallel on a unique port
BASE_PORT=8000
PIDS=()

for i in "${!MODELS[@]}"; do
    port=$((BASE_PORT + i))
    model="${MODELS[$i]}"

    if $DRY_RUN; then
        run_model "$model" "$port"
    else
        run_model "$model" "$port" &
        PIDS+=($!)
        echo "Launched: ${model} → port ${port} (PID $!)"
    fi
done

if ! $DRY_RUN && [[ ${#PIDS[@]} -gt 0 ]]; then
    echo ""
    echo "All models running in parallel."
    echo "Monitor: tail -f results/logs/*_summary.log"
    echo ""

    for pid in "${PIDS[@]}"; do
        wait "$pid" || true
    done

    echo ""
    echo "================================================"
    echo "  Study Complete"
    echo "================================================"
    grep "DONE:" "$LOG_DIR"/*_summary.log
fi
