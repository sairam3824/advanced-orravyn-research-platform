"""
Management command to auto-populate Citation records for all existing papers.

Usage:
    python manage.py backfill_citations
    python manage.py backfill_citations --paper-id 42          # single paper
    python manage.py backfill_citations --only-missing         # skip papers that already have citations
    python manage.py backfill_citations --dry-run              # preview without writing
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Backfill Citation records by extracting references from uploaded PDFs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--paper-id",
            type=int,
            default=None,
            help="Process a single paper by PK.",
        )
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Skip papers that already have at least one outgoing citation.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and match but do not write Citation records.",
        )

    def handle(self, *args, **options):
        from apps.papers.models import Paper
        from apps.ml_engine.citation_extractor import CitationExtractor
        from apps.ml_engine.pdf_text_extractor import extract_pdf_text_from_path

        paper_id = options["paper_id"]
        only_missing = options["only_missing"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no records will be written."))

        # Build queryset
        qs = Paper.objects.filter(pdf_path__isnull=False).exclude(pdf_path="")
        if paper_id:
            qs = qs.filter(pk=paper_id)
        if only_missing:
            qs = qs.filter(citations__isnull=True)

        total = qs.count()
        if total == 0:
            self.stdout.write("No papers to process.")
            return

        self.stdout.write(f"Processing {total} paper(s)...")

        extractor = CitationExtractor()
        total_created = 0
        total_matched = 0
        skipped = 0

        for idx, paper in enumerate(qs.iterator(), start=1):
            self.stdout.write(f"  [{idx}/{total}] {paper.title[:70]}")

            try:
                pdf_text = extract_pdf_text_from_path(paper.pdf_path.path)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"    ✗ Could not read PDF: {e}"))
                skipped += 1
                continue

            if not pdf_text or len(pdf_text.split()) < 50:
                self.stdout.write(self.style.WARNING("    ✗ PDF text too short (scanned/image PDF?)."))
                skipped += 1
                continue

            ref_text = extractor._extract_references_text(pdf_text)
            if not ref_text:
                self.stdout.write("    — No references section found.")
                skipped += 1
                continue

            entries = extractor._parse_entries(ref_text)
            matched = extractor._match_to_papers(entries, paper.id)
            total_matched += len(matched)

            if dry_run:
                self.stdout.write(
                    f"    ~ {len(entries)} refs parsed, {len(matched)} would match: "
                    + (", ".join(p.title[:40] for p in matched) if matched else "none in platform")
                )
                continue

            # Run the full pipeline (saves references_list + Citation records)
            created = extractor.extract_and_link(paper.id, pdf_text)
            total_created += created
            self.stdout.write(
                self.style.SUCCESS(
                    f"    ✓ {len(entries)} refs parsed → {len(matched)} internal matches → {created} new Citation records"
                )
            )

        self.stdout.write("")
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN complete. Would have matched {total_matched} citations across {total - skipped} papers."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. {total_created} Citation records created across {total - skipped} papers "
                    f"({skipped} skipped)."
                )
            )
