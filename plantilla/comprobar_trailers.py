#!/usr/bin/env python3
"""Comprobación de trailers Git (Chat, Model, Plan) en los 3 repositorios.

    python plantilla/comprobar_trailers.py

Ejecutar desde la raíz del worktree de plantilla. Usa gh api. Resultado:
  exit 0 + "OK trailers: ..."
  exit 1 + motivo si falla.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

REPOS = [
    {
        "name": "rag-banking-agent",
        "github": "radelqui/rag-banking-agent",
        "cutoff": None,
    },
    {
        "name": "sypnose-plantilla",
        "github": "radelqui/sypnose-plantilla",
        "cutoff": "d310a12f9e133869a0494ff17ac7623f558443b2",
    },
    {
        "name": "como-estoy-hecho",
        "github": "radelqui/como-estoy-hecho",
        "cutoff": None,
    },
]

REQUIRED_TRAILERS = {"Chat", "Model", "Plan"}


def fallo(msg: str) -> None:
    print(f"FALLO trailers: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_trailers(message: str) -> dict[str, str]:
    paragraphs = message.rstrip().split("\n\n")
    if not paragraphs:
        return {}
    last_para = paragraphs[-1]
    trailers: dict[str, str] = {}
    for line in last_para.split("\n"):
        line = line.strip()
        m = re.match(r"^([A-Za-z][\w-]*)\s*:\s*(.+)$", line)
        if m:
            trailers[m.group(1)] = m.group(2).strip()
    return trailers


def is_merge(commit: dict) -> bool:
    return len(commit.get("parents", [])) > 1


def fetch_commits(repo_slug: str) -> list[dict]:
    all_commits: list[dict] = []
    page = 1
    while True:
        url = (
            f"repos/{repo_slug}/commits"
            f"?sha=main&per_page=100&page={page}"
        )
        r = subprocess.run(
            ["gh", "api", url],
            capture_output=True, text=True, encoding="utf-8",
        )
        if r.returncode != 0:
            fallo(f"gh api {repo_slug}/commits falló: {r.stderr.strip()}")
        commits = json.loads(r.stdout)
        if not commits:
            break
        all_commits.extend(commits)
        if len(commits) < 100:
            break
        page += 1
    return all_commits


def check_repo(repo: dict) -> tuple[int, int, list[str]]:
    name = repo["name"]
    github = repo["github"]
    cutoff = repo["cutoff"]

    commits = fetch_commits(github)
    if not commits:
        fallo(f"{name}: no se encontraron commits en main")

    post_cutoff: list[dict] = []
    pre_cutoff: list[dict] = []

    if cutoff is None:
        post_cutoff = commits
    else:
        for i, c in enumerate(commits):
            if c["sha"] == cutoff:
                pre_cutoff = commits[i:]
                break
            post_cutoff.append(c)
        else:
            post_cutoff = commits

    violations: list[str] = []
    checked = 0
    for c in post_cutoff:
        if is_merge(c):
            continue
        checked += 1
        msg = c.get("commit", {}).get("message", "")
        trailers = parse_trailers(msg)
        missing = REQUIRED_TRAILERS - set(trailers.keys())
        if missing:
            sha_short = c["sha"][:8]
            violations.append(
                f"  {sha_short}: faltan {', '.join(sorted(missing))}"
            )

    debt_count = 0
    for c in pre_cutoff:
        if is_merge(c):
            continue
        msg = c.get("commit", {}).get("message", "")
        trailers = parse_trailers(msg)
        if REQUIRED_TRAILERS - set(trailers.keys()):
            debt_count += 1

    return checked, debt_count, violations


def main() -> None:
    total_violations: list[str] = []
    total_checked = 0
    total_debt = 0
    ok_repos = 0

    for i, repo in enumerate(REPOS, 1):
        name = repo["name"]
        print(f"[{i}/{len(REPOS)}] {name} ...")

        checked, debt, violations = check_repo(repo)
        total_checked += checked
        total_debt += debt

        if violations:
            print(f"  VIOLACIONES ({len(violations)}):")
            for v in violations:
                print(v)
            total_violations.extend(
                [f"{name}: {v.strip()}" for v in violations]
            )
        else:
            print(f"  post-corte: {checked} commits, 0 violaciones")
            ok_repos += 1

        if debt > 0:
            print(f"  deuda histórica: {debt} commits sin trailers completos")
        else:
            print(f"  deuda histórica: 0")

    print()
    if total_violations:
        print(
            f"FALLO trailers: {len(total_violations)} violaciones "
            f"post-corte en {len(REPOS) - ok_repos} repo(s)",
            file=sys.stderr,
        )
        for v in total_violations:
            print(f"  {v}", file=sys.stderr)
        sys.exit(1)

    print(
        f"OK trailers: {total_checked} commits post-corte verificados, "
        f"0 violaciones, deuda histórica {total_debt}"
    )


if __name__ == "__main__":
    main()
