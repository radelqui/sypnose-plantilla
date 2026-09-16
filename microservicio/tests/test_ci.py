# origen: adaptado de specs/T14 (rag-banking-agent@fce331beb35e93b080ed8998f5bf04f7bed0be30)
from pathlib import Path

SKELETON_ROOT = Path(__file__).resolve().parent.parent
CI_YML = SKELETON_ROOT / ".github" / "workflows" / "ci.yml"
DOCKERFILE = SKELETON_ROOT / "Dockerfile"
K8S_DEPLOY = SKELETON_ROOT / "k8s" / "deployment.yaml"

REQUIRED_TOOLS = ["gitleaks", "ruff", "bandit", "pytest", "trivy"]


def test_ci_tools_present():
    w = CI_YML.read_text()
    for tool in REQUIRED_TOOLS:
        assert tool in w, f"{tool} not found in ci.yml"


def test_dockerfile_hardened():
    d = DOCKERFILE.read_text()
    assert "USER appuser" in d
    assert "HEALTHCHECK" in d
    assert "AS builder" in d


def test_k8s_security():
    k = K8S_DEPLOY.read_text()
    assert "readOnlyRootFilesystem: true" in k
    assert "drop" in k and "ALL" in k


def test_origin_markers():
    for f in [CI_YML, DOCKERFILE, K8S_DEPLOY]:
        first_line = f.read_text().split("\n")[0]
        assert "origen: rag-banking-agent@" in first_line, f"Missing origin marker in {f.name}"
