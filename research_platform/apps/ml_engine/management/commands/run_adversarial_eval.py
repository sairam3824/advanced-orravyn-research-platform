"""
Django management command to run adversarial robustness evaluation.

Usage:
    python manage.py run_adversarial_eval --queries queries.json --output results.json
"""
import json
import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run adversarial robustness evaluation on the RAG pipeline"

    def add_arguments(self, parser):
        parser.add_argument(
            "--queries",
            type=str,
            required=True,
            help="Path to JSON file with base queries"
        )
        parser.add_argument(
            "--output",
            type=str,
            default="adversarial_results.json",
            help="Path to save results"
        )
        parser.add_argument(
            "--variants",
            type=int,
            default=3,
            help="Number of adversarial variants per query"
        )

    def handle(self, *args, **options):
        from apps.ml_engine.adversarial_testing import (
            get_adversarial_generator,
            RobustnessEvaluator
        )
        from apps.ml_engine.rag_pipeline import query_rag

        queries_path = options["queries"]
        output_path = options["output"]
        num_variants = options["variants"]

        self.stdout.write(f"Loading queries from {queries_path}...")

        # Load base queries
        try:
            with open(queries_path, "r") as f:
                base_queries = json.load(f)
        except Exception as exc:
            self.stdout.write(
                self.style.ERROR(f"Failed to load queries: {exc}")
            )
            return

        if isinstance(base_queries, dict):
            base_queries = base_queries.get("queries", [])

        self.stdout.write(f"Loaded {len(base_queries)} base queries.")

        # Generate adversarial variants
        generator = get_adversarial_generator()
        self.stdout.write("Generating adversarial variants...")

        adversarial_queries = generator.generate_batch(
            base_queries,
            variants_per_query=num_variants
        )

        self.stdout.write(
            f"Generated {len(adversarial_queries)} adversarial queries."
        )

        # Evaluate each adversarial query
        evaluator = RobustnessEvaluator()
        self.stdout.write("Running evaluation...")

        for i, adv_query in enumerate(adversarial_queries, 1):
            self.stdout.write(
                f"[{i}/{len(adversarial_queries)}] Evaluating: {adv_query['type']}"
            )

            try:
                # Run RAG pipeline
                result = query_rag(adv_query["query"])
                response = result.get("response", "")
                confidence = result.get("faithfulness_score", 0.5)

                # Evaluate
                eval_result = evaluator.evaluate_query(
                    adversarial_query=adv_query,
                    system_response=response,
                    system_confidence=confidence
                )

                status = "PASS" if eval_result["passed"] else "FAIL"
                self.stdout.write(f"  Result: {status}")

            except Exception as exc:
                self.stdout.write(
                    self.style.WARNING(f"  Error: {exc}")
                )

        # Get summary
        summary = evaluator.get_summary()

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("ADVERSARIAL ROBUSTNESS EVALUATION RESULTS")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Total queries: {summary['total_queries']}")
        self.stdout.write(
            f"Pass rate: {summary['pass_rate']:.2%}"
        )
        self.stdout.write(
            f"Uncertainty admission rate: {summary['uncertainty_admission_rate']:.2%}"
        )
        self.stdout.write(
            f"Avg hallucination score: {summary['avg_hallucination_score']:.3f}"
        )

        self.stdout.write("\nBy Query Type:")
        for query_type, stats in summary["by_query_type"].items():
            self.stdout.write(
                f"  {query_type}: {stats['count']} queries, "
                f"{stats['pass_rate']:.2%} pass rate"
            )

        # Save results
        output_data = {
            "summary": summary,
            "detailed_results": evaluator.results
        }

        try:
            with open(output_path, "w") as f:
                json.dump(output_data, f, indent=2)
            self.stdout.write(
                self.style.SUCCESS(f"\nResults saved to {output_path}")
            )
        except Exception as exc:
            self.stdout.write(
                self.style.ERROR(f"Failed to save results: {exc}")
            )
