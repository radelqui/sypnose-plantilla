#!/usr/bin/env python3
"""Comprobación de trailers Git (Chat, Model, Plan) en los repositorios SYPNOSE.

    python plantilla/comprobar_trailers.py
    python plantilla/comprobar_trailers.py --repo nombre:ruta [--repo ...]

Ejecutar desde la raíz del worktree de plantilla.
Usa repos locales (git rev-list) con fallback a GitHub (gh api).

Tres bloques por repo:
  1. Pre-hook: deuda histórica
  2. Hook-a-cierre: deuda de transición (con causas)
  3. Post-cierre: regla de igualdad (0 violaciones exigido)

Exit 0 solo si todos los repos tienen cierre y 0 violaciones post-cierre.
Exit 1 si hay violaciones post-cierre o si el cierre no existe aún.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REQUIRED = {"Chat", "Model", "Plan"}
TEMPLATE_RE = re.compile(r"^<.*>$")

HOOK_SHA_PLANTILLA = "eae906fd62b9a9d783c7c51400004af5c4001704"

REPOS_DEFAULT = [
    {
        "name": "rag-banking-agent",
        "local": "../wt",
        "github": "radelqui/rag-banking-agent",
        "hook_sha": None,
        "closure_sha": None,
    },
    {
        "name": "sypnose-plantilla",
        "local": ".",
        "github": "radelqui/sypnose-plantilla",
        "hook_sha": HOOK_SHA_PLANTILLA,
        "closure_sha": None,
    },
    {
        "name": "como-estoy-hecho",
        "local": "../../como-estoy-hecho",
        "github": "radelqui/como-estoy-hecho",
        "hook_sha": None,
        "closure_sha": None,
    },
]


def fallo(msg: str) -> None:
    print(f"FALLO trailers: {msg}", file=sys.stderr)
    sys.exit(1)


def run_git(path: str, args: list[str]) -> tuple[str, int]:
    r = subprocess.run(
        ["git", "-C", path] + args,
        capture_output=True, text=True, encoding="utf-8",
    )
    if r.returncode != 0:
        return r.stderr.strip(), r.returncode
    return r.stdout.strip(), 0


def is_local_repo(path: str) -> bool:
    _, rc = run_git(path, ["rev-parse", "--git-dir"])
    return rc == 0


@dataclass
class CommitInfo:
    sha: str
    parents: list[str]
    chat: str
    model: str
    plan: str
    subject: str

    @property
    def is_merge(self) -> bool:
        return len(self.parents) > 1

    @property
    def is_auto_merge(self) -> bool:
        return self.is_merge and (
            self.subject.startswith("Merge branch")
            or self.subject.startswith("Merge remote-tracking branch")
        )

    def missing_trailers(self) -> set[str]:
        missing: set[str] = set()
        for key, val in [("Chat", self.chat), ("Model", self.model), ("Plan", self.plan)]:
            v = val.strip()
            if not v or TEMPLATE_RE.match(v):
                missing.add(key)
        return missing


def fetch_commits_local(path: str) -> list[CommitInfo]:
    sep = "\x1f"
    fmt = (
        f"%H{sep}%P{sep}"
        f"%(trailers:key=Chat,valueonly,separator=%x2C){sep}"
        f"%(trailers:key=Model,valueonly,separator=%x2C){sep}"
        f"%(trailers:key=Plan,valueonly,separator=%x2C){sep}"
        f"%s"
    )
    out, rc = run_git(path, ["log", "--all", f"--format={fmt}"])
    if rc != 0:
        fallo(f"git log en {path}: {out}")
    commits: list[CommitInfo] = []
    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = line.split(sep, 5)
        if len(parts) < 6:
            parts += [""] * (6 - len(parts))
        sha, parents_str, chat, model, plan, subject = parts
        parents = parents_str.split() if parents_str.strip() else []
        commits.append(CommitInfo(
            sha=sha.strip(), parents=parents,
            chat=chat.strip(), model=model.strip(),
            plan=plan.strip(), subject=subject.strip(),
        ))
    return commits


def get_sha_set(path: str, args: list[str]) -> set[str]:
    out, rc = run_git(path, ["rev-list"] + args)
    if rc != 0:
        return set()
    return set(out.split()) if out else set()


def parse_trailers_from_message(message: str) -> dict[str, str]:
    paragraphs = message.rstrip().split("\n\n")
    if not paragraphs:
        return {}
    last_para = paragraphs[-1]
    trailers: dict[str, str] = {}
    for line in last_para.split("\n"):
        m = re.match(r"^([A-Za-z][\w-]*)\s*:\s*(.+)$", line.strip())
        if m:
            trailers[m.group(1)] = m.group(2).strip()
    return trailers


def fetch_commits_github(slug: str) -> list[CommitInfo]:
    r = subprocess.run(
        ["gh", "api", f"repos/{slug}/branches", "--paginate",
         "--jq", ".[].name"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if r.returncode != 0:
        fallo(f"gh api branches {slug}: {r.stderr.strip()}")
    branches = [b for b in r.stdout.strip().split("\n") if b]

    seen: set[str] = set()
    commits: list[CommitInfo] = []
    for branch in branches:
        page = 1
        while True:
            url = f"repos/{slug}/commits?sha={branch}&per_page=100&page={page}"
            r2 = subprocess.run(
                ["gh", "api", url],
                capture_output=True, text=True, encoding="utf-8",
            )
            if r2.returncode != 0:
                break
            data = json.loads(r2.stdout)
            if not data:
                break
            for c in data:
                if c["sha"] in seen:
                    continue
                seen.add(c["sha"])
                msg = c.get("commit", {}).get("message", "")
                parents = [p["sha"] for p in c.get("parents", [])]
                trailers = parse_trailers_from_message(msg)
                commits.append(CommitInfo(
                    sha=c["sha"], parents=parents,
                    chat=trailers.get("Chat", ""),
                    model=trailers.get("Model", ""),
                    plan=trailers.get("Plan", ""),
                    subject=msg.split("\n")[0],
                ))
            if len(data) < 100:
                break
            page += 1
    return commits


@dataclass
class BucketResult:
    total: int = 0
    checked: int = 0
    violations: list[str] = None
    exempt_merges: int = 0

    def __post_init__(self):
        if self.violations is None:
            self.violations = []


def check_repo(repo: dict) -> tuple[BucketResult, BucketResult, BucketResult]:
    name = repo["name"]
    local_path = repo.get("local")
    github = repo.get("github")
    hook_sha = repo.get("hook_sha")
    closure_sha = repo.get("closure_sha")

    use_local = local_path and is_local_repo(local_path)

    if use_local:
        print(f"  fuente: local ({local_path})")
        commits = fetch_commits_local(local_path)
    elif github:
        print(f"  fuente: GitHub ({github})")
        commits = fetch_commits_github(github)
    else:
        fallo(f"{name}: sin fuente local ni GitHub")

    all_shas = {c.sha for c in commits}

    if hook_sha and use_local:
        pre_hook_shas = get_sha_set(local_path, [hook_sha])
        post_hook_shas = all_shas - pre_hook_shas
    elif hook_sha:
        pre_hook_shas = set()
        found_hook = False
        for c in commits:
            if c.sha == hook_sha:
                found_hook = True
            if found_hook:
                pre_hook_shas.add(c.sha)
        post_hook_shas = all_shas - pre_hook_shas
    else:
        pre_hook_shas = set()
        post_hook_shas = all_shas

    if closure_sha and use_local:
        pre_closure_shas = get_sha_set(local_path, [closure_sha])
        post_closure_shas = all_shas - pre_closure_shas
    else:
        post_closure_shas = set()

    pre_hook = BucketResult()
    hook_to_closure = BucketResult()
    post_closure = BucketResult()

    for c in commits:
        if c.sha not in post_hook_shas:
            bucket = pre_hook
        elif closure_sha and c.sha in post_closure_shas:
            bucket = post_closure
        else:
            bucket = hook_to_closure

        bucket.total += 1

        if c.is_auto_merge:
            bucket.exempt_merges += 1
            continue

        bucket.checked += 1
        missing = c.missing_trailers()
        if missing:
            bucket.violations.append(
                f"  {c.sha[:8]}: faltan {', '.join(sorted(missing))}  [{c.subject[:60]}]"
            )

    return pre_hook, hook_to_closure, post_closure


def print_bucket(label: str, b: BucketResult) -> None:
    print(f"  {label}: {b.total} commits, {b.checked} verificados, "
          f"{len(b.violations)} violaciones, {b.exempt_merges} merges exentos")
    if b.violations:
        for v in b.violations:
            print(v)


def main() -> None:
    parser = argparse.ArgumentParser(description="Comprobación de trailers Git")
    parser.add_argument(
        "--repo", action="append", metavar="nombre:ruta",
        help="Repo local (nombre:ruta). Repetible. Sustituye los repos por defecto.",
    )
    args = parser.parse_args()

    if args.repo:
        repos = []
        for r in args.repo:
            if ":" not in r:
                fallo(f"formato --repo: nombre:ruta (recibido: {r})")
            name, path = r.split(":", 1)
            repos.append({"name": name, "local": path, "github": None,
                          "hook_sha": None, "closure_sha": None})
    else:
        repos = REPOS_DEFAULT

    total_violations_hook_closure: list[str] = []
    total_violations_post_closure: list[str] = []
    total_checked = 0
    total_debt_pre = 0
    total_debt_transition = 0
    has_closure = False

    for i, repo in enumerate(repos, 1):
        name = repo["name"]
        print(f"[{i}/{len(repos)}] {name} ...")

        pre_hook, hook_to_closure, post_closure = check_repo(repo)

        print_bucket("pre-hook (deuda histórica)", pre_hook)
        print_bucket("hook-a-cierre (transición)", hook_to_closure)

        if repo.get("closure_sha"):
            has_closure = True
            print_bucket("post-cierre (igualdad)", post_closure)
            total_violations_post_closure.extend(
                [f"{name}: {v.strip()}" for v in post_closure.violations]
            )
        else:
            print("  post-cierre: PENDIENTE (cierre no implementado)")

        total_checked += hook_to_closure.checked + post_closure.checked
        total_debt_pre += len(pre_hook.violations)
        total_debt_transition += len(hook_to_closure.violations)
        total_violations_hook_closure.extend(
            [f"{name}: {v.strip()}" for v in hook_to_closure.violations]
        )
        print()

    any_closure_missing = any(not r.get("closure_sha") for r in repos)

    sys.stdout.flush()

    if total_violations_post_closure:
        print(
            f"FALLO trailers: {len(total_violations_post_closure)} violaciones "
            f"post-cierre", file=sys.stderr,
        )
        sys.exit(1)

    if any_closure_missing:
        print(
            f"FALLO trailers: cierre no implementado en "
            f"{sum(1 for r in repos if not r.get('closure_sha'))} repo(s). "
            f"Regla 100 % no verificable aún. "
            f"Transición: {len(total_violations_hook_closure)} violaciones "
            f"post-hook documentadas, "
            f"deuda pre-hook: {total_debt_pre}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"OK trailers: {total_checked} commits verificados, "
        f"0 violaciones post-cierre"
    )


if __name__ == "__main__":
    main()
