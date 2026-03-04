"""
Management command: run_ablation

Run the ablation study for the HA-RAG + SR-MAR + Self-RAG pipeline and
print the results table.  Optionally saves the full JSON results to disk.

Usage
-----
    python manage.py run_ablation --queries queries.json
    python manage.py run_ablation --queries queries.json --output ablation_results.json
    python manage.py run_ablation --queries queries.json --configs full,no_srmar,no_reranker

queries.json format
-------------------
    [
        {
            "query": "What methods are used for document summarization?",
            "relevant_paper_ids": ["42", "17", "33"],
            "reference_answer": "Document summarization methods include..."   // optional
        },
        ...
    ]

--configs values (comma-separated, default = all):
    full        Full Pipeline (ours)
    no_srmar    w/o SR-MAR
    no_reranker w/o Reranker
    no_decomp   w/o Decomposer
    no_selfrag  w/o Self-RAG
    no_hybrid   w/o Hybrid
    dense       Dense-Only
"""
import json
import sys

from django.core.management.base import BaseCommand, CommandError


_CONFIG_MAP = {
    "full":        "Full Pipeline (ours)",
    "no_srmar":    "w/o SR-MAR",
    "no_reranker": "w/o Reranker",
    "no_decomp":   "w/o Decomposer",
    "no_selfrag":  "w/o Self-RAG",
    "no_hybrid":   "w/o Hybrid",
    "dense":       "Dense-Only",
}


class Command(BaseCommand):
    help = "Run ablation study for the HA-RAG + SR-MAR + Self-RAG pipeline."

    def add_arguments(self, parser):
        parser.add_argument(
            "--queries",
            required=True,
            help="Path to a JSON file containing test queries.",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Path to write JSON results (optional).",
        )
        parser.add_argument(
            "--configs",
            default="all",
            help=(
                "Comma-separated list of configs to run. "
                "Choices: all, full, no_srmar, no_reranker, no_decomp, no_selfrag, no_hybrid, dense. "
                "Default: all"
            ),
        )

    def handle(self, *args, **options):
        from apps.ml_engine.evaluation import AblationRunner, STANDARD_ABLATIONS

        # --- Load queries ---
        queries_path = options["queries"]
        try:
            with open(queries_path) as f:
                queries = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"Queries file not found: {queries_path}")
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {queries_path}: {exc}")

        if not isinstance(queries, list) or not queries:
            raise CommandError("queries.json must be a non-empty list.")

        self.stdout.write(
            self.style.SUCCESS(f"Loaded {len(queries)} queries from {queries_path}")
        )

        # --- Select configs ---
        config_arg = options["configs"].strip()
        if config_arg == "all":
            selected_configs = STANDARD_ABLATIONS
        else:
            requested_keys = [k.strip() for k in config_arg.split(",")]
            requested_names = set()
            for key in requested_keys:
                if key not in _CONFIG_MAP:
                    raise CommandError(
                        f"Unknown config '{key}'. Valid keys: {', '.join(_CONFIG_MAP)}"
                    )
                requested_names.add(_CONFIG_MAP[key])
            selected_configs = [c for c in STANDARD_ABLATIONS if c.name in requested_names]

        self.stdout.write(f"Running {len(selected_configs)} ablation configuration(s)…\n")

        # --- Run ablation ---
        runner = AblationRunner(queries)
        results = runner.run_all(configs=selected_configs)

        # --- Print table ---
        runner.print_table(results)

        # --- Save JSON ---
        output_path = options.get("output")
        if output_path:
            runner.save_results(results, output_path)
            self.stdout.write(self.style.SUCCESS(f"\nResults saved to {output_path}"))

        # Exit with error code if any config failed
        if any("error" in v for v in results.values()):
            sys.exit(1)
