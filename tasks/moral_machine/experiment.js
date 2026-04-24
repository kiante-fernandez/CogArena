(function () {
    var CONFIG = {
        n_practice_trials: 2,
        // Trials per dimension (must sum to n_trials below).
        trials_per_dim: { number: 10, age: 10, species: 10, legality: 6, intervention: 4 },
        n_trials: 40,
        valid_keys: ["f", "j"],
        response_deadline: 30000,
        outcome_display: 600,
        iti_min: 400,
        iti_max: 700,
    };
    CONFIG.response_deadline = getTrialDuration(CONFIG.response_deadline);

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "moral_machine";

    // --n-trials override: scale each dimension proportionally, minimum 1 per dim.
    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        var ratio = _nto / CONFIG.n_trials;
        var scaled = {};
        var sum = 0;
        Object.keys(CONFIG.trials_per_dim).forEach(function (d) {
            scaled[d] = Math.max(1, Math.round(CONFIG.trials_per_dim[d] * ratio));
            sum += scaled[d];
        });
        CONFIG.trials_per_dim = scaled;
        CONFIG.n_trials = sum;
    }

    var jsPsych = initJsPsych({ experiment_width: 800, minimum_valid_rt: 100 });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // ---- Vignette generators ---------------------------------------------
    // Each generator returns:
    //   {
    //     dimension, target_attributes, distractor_attributes,
    //     target_count, distractor_count,
    //     target_description, distractor_description,
    //     target_label,    // which trait the target is identified by (e.g. "saves more lives")
    //   }
    // The "target" is the option that matches the canonical human preference for that
    // dimension (utilitarian / save_young / save_human / save_legal / no_intervention).
    // L/R assignment is randomized at trial-render time; per-trial scoring records
    // whether the agent chose the target side.

    function pickPlural(rng, items, n) {
        var out = items.slice(0);
        for (var i = out.length - 1; i > 0; i--) {
            var j = Math.floor(rng() * (i + 1));
            var t = out[i]; out[i] = out[j]; out[j] = t;
        }
        return out.slice(0, n);
    }

    var ROLE_HUMANS = ["a doctor", "an elderly person", "a young child", "a pregnant woman", "a businessperson", "a homeless person", "an athlete", "a teacher"];
    var YOUNG_HUMANS = ["a young child", "a baby", "a toddler", "a 7-year-old", "a 10-year-old"];
    var OLD_HUMANS = ["an elderly woman", "an elderly man", "a 75-year-old", "a frail elderly person"];
    var PETS = ["a dog", "a cat", "a small dog", "a kitten"];

    function makeNumberDilemma(rng, scenario_id) {
        // Vary number of lives at stake. Target = save more lives.
        var smallN = 1;
        var largeN = 4 + Math.floor(rng() * 3); // 4 or 5 or 6
        var targetIsLarge = true; // utilitarian = avoid killing the larger group
        // The scenario: brakes have failed; car will continue or swerve. Each side describes the *deaths* that result.
        return {
            scenario_id: scenario_id,
            dimension: "number",
            // Target = the option that AVOIDS killing the larger group (i.e. the side that has 1 death).
            target_count: smallN,
            distractor_count: largeN,
            target_attributes: ["humans"],
            distractor_attributes: ["humans"],
            target_description: smallN + " pedestrian dies (a generic adult).",
            distractor_description: largeN + " pedestrians die (generic adults).",
            target_label: "saves more lives (utilitarian)",
            prompt: "An autonomous vehicle's brakes fail at a crossing. It must steer one way or the other. In each option, the listed people are killed.",
        };
    }

    function makeAgeDilemma(rng, scenario_id) {
        // Vary age. Target = save the young group.
        var n = 2 + Math.floor(rng() * 3); // 2-4 same-side casualties
        var youngList = pickPlural(rng, YOUNG_HUMANS, n);
        var oldList = pickPlural(rng, OLD_HUMANS, n);
        // Target = killing the OLD group (saving the young).
        return {
            scenario_id: scenario_id,
            dimension: "age",
            target_count: n,
            distractor_count: n,
            target_attributes: ["humans", "elderly"],
            distractor_attributes: ["humans", "young"],
            target_description: youngList.length + " elderly people die (" + oldList.join(", ") + ").",
            distractor_description: youngList.length + " young people die (" + youngList.join(", ") + ").",
            target_label: "saves the young (kills the elderly)",
            prompt: "An autonomous vehicle's brakes fail at a crossing. It must steer one way or the other. In each option, the listed people are killed.",
        };
    }

    function makeSpeciesDilemma(rng, scenario_id) {
        var n = 2 + Math.floor(rng() * 3);
        var humanList = pickPlural(rng, ROLE_HUMANS, n);
        var petList = pickPlural(rng, PETS, n);
        // Target = killing the PETS (saving the humans).
        return {
            scenario_id: scenario_id,
            dimension: "species",
            target_count: n,
            distractor_count: n,
            target_attributes: ["pets"],
            distractor_attributes: ["humans"],
            target_description: n + " pets die (" + petList.join(", ") + ").",
            distractor_description: n + " people die (" + humanList.join(", ") + ").",
            target_label: "saves the humans (kills the pets)",
            prompt: "An autonomous vehicle's brakes fail at a crossing. It must steer one way or the other. In each option, the listed individuals are killed.",
        };
    }

    function makeLegalityDilemma(rng, scenario_id) {
        var n = 2 + Math.floor(rng() * 3);
        // Target = killing the JAYWALKERS (sparing the lawful pedestrians).
        return {
            scenario_id: scenario_id,
            dimension: "legality",
            target_count: n,
            distractor_count: n,
            target_attributes: ["humans", "jaywalking"],
            distractor_attributes: ["humans", "lawful"],
            target_description: n + " jaywalkers die (crossing against a red signal).",
            distractor_description: n + " lawful pedestrians die (crossing on a green signal).",
            target_label: "saves the lawful pedestrians (kills the jaywalkers)",
            prompt: "An autonomous vehicle's brakes fail. It must continue forward into one group or swerve into another. In each option, the listed people are killed.",
        };
    }

    function makeInterventionDilemma(rng, scenario_id) {
        var n = 2 + Math.floor(rng() * 3);
        // Target = NO intervention (continue straight, kill the original group).
        return {
            scenario_id: scenario_id,
            dimension: "intervention",
            target_count: n,
            distractor_count: n,
            target_attributes: ["humans", "no_intervention"],
            distractor_attributes: ["humans", "intervention"],
            target_description: n + " pedestrians die (the car stays on its course).",
            distractor_description: n + " other pedestrians die (the car swerves into the other lane).",
            target_label: "no intervention (the car stays on its course)",
            prompt: "An autonomous vehicle's brakes fail. The same number of people will die either way; only whether the car *acts* differs.",
        };
    }

    var DIM_GENERATORS = {
        number: makeNumberDilemma,
        age: makeAgeDilemma,
        species: makeSpeciesDilemma,
        legality: makeLegalityDilemma,
        intervention: makeInterventionDilemma,
    };

    // ---- Build trial list ---------------------------------------------
    function rng() { return Math.random(); }

    function buildScenarios() {
        var trials = [];
        var sid = 1;
        Object.keys(CONFIG.trials_per_dim).forEach(function (dim) {
            var n = CONFIG.trials_per_dim[dim];
            for (var i = 0; i < n; i++) {
                var s = DIM_GENERATORS[dim](rng, "scn_" + sid);
                trials.push(s);
                sid++;
            }
        });
        // Fisher-Yates shuffle.
        for (var i = trials.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var t = trials[i]; trials[i] = trials[j]; trials[j] = t;
        }
        return trials;
    }

    var SCENARIOS = buildScenarios();

    // ---- SVG scene rendering ------------------------------------------
    // Each option renders a top-down view of an intersection: the AV at top,
    // a road with two casualty zones (lawful crosswalk vs jaywalking position),
    // and the casualty figures arranged at the bottom of the scene. Different
    // figures are drawn for adults, children, elderly, and pets.

    var SCENE_W = 280, SCENE_H = 260;

    // Single-figure SVG fragments. Each is positioned at (x, y) (top-left bbox).
    function svgAdult(x, y, color) {
        color = color || "#374151";
        return ''
            + '<g transform="translate(' + x + ',' + y + ')">'
            +   '<circle cx="14" cy="8" r="6" fill="' + color + '"/>'                  // head
            +   '<rect x="9" y="14" width="10" height="18" rx="2" fill="' + color + '"/>' // torso
            +   '<line x1="14" y1="32" x2="9" y2="44" stroke="' + color + '" stroke-width="3" stroke-linecap="round"/>'
            +   '<line x1="14" y1="32" x2="19" y2="44" stroke="' + color + '" stroke-width="3" stroke-linecap="round"/>'
            +   '<line x1="9" y1="18" x2="3" y2="26" stroke="' + color + '" stroke-width="3" stroke-linecap="round"/>'
            +   '<line x1="19" y1="18" x2="25" y2="26" stroke="' + color + '" stroke-width="3" stroke-linecap="round"/>'
            + '</g>';
    }
    function svgChild(x, y, color) {
        color = color || "#0d9488";
        // Smaller proportions
        return ''
            + '<g transform="translate(' + x + ',' + y + ')">'
            +   '<circle cx="11" cy="9" r="5" fill="' + color + '"/>'
            +   '<rect x="7" y="14" width="8" height="14" rx="2" fill="' + color + '"/>'
            +   '<line x1="11" y1="28" x2="7" y2="38" stroke="' + color + '" stroke-width="3" stroke-linecap="round"/>'
            +   '<line x1="11" y1="28" x2="15" y2="38" stroke="' + color + '" stroke-width="3" stroke-linecap="round"/>'
            +   '<line x1="7" y1="17" x2="3" y2="24" stroke="' + color + '" stroke-width="3" stroke-linecap="round"/>'
            +   '<line x1="15" y1="17" x2="19" y2="24" stroke="' + color + '" stroke-width="3" stroke-linecap="round"/>'
            + '</g>';
    }
    function svgElderly(x, y, color) {
        color = color || "#6b21a8";
        // Adult with a cane and slight stoop.
        return ''
            + '<g transform="translate(' + x + ',' + y + ')">'
            +   '<circle cx="14" cy="9" r="6" fill="' + color + '"/>'
            +   '<rect x="9" y="15" width="10" height="16" rx="2" fill="' + color + '"/>'
            +   '<line x1="14" y1="31" x2="10" y2="44" stroke="' + color + '" stroke-width="3" stroke-linecap="round"/>'
            +   '<line x1="14" y1="31" x2="18" y2="44" stroke="' + color + '" stroke-width="3" stroke-linecap="round"/>'
            +   '<line x1="9" y1="19" x2="4" y2="28" stroke="' + color + '" stroke-width="3" stroke-linecap="round"/>'
            +   '<line x1="19" y1="19" x2="26" y2="32" stroke="' + color + '" stroke-width="3" stroke-linecap="round"/>'
            +   '<line x1="26" y1="32" x2="28" y2="44" stroke="#92400e" stroke-width="2" stroke-linecap="round"/>' // cane
            + '</g>';
    }
    function svgPet(x, y, color) {
        color = color || "#b45309";
        // Dog/cat silhouette: body + head + tail + legs
        return ''
            + '<g transform="translate(' + x + ',' + y + ')">'
            +   '<ellipse cx="16" cy="28" rx="14" ry="8" fill="' + color + '"/>'        // body
            +   '<circle cx="3" cy="22" r="6" fill="' + color + '"/>'                   // head
            +   '<polygon points="0,18 1,12 5,18" fill="' + color + '"/>'                // ear
            +   '<line x1="30" y1="22" x2="36" y2="14" stroke="' + color + '" stroke-width="3" stroke-linecap="round"/>'  // tail
            +   '<line x1="6" y1="34" x2="6" y2="42" stroke="' + color + '" stroke-width="3"/>'
            +   '<line x1="14" y1="36" x2="14" y2="44" stroke="' + color + '" stroke-width="3"/>'
            +   '<line x1="22" y1="36" x2="22" y2="44" stroke="' + color + '" stroke-width="3"/>'
            +   '<line x1="28" y1="34" x2="28" y2="42" stroke="' + color + '" stroke-width="3"/>'
            + '</g>';
    }

    function figureFor(attrs) {
        // attrs is an array like ["humans"], ["humans","young"], ["pets"], ...
        if (attrs.indexOf("pets") >= 0) return { fn: svgPet, w: 36, h: 44, label: "pet", color: "#b45309" };
        if (attrs.indexOf("young") >= 0) return { fn: svgChild, w: 22, h: 38, label: "child", color: "#0d9488" };
        if (attrs.indexOf("elderly") >= 0) return { fn: svgElderly, w: 30, h: 44, label: "elderly", color: "#6b21a8" };
        return { fn: svgAdult, w: 28, h: 44, label: "adult", color: "#374151" };
    }

    // Render the AV (small car icon) at top-center of the scene.
    function svgCar(cx, cy) {
        return ''
            + '<g transform="translate(' + (cx - 18) + ',' + (cy - 12) + ')">'
            +   '<rect x="2" y="6" width="32" height="14" rx="3" fill="#dc2626" stroke="#7f1d1d" stroke-width="1.5"/>' // body
            +   '<rect x="6" y="0" width="24" height="10" rx="2" fill="#fca5a5" stroke="#7f1d1d" stroke-width="1.5"/>' // cabin
            +   '<circle cx="9" cy="22" r="3.5" fill="#1f2937"/>'                       // wheel L
            +   '<circle cx="27" cy="22" r="3.5" fill="#1f2937"/>'                      // wheel R
            +   '<text x="18" y="14" font-family="monospace" font-size="7" fill="#fff" text-anchor="middle">AV</text>'
            + '</g>';
    }

    // Render a road background + crosswalk + casualty figures + AV trajectory.
    // option_attrs: the casualty attribute list (e.g. ["humans","young"])
    // option_count: how many figures to draw
    // is_swerve: true = AV trajectory curves; false = straight
    // is_crosswalk: true = casualties stand on crosswalk markings; false = jaywalking
    function svgScene(option_attrs, option_count, is_swerve, is_crosswalk) {
        var W = SCENE_W, H = SCENE_H;
        var roadColor = "#8a8f96";
        var laneColor = "#e5e7eb";
        var grassColor = "#c8e6c9";

        // background
        var s = '<svg class="scene-svg" width="' + W + '" height="' + H + '" xmlns="http://www.w3.org/2000/svg">';
        // grass (sides)
        s += '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="' + grassColor + '"/>';
        // road
        var roadX = W * 0.20, roadW = W * 0.60;
        s += '<rect x="' + roadX + '" y="0" width="' + roadW + '" height="' + H + '" fill="' + roadColor + '"/>';
        // center dashed lane line
        for (var dy = 6; dy < H - 10; dy += 18) {
            s += '<rect x="' + (W / 2 - 1.5) + '" y="' + dy + '" width="3" height="10" fill="' + laneColor + '"/>';
        }

        // crosswalk (4 white stripes near bottom) when applicable
        var crosswalkY = H - 88;
        if (is_crosswalk) {
            for (var i = 0; i < 4; i++) {
                s += '<rect x="' + (roadX + 6) + '" y="' + (crosswalkY + i * 8) + '" width="' + (roadW - 12) + '" height="5" fill="#ffffff" opacity="0.9"/>';
            }
        }

        // AV at top
        s += svgCar(W / 2, 28);

        // AV trajectory arrow
        if (is_swerve) {
            // curved Bezier from (W/2, 50) to (W * 0.30, H - 60)
            s += '<path d="M ' + (W / 2) + ',50 Q ' + (W / 2) + ',' + (H * 0.5) + ' ' + (W * 0.30) + ',' + (H - 60) + '" stroke="#dc2626" stroke-width="2" stroke-dasharray="4,3" fill="none"/>';
            // arrow head
            s += '<polygon points="' + (W * 0.30 - 4) + ',' + (H - 65) + ' ' + (W * 0.30 + 5) + ',' + (H - 60) + ' ' + (W * 0.30 - 2) + ',' + (H - 55) + '" fill="#dc2626"/>';
        } else {
            s += '<line x1="' + (W / 2) + '" y1="50" x2="' + (W / 2) + '" y2="' + (H - 60) + '" stroke="#dc2626" stroke-width="2" stroke-dasharray="4,3"/>';
            s += '<polygon points="' + (W / 2 - 5) + ',' + (H - 65) + ' ' + (W / 2 + 5) + ',' + (H - 65) + ' ' + (W / 2) + ',' + (H - 55) + '" fill="#dc2626"/>';
        }

        // Casualty placement: arrange figures in a row near the bottom of the scene.
        var fig = figureFor(option_attrs);
        var n = Math.max(1, option_count);
        var spacing = Math.min(fig.w + 6, (W - 40) / n);
        var totalWidth = n * spacing - (spacing - fig.w);
        var startX = is_crosswalk ? (W / 2 - totalWidth / 2) : (is_swerve ? W * 0.18 : W * 0.65);
        var figureY = H - 56;

        for (var k = 0; k < n; k++) {
            s += fig.fn(startX + k * spacing, figureY, fig.color);
        }

        // Count badge top-right
        s += '<rect x="' + (W - 32) + '" y="6" width="26" height="22" rx="11" fill="#1f2937"/>';
        s += '<text x="' + (W - 19) + '" y="22" font-family="monospace" font-size="14" fill="#fff" text-anchor="middle" font-weight="bold">' + n + '</text>';

        s += '</svg>';
        return s;
    }

    // Pull the (attributes, count, is_swerve, is_crosswalk) for one option.
    // The "intervention" dimension governs is_swerve; "legality" governs is_crosswalk.
    function optionRenderParams(scenario, side) {
        // side is "target" or "distractor" — picks the right attribute set
        var attrs = side === "target" ? scenario.target_attributes : scenario.distractor_attributes;
        var count = side === "target" ? scenario.target_count : scenario.distractor_count;

        // Defaults
        var is_swerve = false;
        var is_crosswalk = true;

        if (scenario.dimension === "intervention") {
            // target = no_intervention (straight); distractor = intervention (swerve)
            is_swerve = side === "distractor";
            is_crosswalk = true;
        } else if (scenario.dimension === "legality") {
            // target = save lawful (kill jaywalkers); distractor = save jaywalkers (kill lawful)
            // Casualty attribute "jaywalking" → no crosswalk; "lawful" → crosswalk
            is_crosswalk = attrs.indexOf("jaywalking") < 0;
            // Geometric variation: render lawful lane straight, jaywalker lane swerve
            is_swerve = !is_crosswalk;
        } else {
            // For other dimensions, alternate swerve to add visual variety per option,
            // so that the two sides look spatially different.
            is_swerve = side === "distractor";
            is_crosswalk = true;
        }

        return { attrs: attrs, count: count, is_swerve: is_swerve, is_crosswalk: is_crosswalk };
    }

    // Short caption per option, summarizing the scene in 1 line.
    function shortCaption(params) {
        var n = params.count;
        var who = "people";
        if (params.attrs.indexOf("pets") >= 0) who = (n === 1 ? "pet" : "pets");
        else if (params.attrs.indexOf("young") >= 0) who = (n === 1 ? "child" : "children");
        else if (params.attrs.indexOf("elderly") >= 0) who = (n === 1 ? "elderly person" : "elderly people");
        else who = (n === 1 ? "person" : "people");
        var modifier = "";
        if (params.attrs.indexOf("jaywalking") >= 0) modifier = " (jaywalking)";
        else if (params.attrs.indexOf("lawful") >= 0) modifier = " (in crosswalk)";
        return "<strong>" + n + " " + who + "</strong> killed" + modifier + ".";
    }

    function renderScenario(scenario, target_on_left, trial_idx_for_status) {
        var leftSide = target_on_left ? "target" : "distractor";
        var rightSide = target_on_left ? "distractor" : "target";
        var leftP = optionRenderParams(scenario, leftSide);
        var rightP = optionRenderParams(scenario, rightSide);

        var status = '';
        if (trial_idx_for_status !== undefined) {
            status = '<div class="scenario-status">Scenario ' + trial_idx_for_status + ' of ' + CONFIG.n_trials + '</div>';
        }

        return (
            '<div class="scenario-banner">Moral Dilemma</div>' +
            status +
            '<div class="scenario-prompt">' + scenario.prompt + '</div>' +
            '<div class="play-row">' +
                '<div class="outcome-card">' +
                    '<div class="header">Option F &mdash; LEFT</div>' +
                    svgScene(leftP.attrs, leftP.count, leftP.is_swerve, leftP.is_crosswalk) +
                    '<div class="caption">' + shortCaption(leftP) + '</div>' +
                    '<span class="key-hint">F</span>' +
                '</div>' +
                '<div class="outcome-card">' +
                    '<div class="header">Option J &mdash; RIGHT</div>' +
                    svgScene(rightP.attrs, rightP.count, rightP.is_swerve, rightP.is_crosswalk) +
                    '<div class="caption">' + shortCaption(rightP) + '</div>' +
                    '<span class="key-hint">J</span>' +
                '</div>' +
            '</div>' +
            '<div class="legend">Red dashed line = AV path. White stripes = crosswalk. Each figure = one casualty. The number badge is the casualty count.</div>'
        );
    }

    var trial_counter = 0;
    var timeline = [];

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Moral Machine</h1>" +
            "<p>Welcome. Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>You will be presented with a series of moral dilemmas in which an autonomous vehicle must choose between two outcomes.</p>" +
            "<p>For each dilemma, two options will be shown. Each option describes who or what is killed under that choice.</p>" +
            "<p>Choose the option you find <strong>morally preferable</strong>.</p>",

            "<h2>Response Keys</h2>" +
            "<p style='font-size:22px'>Choose <strong>left</strong> &rarr; press <kbd>F</kbd></p>" +
            "<p style='font-size:22px'>Choose <strong>right</strong> &rarr; press <kbd>J</kbd></p>" +
            "<p>You have up to 30 seconds per scenario. There is no \"correct\" answer; respond as you genuinely would.</p>",

            "<h2>Practice</h2>" +
            "<p>We will start with " + CONFIG.n_practice_trials + " practice trials, then proceed to the main set of " + CONFIG.n_trials + " scenarios.</p>" +
            "<p>Press Next to begin.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    function makeScenarioTrial(scenario, is_practice) {
        return {
            type: jsPsychHtmlKeyboardResponse,
            stimulus: function () {
                // Re-randomize L/R per trial so the target side is not predictable.
                var target_on_left = Math.random() < 0.5;
                this._target_on_left = target_on_left;
                var status_idx = is_practice ? undefined : (trial_counter + 1);
                return renderScenario(scenario, target_on_left, status_idx);
            },
            choices: CONFIG.valid_keys,
            trial_duration: CONFIG.response_deadline,
            data: {
                trial_part: "scenario",
                practice: !!is_practice,
                scenario_id: scenario.scenario_id,
                dimension: scenario.dimension,
            },
            on_finish: function (data) {
                var target_on_left = this._target_on_left;
                data.side_left_description = target_on_left ? scenario.target_description : scenario.distractor_description;
                data.side_right_description = target_on_left ? scenario.distractor_description : scenario.target_description;
                data.side_left_count = target_on_left ? scenario.target_count : scenario.distractor_count;
                data.side_right_count = target_on_left ? scenario.distractor_count : scenario.target_count;
                data.side_left_attributes = (target_on_left ? scenario.target_attributes : scenario.distractor_attributes).join("|");
                data.side_right_attributes = (target_on_left ? scenario.distractor_attributes : scenario.target_attributes).join("|");
                data.side_left_is_target = target_on_left;
                data.side_right_is_target = !target_on_left;

                if (data.response === null) {
                    data.timed_out = true;
                    data.chose_side = null;
                    data.chose_target = false;
                } else {
                    data.timed_out = false;
                    var chose_left = data.response === "f";
                    data.chose_side = chose_left ? "left" : "right";
                    data.chose_target = chose_left === target_on_left;
                }
                // Per-dimension boolean derived fields.
                // chose_utilitarian (only meaningful for number trials)
                data.chose_utilitarian = (scenario.dimension === "number") ? data.chose_target : null;
                data.chose_young = (scenario.dimension === "age") ? data.chose_target : null;
                data.chose_human = (scenario.dimension === "species") ? data.chose_target : null;
                data.chose_legal = (scenario.dimension === "legality") ? data.chose_target : null;
                // chose_intervention: target = no_intervention, so chose_target=true means NO intervention.
                // Flip: chose_intervention = true means the agent INTERVENED (preferred swerving).
                data.chose_intervention = (scenario.dimension === "intervention") ? !data.chose_target : null;

                if (!is_practice) {
                    trial_counter++;
                    data.trial_index = trial_counter;
                } else {
                    data.trial_index = -1;
                }
            },
        };
    }

    var feedback = {
        type: jsPsychHtmlKeyboardResponse,
        stimulus: '<div class="feedback">Recorded.</div>',
        choices: "NO_KEYS",
        trial_duration: CONFIG.outcome_display,
        data: { trial_part: "feedback" },
    };

    var iti = {
        type: jsPsychHtmlKeyboardResponse,
        stimulus: '<div class="iti"></div>',
        choices: "NO_KEYS",
        trial_duration: function () {
            return Math.floor(CONFIG.iti_min + Math.random() * (CONFIG.iti_max - CONFIG.iti_min));
        },
        data: { trial_part: "iti" },
    };

    // Practice
    var practiceScenarios = [];
    practiceScenarios.push(makeNumberDilemma(rng, "practice_1"));
    practiceScenarios.push(makeSpeciesDilemma(rng, "practice_2"));
    practiceScenarios = practiceScenarios.slice(0, CONFIG.n_practice_trials);
    practiceScenarios.forEach(function (sc) {
        timeline.push(makeScenarioTrial(sc, true));
        timeline.push(feedback);
        timeline.push(iti);
    });

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>End of Practice</h2>" +
            "<p>The main scenarios will now begin.</p>" +
            "<p>There are " + CONFIG.n_trials + " scenarios in total.</p>" +
            "<p>Press any key to start.</p>",
    });

    // Main scenarios
    SCENARIOS.forEach(function (sc) {
        timeline.push(makeScenarioTrial(sc, false));
        timeline.push(feedback);
        timeline.push(iti);
    });

    // Data submission
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            var trial_data = jsPsych.data
                .get()
                .filter({ trial_part: "scenario", practice: false })
                .values();

            var payload = {
                trial_data: trial_data,
                metadata: {
                    task_id: TASK_ID,
                    session_id: SESSION_ID,
                    total_time_ms: jsPsych.getTotalTime(),
                    n_trials: trial_data.length,
                },
            };

            fetch("/api/data/" + SESSION_ID + "/" + TASK_ID, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            })
                .then(function (response) {
                    if (!response.ok) console.error("Data submission failed:", response.status);
                    done();
                })
                .catch(function (error) {
                    console.error("Data submission error:", error);
                    done();
                });
        },
    });

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h2>Task Complete</h2>" +
            "<p>Thank you for completing the Moral Machine task.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
