"""
Management command: evaluate_summarization

Evaluate the Section-Aware Hierarchical Summarizer on a set of papers
with reference summaries.

Usage
-----
    python manage.py evaluate_summarization --data eval_data.json
    python manage.py evaluate_summarization --data eval_data.json --skip-bertscore
    python manage.py evaluate_summarization --paper-ids 42,17,33 --skip-bertscore

eval_data.json format
---------------------
    [
        {
            "paper_id": 42,             // optional; if provided, text is fetched from DB
            "text": "Full paper...",    // required when paper_id is absent
            "reference": "Gold summary..."
        },
        ...
    ]

When --paper-ids is used the command fetches Paper objects from the database,
runs the summarizer on their stored text, and compares to ``Paper.summary``.
"""
import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Evaluate the section-aware summarizer on papers with reference summaries."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--data",
            help="Path to eval JSON file with {text, reference} pairs.",
        )
        group.add_argument(
            "--paper-ids",
            help="Comma-separated Paper IDs from the database.",
        )
        parser.add_argument(
            "--skip-bertscore",
            action="store_true",
            default=False,
            help="Skip BERTScore computation (saves time/memory).",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Path to write JSON results (optional).",
        )

    def handle(self, *args, **options):
        from apps.ml_engine.evaluation import evaluate_summarization
        from apps.ml_engine.section_summarizer import SectionAwareSummarizer

        summarizer = SectionAwareSummarizer()
        predictions = []
        references = []
        section_summaries_list = []

        # ---- Load from JSON file ----
        if options.get("data"):
            data_path = options["data"]
            try:
                with open(data_path) as f:
                    data = json.load(f)
            except FileNotFoundError:
                raise CommandError(f"File not found: {data_path}")
            except json.JSONDecodeError as exc:
                raise CommandError(f"Invalid JSON in {data_path}: {exc}")

            self.stdout.write(f"Loaded {len(data)} samples from {data_path}")

            for item in data:
                text = item.get("text", "")
                reference = item.get("reference", "")
                if not text or not reference:
                    self.stderr.write(
                        "Skipping item: missing 'text' or 'reference'."
                    )
                    continue

                result = summarizer.summarize_paper(text)
                predictions.append(result["final_summary"])
                references.append(reference)
                if result.get("section_summaries"):
                    section_summaries_list.append(result["section_summaries"])

        # ---- Load from database paper IDs ----
        elif options.get("paper_ids"):
            import django
            django.setup()  # ensure apps ready in standalone invocation
            from apps.papers.models import Paper

            raw_ids = [pid.strip() for pid in options["paper_ids"].split(",")]
            try:
                int_ids = [int(pid) for pid in raw_ids]
            except ValueError:
                raise CommandError("--paper-ids must be comma-separated integers.")

            papers = Paper.objects.filter(pk__in=int_ids)
            self.stdout.write(f"Found {papers.count()} papers in DB.")

            for paper in papers:
                if not paper.summary:
                    self.stderr.write(
                        f"Paper {paper.pk} has no stored summary; skipping."
                    )
                    continue

                text = getattr(paper, "full_text", None) or ""
                if not text:
                    self.stderr.write(
                        f"Paper {paper.pk} has no stored full_text; skipping."
                    )
                    continue

                result = summarizer.summarize_paper(text)
                predictions.append(result["final_summary"])
                references.append(paper.summary)
                if result.get("section_summaries"):
                    section_summaries_list.append(result["section_summaries"])

        if not predictions:
            raise CommandError("No valid samples to evaluate.")

        self.stdout.write(f"\nEvaluating {len(predictions)} summaries…\n")

        metrics = evaluate_summarization(
            predictions=predictions,
            references=references,
            section_summaries_list=section_summaries_list or None,
            skip_bertscore=options["skip_bertscore"],
        )

        # --- Print results ---
        self.stdout.write("\n" + "=" * 55)
        self.stdout.write("SUMMARIZATION EVALUATION RESULTS")
        self.stdout.write("=" * 55)
        for metric, value in sorted(metrics.items()):
            self.stdout.write(f"  {metric:<30} {value:.4f}")
        self.stdout.write("=" * 55 + "\n")

        # --- Save JSON ---
        output_path = options.get("output")
        if output_path:
            with open(output_path, "w") as f:
                json.dump(metrics, f, indent=2)
            self.stdout.write(self.style.SUCCESS(f"Results saved to {output_path}"))
