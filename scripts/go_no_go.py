import json
import os

from app.release_readiness import ReleaseEvidence, evaluate_release


def env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on", "pass", "passed"}


def main() -> None:
    evidence = ReleaseEvidence(
        ci_green=env_bool("EVIDENCE_CI_GREEN"),
        migration_rehearsal=env_bool("EVIDENCE_MIGRATION_REHEARSAL"),
        customer_admin_journey=env_bool("EVIDENCE_CUSTOMER_ADMIN_JOURNEY"),
        backup_restore_rehearsal=env_bool("EVIDENCE_BACKUP_RESTORE_REHEARSAL"),
        fresh_production_secrets=env_bool("EVIDENCE_FRESH_PRODUCTION_SECRETS"),
        no_legacy_demo_accounts=env_bool("EVIDENCE_NO_LEGACY_DEMO_ACCOUNTS"),
        production_health_ready=env_bool("EVIDENCE_PRODUCTION_HEALTH_READY"),
        domain_tls_reverse_proxy=env_bool("EVIDENCE_DOMAIN_TLS_REVERSE_PROXY"),
        operator_runbook_reviewed=env_bool("EVIDENCE_OPERATOR_RUNBOOK_REVIEWED"),
    )
    result = evaluate_release(evidence)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["decision"] != "GO":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
