from codex_memory.skills import write_skill_candidate


def test_write_skill_candidate_creates_draft_without_touching_skills_dir(tmp_path):
    output_dir = tmp_path / "skill-candidates"
    real_skills_dir = tmp_path / "real-skills"
    real_skills_dir.mkdir()

    path = write_skill_candidate(
        output_dir=output_dir,
        title="Trainer Failure Triage",
        slug="trainer-failure-triage",
        applies_when="A training run fails repeatedly.",
        triggers=["failed run_full", "stack timeout"],
        steps=["Collect human.log", "Classify known issue", "Write TODO candidate"],
        counterexamples=["One-off user preference"],
        evidence="Seen in repeated trainer debugging sessions.",
        suggested_install_path=real_skills_dir / "trainer-failure-triage" / "SKILL.md",
    )

    assert path == output_dir / "trainer-failure-triage.md"
    assert path.exists()
    assert not any(real_skills_dir.iterdir())
    content = path.read_text(encoding="utf-8")
    assert "# Trainer Failure Triage" in content
    assert "## 建议安装位置" in content
