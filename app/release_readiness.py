from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseEvidence:
    ci_green: bool
    migration_rehearsal: bool
    customer_admin_journey: bool
    backup_restore_rehearsal: bool
    fresh_production_secrets: bool
    no_legacy_demo_accounts: bool
    production_health_ready: bool
    domain_tls_reverse_proxy: bool
    operator_runbook_reviewed: bool


GATE_LABELS = {
    "ci_green": "CI release hijau",
    "migration_rehearsal": "Migration rehearsal sukses",
    "customer_admin_journey": "Customer-to-admin journey sukses",
    "backup_restore_rehearsal": "Backup dan restore rehearsal sukses",
    "fresh_production_secrets": "Secret production fresh dan tidak pernah disimpan di Git",
    "no_legacy_demo_accounts": "Database production bebas akun demo/default legacy",
    "production_health_ready": "Production /health/live dan /health/ready hijau",
    "domain_tls_reverse_proxy": "Domain, TLS, dan reverse proxy final aktif",
    "operator_runbook_reviewed": "Operator sudah memahami backup, rollback, dan incident runbook",
}


def evaluate_release(evidence: ReleaseEvidence) -> dict:
    values = evidence.__dict__
    checks = [
        {"id": key, "label": label, "passed": bool(values[key])}
        for key, label in GATE_LABELS.items()
    ]
    blockers = [item for item in checks if not item["passed"]]
    return {
        "decision": "GO" if not blockers else "NO-GO",
        "checks": checks,
        "blockers": blockers,
    }
