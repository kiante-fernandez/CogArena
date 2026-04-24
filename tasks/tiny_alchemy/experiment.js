(function () {
    var CONFIG = {
        time_cap_minutes: 12,
        max_combinations: 200,
    };

    var urlParams = new URLSearchParams(window.location.search);
    var SESSION_ID = urlParams.get("session_id") || "debug";
    var TASK_ID = "tiny_alchemy";

    var _nto = parseInt(urlParams.get("n_trials"));
    if (!isNaN(_nto) && _nto > 0) {
        CONFIG.max_combinations = _nto;
    }

    var jsPsych = initJsPsych({
        experiment_width: 900,
        minimum_valid_rt: 50,
    });
    if (SESSION_ID === "debug") window._jsPsych = jsPsych;

    // ---- Game data + lookups ----
    var GAME = null;          // {elements, base_elements, recipes, n_elements}
    var BY_RECIPE = null;     // "elem1,elem2" (sorted) -> [result_idx, ...]
    var IN_DEGREE = null;     // element_idx -> n_recipes that produce it
    var RECIPES_USING_ELEMENT = null;  // element_idx -> n_recipes that *use* it
    var GAME_LOAD_PROMISE = fetch("/tasks/tiny_alchemy/assets/alchemy_data.json", { cache: "force-cache" })
        .then(function (r) { return r.json(); })
        .then(function (game) {
            GAME = game;
            BY_RECIPE = {};
            IN_DEGREE = new Array(game.n_elements).fill(0);
            RECIPES_USING_ELEMENT = new Array(game.n_elements).fill(0);
            for (var i = 0; i < game.n_elements; i++) {
                var rs = game.recipes[i];
                IN_DEGREE[i] = rs.length;
                for (var j = 0; j < rs.length; j++) {
                    var pair = rs[j].slice().sort(function (a, b) { return a - b; });
                    var key = pair[0] + "," + pair[1];
                    if (!BY_RECIPE[key]) BY_RECIPE[key] = [];
                    BY_RECIPE[key].push(i);
                    RECIPES_USING_ELEMENT[pair[0]] += 1;
                    if (pair[1] !== pair[0]) RECIPES_USING_ELEMENT[pair[1]] += 1;
                }
            }
        })
        .catch(function (err) { console.error("Failed to load alchemy data:", err); });

    // ---- Game state ----
    var inventory = [];          // ordered list of element indices owned
    var inventorySet = null;     // Set of indices for fast lookup
    var attempts = [];           // recorded combinations, one per attempt
    var startTime = null;
    var trialCounter = 0;

    function nameOf(idx) { return GAME.elements[idx]; }
    function isBase(idx) { return GAME.base_elements.indexOf(idx) >= 0; }

    // ---- Element icon mapping (substring-based, defaults to ✨) ----
    var ICON_MAP = [
        // Base elements
        ["water", "💧"], ["fire", "🔥"], ["earth", "🌍"], ["air", "💨"],
        // Common compounds
        ["rain", "🌧️"], ["cloud", "☁️"], ["snow", "❄️"], ["ice", "🧊"], ["steam", "♨️"],
        ["lava", "🌋"], ["mud", "🟫"], ["sand", "🏜️"], ["stone", "🪨"], ["mountain", "⛰️"],
        ["sun", "☀️"], ["moon", "🌙"], ["star", "⭐"], ["lightning", "⚡"],
        ["tree", "🌳"], ["flower", "🌸"], ["grass", "🌿"], ["plant", "🌱"], ["leaf", "🍃"],
        ["seed", "🌰"], ["wood", "🪵"], ["forest", "🌲"], ["fruit", "🍎"], ["vegetable", "🥕"],
        // Animals
        ["dragon", "🐉"], ["dog", "🐕"], ["cat", "🐈"], ["bird", "🐦"], ["fish", "🐟"],
        ["horse", "🐴"], ["cow", "🐄"], ["pig", "🐖"], ["sheep", "🐑"], ["chicken", "🐔"],
        ["rabbit", "🐇"], ["mouse", "🐁"], ["snake", "🐍"], ["frog", "🐸"], ["bear", "🐻"],
        ["wolf", "🐺"], ["lion", "🦁"], ["tiger", "🐅"], ["monkey", "🐒"], ["elephant", "🐘"],
        ["bee", "🐝"], ["butterfly", "🦋"], ["spider", "🕷️"], ["ant", "🐜"], ["dinosaur", "🦖"],
        ["unicorn", "🦄"], ["whale", "🐋"], ["shark", "🦈"], ["octopus", "🐙"], ["turtle", "🐢"],
        // Mythical / special
        ["wizard", "🧙"], ["witch", "🧙‍♀️"], ["ghost", "👻"], ["zombie", "🧟"], ["vampire", "🧛"],
        ["angel", "👼"], ["devil", "😈"], ["robot", "🤖"], ["alien", "👽"], ["fairy", "🧚"],
        ["knight", "🛡️"], ["pirate", "🏴‍☠️"], ["ninja", "🥷"], ["samurai", "⚔️"],
        // Tech/objects
        ["car", "🚗"], ["plane", "✈️"], ["boat", "⛵"], ["rocket", "🚀"], ["bicycle", "🚲"],
        ["train", "🚂"], ["truck", "🚚"], ["motorcycle", "🏍️"], ["ship", "🚢"],
        ["computer", "💻"], ["phone", "📱"], ["camera", "📷"], ["clock", "⏰"], ["watch", "⌚"],
        ["bomb", "💣"], ["sword", "🗡️"], ["gun", "🔫"], ["axe", "🪓"], ["hammer", "🔨"],
        ["bow", "🏹"], ["shield", "🛡️"], ["key", "🔑"], ["lock", "🔒"], ["coin", "🪙"],
        ["money", "💰"], ["gold", "🏆"], ["diamond", "💎"], ["crystal", "🔮"], ["gem", "💍"],
        // Food
        ["bread", "🍞"], ["cake", "🍰"], ["cookie", "🍪"], ["pizza", "🍕"], ["burger", "🍔"],
        ["egg", "🥚"], ["milk", "🥛"], ["cheese", "🧀"], ["meat", "🍖"], ["sushi", "🍣"],
        ["soup", "🍲"], ["coffee", "☕"], ["tea", "🍵"], ["wine", "🍷"], ["beer", "🍺"],
        ["candy", "🍬"], ["donut", "🍩"], ["pie", "🥧"], ["honey", "🍯"], ["banana", "🍌"],
        ["apple", "🍎"], ["carrot", "🥕"], ["pumpkin", "🎃"], ["mushroom", "🍄"],
        // Buildings/places
        ["house", "🏠"], ["castle", "🏰"], ["church", "⛪"], ["bank", "🏦"], ["hospital", "🏥"],
        ["school", "🏫"], ["factory", "🏭"], ["barn", "🏚️"], ["bridge", "🌉"], ["pyramid", "🔺"],
        ["city", "🏙️"], ["village", "🏘️"], ["temple", "🛕"], ["statue", "🗿"],
        // People / roles
        ["doctor", "👨‍⚕️"], ["farmer", "👨‍🌾"], ["chef", "👨‍🍳"], ["pilot", "👨‍✈️"], ["teacher", "👩‍🏫"],
        ["sailor", "⚓"], ["soldier", "🪖"], ["fireman", "🚒"], ["police", "👮"], ["scientist", "🔬"],
        ["human", "🧑"], ["baby", "👶"], ["family", "👨‍👩‍👧"], ["bride", "👰"],
        // Misc
        ["book", "📚"], ["letter", "✉️"], ["map", "🗺️"], ["sign", "🪧"], ["flag", "🚩"],
        ["light", "💡"], ["candle", "🕯️"], ["lamp", "🪔"], ["fire extinguisher", "🧯"],
        ["umbrella", "☂️"], ["balloon", "🎈"], ["gift", "🎁"], ["music", "🎵"], ["paint", "🎨"],
        ["glasses", "👓"], ["hat", "🎩"], ["crown", "👑"], ["ring", "💍"], ["necklace", "📿"],
        ["clock", "⏰"], ["bell", "🔔"], ["clock", "🕒"], ["mirror", "🪞"], ["door", "🚪"],
        ["window", "🪟"], ["chair", "🪑"], ["bed", "🛏️"], ["bath", "🛁"], ["toilet", "🚽"],
    ];

    var _iconCache = {};
    function iconFor(name) {
        if (_iconCache[name] !== undefined) return _iconCache[name];
        var lower = (name || "").toLowerCase();
        for (var i = 0; i < ICON_MAP.length; i++) {
            if (lower.indexOf(ICON_MAP[i][0]) !== -1) {
                _iconCache[name] = ICON_MAP[i][1];
                return ICON_MAP[i][1];
            }
        }
        _iconCache[name] = "✨";
        return "✨";
    }

    function tryCombine(a_idx, b_idx) {
        var pair = [a_idx, b_idx].sort(function (a, b) { return a - b; });
        var key = pair[0] + "," + pair[1];
        var results = BY_RECIPE[key];
        return results && results.length > 0 ? results : null;
    }

    function recordAttempt(a_idx, b_idx, result_idx, rt) {
        trialCounter++;
        var elapsed = startTime ? (performance.now() - startTime) : 0;
        var pair = [a_idx, b_idx].sort(function (a, b) { return a - b; });
        var inv_before = inventory.length;
        var was_novel = false;
        if (result_idx !== null && !inventorySet.has(result_idx)) {
            was_novel = true;
        }
        var inv_after = inv_before + (was_novel ? 1 : 0);
        var aRecIn = RECIPES_USING_ELEMENT[pair[0]];
        var bRecIn = RECIPES_USING_ELEMENT[pair[1]];
        var rec = {
            trial_part: "attempt",
            trial_index: trialCounter,
            elapsed_time_ms: Math.round(elapsed),
            element_a: nameOf(pair[0]),
            element_b: nameOf(pair[1]),
            element_a_idx: pair[0],
            element_b_idx: pair[1],
            result: result_idx !== null ? nameOf(result_idx) : null,
            result_idx: result_idx,
            is_success: result_idx !== null,
            is_novel_discovery: was_novel,
            inventory_size_before: inv_before,
            inventory_size_after: inv_after,
            a_is_base: isBase(pair[0]),
            b_is_base: isBase(pair[1]),
            a_n_recipes_in: aRecIn,
            b_n_recipes_in: bRecIn,
            mean_input_recipes_in: (aRecIn + bRecIn) / 2,
            result_n_recipes_in: result_idx !== null ? RECIPES_USING_ELEMENT[result_idx] : 0,
            rt: Math.round(rt),
            timed_out: false,
        };
        attempts.push(rec);
        if (was_novel) {
            inventory.push(result_idx);
            inventorySet.add(result_idx);
        }
        return rec;
    }

    // ---- Inventory render ----
    var selectedSlots = [null, null]; // 2 selected element indices, or null
    var lastAttemptRender = null;     // {success, novel, message}

    function renderInventory() {
        var html = "";
        for (var i = 0; i < inventory.length; i++) {
            var idx = inventory[i];
            var name = nameOf(idx);
            var classes = ["element-chip"];
            if (isBase(idx)) classes.push("base");
            if (selectedSlots[0] === idx || selectedSlots[1] === idx) classes.push("selected");
            // Highlight newly discovered (last 3)
            if (i >= inventory.length - 3 && !isBase(idx)) classes.push("new");
            html += '<span class="' + classes.join(" ") + '" data-idx="' + idx + '">' +
                '<span class="icon">' + iconFor(name) + '</span>' +
                '<span class="label">' + name + '</span>' +
                '</span>';
        }
        return html;
    }

    function renderShell() {
        var sec_left = Math.max(0, Math.round(CONFIG.time_cap_minutes * 60 - (performance.now() - startTime) / 1000));
        var time_str = Math.floor(sec_left / 60) + ":" + String(sec_left % 60).padStart(2, "0");
        function fillSlot(idx) {
            if (idx === null) return '<div class="slot">pick element</div>';
            var name = nameOf(idx);
            return '<div class="slot filled"><span class="icon">' + iconFor(name) + '</span><span>' + name + '</span></div>';
        }
        var slot1 = fillSlot(selectedSlots[0]);
        var slot2 = fillSlot(selectedSlots[1]);
        var combine_disabled = (selectedSlots[0] === null || selectedSlots[1] === null) ? " disabled" : "";
        var fb = "";
        if (lastAttemptRender) {
            var cls = lastAttemptRender.novel ? "novel" : (lastAttemptRender.success ? "success" : "fail");
            fb = '<div class="feedback-line ' + cls + '">' + lastAttemptRender.message + "</div>";
        } else {
            fb = '<div class="feedback-line">&nbsp;</div>';
        }
        return '' +
            '<div class="session-bar">' +
                '<strong>' + inventory.length + '</strong> elements discovered &middot; ' +
                '<strong>' + attempts.length + '</strong> attempts &middot; ' +
                'time left: <strong>' + time_str + '</strong>' +
            '</div>' +
            '<div class="alchemy-shell">' +
                '<div class="panel">' +
                    '<div class="panel-header">Inventory <span class="small">(click two to combine)</span></div>' +
                    '<div class="inventory-list">' + renderInventory() + '</div>' +
                '</div>' +
                '<div class="panel workspace">' +
                    '<div class="panel-header">Workspace</div>' +
                    '<div class="workspace-slots">' + slot1 + '<div style="font-size:18px">+</div>' + slot2 + '</div>' +
                    '<div>' +
                        '<button class="combine-btn"' + combine_disabled + ' id="combine-btn">Combine</button>' +
                        '<button class="clear-btn" id="clear-btn">Clear</button>' +
                    '</div>' +
                    fb +
                    '<button class="end-btn" id="end-btn">End early</button>' +
                '</div>' +
            '</div>';
    }

    function attachShellHandlers(refreshFn, finishFn) {
        // Element chip clicks
        var chips = document.querySelectorAll(".element-chip");
        chips.forEach(function (chip) {
            chip.addEventListener("click", function () {
                var idx = parseInt(chip.getAttribute("data-idx"));
                if (selectedSlots[0] === null) {
                    selectedSlots[0] = idx;
                } else if (selectedSlots[1] === null && selectedSlots[0] !== idx) {
                    selectedSlots[1] = idx;
                } else {
                    // already 2 selected — replace slot 1, push slot 2
                    selectedSlots[0] = idx;
                    selectedSlots[1] = null;
                }
                refreshFn();
            });
        });
        // Combine
        var combineBtn = document.getElementById("combine-btn");
        if (combineBtn) {
            combineBtn.addEventListener("click", function () {
                if (selectedSlots[0] === null || selectedSlots[1] === null) return;
                var a = selectedSlots[0], b = selectedSlots[1];
                var t0 = performance.now();
                var results = tryCombine(a, b);
                var rt = performance.now() - t0;
                var resultIdx = results ? results[0] : null;
                var rec = recordAttempt(a, b, resultIdx, rt);
                if (rec.is_novel_discovery) {
                    lastAttemptRender = { success: true, novel: true,
                        message: "🎉 NEW! " + iconFor(rec.result) + " " + rec.result };
                } else if (rec.is_success) {
                    lastAttemptRender = { success: true, novel: false,
                        message: iconFor(rec.result) + " " + rec.result + " (already discovered)" };
                } else {
                    lastAttemptRender = { success: false, novel: false, message: "No combination ✗" };
                }
                selectedSlots = [null, null];
                if (attempts.length >= CONFIG.max_combinations) {
                    finishFn();
                    return;
                }
                refreshFn();
            });
        }
        // Clear
        var clearBtn = document.getElementById("clear-btn");
        if (clearBtn) {
            clearBtn.addEventListener("click", function () {
                selectedSlots = [null, null];
                refreshFn();
            });
        }
        // End early
        var endBtn = document.getElementById("end-btn");
        if (endBtn) {
            endBtn.addEventListener("click", function () { finishFn(); });
        }
    }

    // ---- Main task trial: a single jsPsych trial that runs the whole alchemy session ----
    var taskTrial = {
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            // Build initial inventory from base elements.
            inventory = GAME.base_elements.slice();
            inventorySet = new Set(inventory);
            attempts = [];
            selectedSlots = [null, null];
            lastAttemptRender = null;
            startTime = performance.now();
            trialCounter = 0;

            var content = document.querySelector("#jspsych-content");
            if (!content) { done(); return; }

            var deadlineMs = CONFIG.time_cap_minutes * 60 * 1000;
            var deadlineTimer = null;
            var tickTimer = null;
            var finished = false;

            function refresh() {
                content.innerHTML = renderShell();
                attachShellHandlers(refresh, finish);
            }
            function finish() {
                if (finished) return;
                finished = true;
                if (deadlineTimer) clearTimeout(deadlineTimer);
                if (tickTimer) clearInterval(tickTimer);
                done();
            }
            deadlineTimer = setTimeout(finish, deadlineMs);
            tickTimer = setInterval(function () { if (!finished) refresh(); }, 5000);
            refresh();
        },
    };

    var timeline = [];

    timeline.push({
        type: jsPsychHtmlKeyboardResponse,
        stimulus:
            "<h1>Tiny Alchemy</h1>" +
            "<p>Welcome. Press any key to begin.</p>",
    });

    timeline.push({
        type: jsPsychInstructions,
        pages: [
            "<h2>Instructions</h2>" +
            "<p>You start with four base elements: <strong>water, fire, earth, air</strong>.</p>" +
            "<p>You can combine any two elements in your inventory to discover new elements.</p>" +
            "<p>There are 540 elements in total. Try to discover as many as you can.</p>",

            "<h2>How to combine</h2>" +
            "<p>Click an element in your inventory to put it into the workspace.</p>" +
            "<p>Click a second element to put it into the second workspace slot.</p>" +
            "<p>Click <strong>Combine</strong> to attempt the combination.</p>" +
            "<p>If the combination has a recipe, the new element is added to your inventory.</p>" +
            "<p>If not, you'll see <em>No combination</em>. Try again.</p>",

            "<h2>Time</h2>" +
            "<p>You have <strong>" + CONFIG.time_cap_minutes + " minutes</strong> total.</p>" +
            "<p>You can also click <strong>End early</strong> at any time.</p>" +
            "<p>Press Next to start.</p>",
        ],
        show_clickable_nav: true,
        button_label_next: "Next",
        button_label_previous: "Previous",
    });

    // Wait for game data to load before starting.
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            GAME_LOAD_PROMISE.then(function () { done(); });
        },
    });

    timeline.push(taskTrial);

    // Data submission.
    timeline.push({
        type: jsPsychCallFunction,
        async: true,
        func: function (done) {
            var payload = {
                trial_data: attempts,
                metadata: {
                    task_id: TASK_ID,
                    session_id: SESSION_ID,
                    total_time_ms: jsPsych.getTotalTime(),
                    n_trials: attempts.length,
                    final_inventory_size: inventory.length,
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
            "<p>Thank you for playing Tiny Alchemy.</p>" +
            "<p>Your data has been submitted.</p>",
        choices: "NO_KEYS",
        trial_duration: 3000,
    });

    jsPsych.run(timeline);
})();
