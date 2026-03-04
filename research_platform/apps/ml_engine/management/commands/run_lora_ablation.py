"""
Management command: run_lora_ablation

Fine-tunes the BART summarizer with different LoRA ranks and records
ROUGE / BERTScore for each rank.  Produces the ablation table required
for the Section-Aware Hierarchical Summarization paper (Option 2).

Usage
-----
    python manage.py run_lora_ablation --data eval_data.json
    python manage.py run_lora_ablation --data eval_data.json --ranks 4,8,16,32
    python manage.py run_lora_ablation --data eval_data.json --output lora_ablation.json

eval_data.json format
---------------------
    [{"text": "<full paper text>", "reference": "<gold summary>"}, ...]

The command:
  1. Loads base facebook/bart-large-cnn
  2. Applies LoRA with each rank via peft
  3. Fine-tunes for --epochs on the provided data
  4. Evaluates ROUGE-1/2/L + BERTScore-F1 on the same data (proxy — use held-out set in practice)
  5. Prints a comparison table and saves JSON results
"""
import json
import sys

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Run LoRA rank ablation on the BART summarizer (ranks 4, 8, 16, 32)."

    def add_arguments(self, parser):
        parser.add_argument("--data",   required=True,
                            help="Path to eval JSON file with {text, reference} pairs.")
        parser.add_argument("--ranks",  default="4,8,16,32",
                            help="Comma-separated LoRA ranks to test (default: 4,8,16,32).")
        parser.add_argument("--epochs", type=int, default=3,
                            help="Training epochs per rank (default: 3).")
        parser.add_argument("--output", default=None,
                            help="Path to write JSON results.")

    def handle(self, *args, **options):
        try:
            import torch
            from peft import LoraConfig, TaskType, get_peft_model
            from transformers import BartForConditionalGeneration, BartTokenizer
        except ImportError as exc:
            raise CommandError(
                f"Missing dependencies: pip install peft transformers torch\n{exc}"
            )

        from apps.ml_engine.evaluation import evaluate_summarization

        # ── Load eval data ────────────────────────────────────────────────
        try:
            with open(options["data"]) as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"File not found: {options['data']}")
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON: {exc}")

        texts      = [d["text"]      for d in data if d.get("text") and d.get("reference")]
        references = [d["reference"] for d in data if d.get("text") and d.get("reference")]
        if not texts:
            raise CommandError("No valid {text, reference} pairs found.")
        self.stdout.write(f"Loaded {len(texts)} samples.")

        # ── Parse ranks ───────────────────────────────────────────────────
        try:
            ranks = [int(r.strip()) for r in options["ranks"].split(",")]
        except ValueError:
            raise CommandError("--ranks must be comma-separated integers, e.g. 4,8,16,32")

        MODEL_NAME = "facebook/bart-large-cnn"
        device     = "cuda" if torch.cuda.is_available() else "cpu"
        epochs     = options["epochs"]

        self.stdout.write(f"Device: {device} | Epochs: {epochs} | Ranks: {ranks}\n")

        results = {}

        for rank in ranks:
            self.stdout.write(f"\n{'='*50}")
            self.stdout.write(f"Testing LoRA rank={rank} …")
            try:
                tokenizer = BartTokenizer.from_pretrained(MODEL_NAME)
                base      = BartForConditionalGeneration.from_pretrained(MODEL_NAME)

                lora_cfg = LoraConfig(
                    task_type     = TaskType.SEQ_2_SEQ_LM,
                    r             = rank,
                    lora_alpha    = rank * 2,
                    lora_dropout  = 0.05,
                    target_modules= ["q_proj", "v_proj"],
                )
                model = get_peft_model(base, lora_cfg)
                model.to(device)
                n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
                self.stdout.write(f"  Trainable params: {n_params:,}")

                # ── Minimal fine-tuning loop ───────────────────────────
                import torch.nn as nn
                optimizer = torch.optim.AdamW(
                    [p for p in model.parameters() if p.requires_grad], lr=3e-5
                )
                model.train()
                for epoch in range(epochs):
                    epoch_loss = 0.0
                    for text, ref in zip(texts[:50], references[:50]):  # subsample for speed
                        inp = tokenizer(
                            text[:1024], return_tensors="pt",
                            truncation=True, max_length=1024,
                        ).to(device)
                        tgt = tokenizer(
                            ref, return_tensors="pt",
                            truncation=True, max_length=128,
                        ).input_ids.to(device)
                        out  = model(**inp, labels=tgt)
                        loss = out.loss
                        optimizer.zero_grad()
                        loss.backward()
                        optimizer.step()
                        epoch_loss += loss.item()
                    self.stdout.write(
                        f"  Epoch {epoch+1}/{epochs} — loss={epoch_loss/max(len(texts[:50]),1):.4f}"
                    )

                # ── Evaluation ─────────────────────────────────────────
                model.eval()
                preds = []
                with torch.no_grad():
                    for text in texts[:30]:
                        inp  = tokenizer(text[:1024], return_tensors="pt",
                                         truncation=True, max_length=1024).to(device)
                        ids  = model.generate(**inp, max_new_tokens=128, num_beams=4)
                        pred = tokenizer.decode(ids[0], skip_special_tokens=True)
                        preds.append(pred)

                metrics = evaluate_summarization(
                    predictions=preds,
                    references=references[:30],
                    skip_bertscore=False,
                )
                metrics["lora_rank"]      = rank
                metrics["trainable_params"] = n_params
                results[f"rank_{rank}"]   = metrics

                self.stdout.write(
                    f"  ROUGE-L={metrics.get('rougeL', 0):.4f}  "
                    f"BERTScore-F1={metrics.get('bertscore_f1', 0):.4f}  "
                    f"METEOR={metrics.get('meteor', 0):.4f}"
                )

            except Exception as exc:
                self.stderr.write(f"  rank={rank} FAILED: {exc}")
                results[f"rank_{rank}"] = {"error": str(exc)}

        # ── Summary table ─────────────────────────────────────────────────
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("LORA RANK ABLATION RESULTS")
        self.stdout.write(f"{'='*60}")
        self.stdout.write(
            f"{'Rank':<8} {'Params':>12} {'ROUGE-L':>10} {'BERTScore-F1':>14} {'METEOR':>10}"
        )
        self.stdout.write("-" * 60)
        for rank in ranks:
            r = results.get(f"rank_{rank}", {})
            if "error" in r:
                self.stdout.write(f"{rank:<8} ERROR: {r['error']}")
            else:
                self.stdout.write(
                    f"{rank:<8} {r.get('trainable_params',0):>12,} "
                    f"{r.get('rougeL',0):>10.4f} "
                    f"{r.get('bertscore_f1',0):>14.4f} "
                    f"{r.get('meteor',0):>10.4f}"
                )
        self.stdout.write("=" * 60)

        # ── Save JSON ─────────────────────────────────────────────────────
        if options.get("output"):
            with open(options["output"], "w") as f:
                json.dump(results, f, indent=2)
            self.stdout.write(self.style.SUCCESS(f"Results saved to {options['output']}"))

        if any("error" in v for v in results.values()):
            sys.exit(1)
