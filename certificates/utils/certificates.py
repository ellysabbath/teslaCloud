"""
Atomic certificate number generator: TCI-YYYY-NNNN
SQLite-safe using select_for_update inside an atomic transaction.
"""
from django.db import transaction
from certificates.models import CertificateSequence


def next_certificate_number() -> str:
    from django.utils import timezone
    year = timezone.now().strftime("%Y")

    with transaction.atomic():
        seq, _ = CertificateSequence.objects.select_for_update().get_or_create(
            year=year, defaults={"last_sequence": 0}
        )
        seq.last_sequence += 1
        seq.save(update_fields=["last_sequence"])
        number = seq.last_sequence

    return f"TCI-{year}-{number:04d}"