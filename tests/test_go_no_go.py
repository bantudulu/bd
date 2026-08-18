from app.release_readiness import ReleaseEvidence, evaluate_release


def evidence(**overrides):
    values = {
        "ci_green": True,
        "migration_rehearsal": True,
        "customer_admin_journey": True,
        "backup_restore_rehearsal": True,
        "fresh_production_secrets": True,
        "no_legacy_demo_accounts": True,
        "production_health_ready": True,
        "domain_tls_reverse_proxy": True,
        "operator_runbook_reviewed": True,
    }
    values.update(overrides)
    return ReleaseEvidence(**values)


def test_go_requires_every_gate():
    result = evaluate_release(evidence())
    assert result["decision"] == "GO"
    assert result["blockers"] == []


def test_missing_external_evidence_is_no_go():
    result = evaluate_release(
        evidence(
            backup_restore_rehearsal=False,
            production_health_ready=False,
            domain_tls_reverse_proxy=False,
        )
    )
    assert result["decision"] == "NO-GO"
    assert {item["id"] for item in result["blockers"]} == {
        "backup_restore_rehearsal",
        "production_health_ready",
        "domain_tls_reverse_proxy",
    }
