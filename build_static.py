"""Pre-render Jinja2 templates to static HTML for Vercel deployment."""
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

PROJECT_ROOT = Path(__file__).parent
TASKS_DIR = PROJECT_ROOT / "tasks"
PUBLIC_DIR = PROJECT_ROOT / "public"

DOMAIN_LABELS = {
    "perception_attention": "Perception & Attention",
    "multi_armed_bandits": "Bandits & Exploration",
    "decision_making": "Decision-Making",
    "social_strategic": "Social & Strategic",
    "memory_learning": "Memory & Learning",
    "reinforcement_learning": "Reinforcement Learning",
}


def load_tasks_meta():
    tasks = []
    for task_dir in sorted(TASKS_DIR.iterdir()):
        config_path = task_dir / "task_config.json"
        if not (task_dir.is_dir() and config_path.exists()):
            continue
        with open(config_path) as f:
            config = json.load(f)
        params = config.get("parameters", {})
        sig_path = task_dir / "scoring" / "level3_signatures.json"
        n_sigs = 0
        if sig_path.exists():
            with open(sig_path) as f:
                n_sigs = len(json.load(f).get("signatures", []))
        response_type = config.get("response_type", "keyboard")
        response_labels = {
            "keyboard": "Keyboard", "button": "Button Click",
            "slider": "Slider", "text": "Text Input",
        }
        tasks.append({
            "task_id": config["task_id"],
            "task_name": config.get("task_name", config["task_id"]),
            "domain": config.get("domain", "unknown"),
            "domain_label": DOMAIN_LABELS.get(config.get("domain", ""), config.get("domain", "")),
            "description": config.get("description", ""),
            "citation": config.get("citation", ""),
            "n_trials": params.get("n_trials", 0),
            "n_signatures": n_sigs,
            "parameters": params,
            "response_label": response_labels.get(response_type, response_type),
        })
    return tasks


class FakeRequest:
    """Minimal request object for Jinja2 templates that use {{ request.base_url }}."""
    class base_url:
        def __str__(self):
            return "/"
    def __init__(self):
        self.base_url = "/"


def build():
    env = Environment(loader=FileSystemLoader(str(PROJECT_ROOT / "templates")))
    tasks = load_tasks_meta()
    domains = set(t["domain"] for t in tasks)
    request = FakeRequest()

    pages = {
        "index.html": {"request": request, "task_count": len(tasks), "domain_count": len(domains)},
        "catalog.html": {"request": request, "tasks": tasks, "domains": domains},
        "leaderboard.html": {"request": request},
        "try.html": {"request": request, "tasks": tasks},
        "submit.html": {"request": request, "base_url": ""},
    }

    for filename, context in pages.items():
        template = env.get_template(filename)
        html = template.render(**context)
        out_name = filename if filename != "index.html" else "index.html"
        out_path = PUBLIC_DIR / out_name
        out_path.write_text(html)
        print(f"  Built {out_path}")

    # Task detail pages
    catalog_dir = PUBLIC_DIR / "catalog"
    catalog_dir.mkdir(exist_ok=True)
    template = env.get_template("task_detail.html")
    for task in tasks:
        html = template.render(request=request, task=task)
        out_path = catalog_dir / task["task_id"] / "index.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html)
    print(f"  Built {len(tasks)} task detail pages in catalog/")

    # Copy skill.md
    skill_src = PROJECT_ROOT / "static" / "skill.md"
    skill_dst = PUBLIC_DIR / "skill.md"
    skill_dst.write_text(skill_src.read_text())
    print(f"  Copied skill.md")


if __name__ == "__main__":
    print("Building static site...")
    build()
    print("Done!")
