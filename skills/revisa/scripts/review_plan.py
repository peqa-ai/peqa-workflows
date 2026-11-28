#!/usr/bin/env python3
"""Deterministic reviewer model/depth recommendation and PR inline review payload helper.

Python 3.10+ standard library only. Read-only, no network, no subprocesses.

Model strings are matched by family name (astra, opus, neon, sol) as whole words;
the exact version and provider ID come from the host catalog, never from here.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


MAX_INPUT_BYTES = 2 * 1024 * 1024
# commit_id is the full head SHA (headRefOid); an abbreviation is refused here, not left to the API.
SHA_RE = re.compile(r'^(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})$')
HUNK_RE = re.compile(r'^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
# GitHub caps a review body and each review comment at 65536 characters.
MAX_GITHUB_BODY_CHARS = 65536
SEVERITIES = ('critical', 'high', 'medium', 'low')
FINDING_STATUSES = ('open', 'resolved', 'dismissed')
FINDING_TEXT_FIELDS = ('conditions', 'impact', 'minimal_fix', 'visible_flow', 'adjudication')
LOCAL_PATH_RE = re.compile(r'(?<![\w.:/~-])(?:/(?:Users|home|private|tmp|var/folders)/|~/)[^\s`)\]>"\']*')

MODELS = {
    'astra-6.2': {
        'id': 'astra-6.2',
        'name': 'Astra 6.2',
        'role': 'backend_complex',
        'summary_es': 'Backend, lógica compleja, esquemas, integridad de datos y seguridad.',
        'summary_en': 'Backend, complex business logic, schemas, data integrity, and security.',
    },
    'opus-5.5': {
        'id': 'opus-5.5',
        'name': 'Opus 5.5',
        'role': 'general_frontend',
        'summary_es': 'Uso general, frontend/full-stack y alternativa sólida para backend.',
        'summary_en': 'General-purpose, frontend/full-stack, and strong backend alternative.',
    },
    'neon-4': {
        'id': 'neon-4',
        'name': 'Neon 4',
        'role': 'general_frontend',
        'summary_es': 'Uso general, frontend/full-stack y alternativa sólida para backend.',
        'summary_en': 'General-purpose, frontend/full-stack, and strong backend alternative.',
    },
    'sol-6.2': {
        'id': 'sol-6.2',
        'name': 'Sol 6.2',
        'role': 'simple_lightweight',
        'summary_es': 'Tareas simples, cambios pequeños y revisiones ligeras.',
        'summary_en': 'Simpler, smaller tasks and lightweight reviews.',
    },
}

MODEL_FAMILIES = (('astra', 'astra-6.2'), ('opus', 'opus-5.5'), ('neon', 'neon-4'), ('sol', 'sol-6.2'))
# Placeholders a host uses when it does not expose the running model.
UNDETECTED_MODELS = frozenset({'unknown', 'desconocido', 'none', 'null', 'auto', 'default', 'inherit'})

DOMAINS = ('backend', 'frontend', 'fullstack', 'simple', 'general')
COMPLEXITIES = ('simple', 'standard', 'complex')
DEPTHS = ('lite', 'deep')
HIGH_RISK_FLAGS = frozenset({
    'auth',
    'authorization',
    'money',
    'ledger',
    'migration',
    'migrations',
    'security',
    'multi_repo',
    'concurrency',
    'schema',
    'data_integrity',
    'high_risk',
})
BACKEND_RISK_FLAGS = frozenset({
    'auth',
    'authorization',
    'money',
    'ledger',
    'migration',
    'migrations',
    'security',
    'concurrency',
    'schema',
    'data_integrity',
})


class PlanError(Exception):
    """Fixed error code safe to emit across the CLI boundary."""


def normalize_model_id(raw: str | None) -> str | None:
    """Map a host-exposed or user-typed model string to a canonical reviewer catalog ID.

    Returns one of the four catalog IDs, or None if the input is empty/unknown,
    names a model outside the four-model catalog, or names more than one family.
    The family must appear as a whole word: `gpt-6.2-sol` is Sol, `console` is not.
    """
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip().lower()
    if not text or text in UNDETECTED_MODELS:
        return None
    words = set(re.findall(r'[a-z]+', text))
    matches = [model_id for family, model_id in MODEL_FAMILIES if family in words]
    return matches[0] if len(matches) == 1 else None


def _available_ids(available_models) -> set[str] | None:
    """None means the caller did not check routes; a set lists the models it can run."""
    if available_models is None:
        return None
    ids = set()
    for item in available_models:
        model_id = normalize_model_id(item)
        if model_id is None:
            raise PlanError('INVALID_AVAILABLE_MODEL')
        ids.add(model_id)
    return ids


def _clean_flags(risk_flags) -> list[str]:
    if not risk_flags:
        return []
    cleaned = []
    for item in risk_flags:
        if not isinstance(item, str):
            raise PlanError('INVALID_RISK_FLAG')
        flag = item.strip().lower().replace('-', '_')
        if not flag:
            continue
        if flag not in HIGH_RISK_FLAGS:
            raise PlanError('INVALID_RISK_FLAG')
        if flag not in cleaned:
            cleaned.append(flag)
    return cleaned


def recommend_review(
    domain: str = 'general',
    complexity: str = 'standard',
    risk_flags=(),
    session_model: str | None = None,
    requested_model: str | None = None,
    requested_depth: str | None = None,
    available_models=None,
) -> dict:
    """Recommend reviewer model and depth (`lite` | `deep`) with session diversity.

    `available_models` lists the catalog models this host can actually run. When
    given, models without a route are ordered last and never recommended while
    another one is available.
    """
    domain = (domain or 'general').strip().lower()
    complexity = (complexity or 'standard').strip().lower()
    if domain not in DOMAINS:
        raise PlanError('INVALID_DOMAIN')
    if complexity not in COMPLEXITIES:
        raise PlanError('INVALID_COMPLEXITY')
    flags = _clean_flags(risk_flags)

    session_raw = session_model.strip() if isinstance(session_model, str) and session_model.strip() else None
    session_detected = bool(session_raw and session_raw.lower() not in UNDETECTED_MODELS)
    session_id = normalize_model_id(session_raw) if session_detected else None

    explicit_model_id = None
    if requested_model is not None and str(requested_model).strip():
        explicit_model_id = normalize_model_id(str(requested_model))
        if explicit_model_id is None:
            raise PlanError('INVALID_REQUESTED_MODEL')

    explicit_depth = None
    if requested_depth is not None and str(requested_depth).strip():
        candidate = str(requested_depth).strip().lower()
        if candidate not in DEPTHS:
            raise PlanError('INVALID_DEPTH')
        explicit_depth = candidate

    backend_weighted = (
        domain == 'backend'
        or complexity == 'complex'
        or bool(BACKEND_RISK_FLAGS.intersection(flags))
    )
    simple_weighted = (
        not backend_weighted
        and not flags
        and (domain == 'simple' or complexity == 'simple')
    )

    if backend_weighted:
        priority = ['astra-6.2', 'opus-5.5', 'neon-4', 'sol-6.2']
        model_reason = 'backend_or_complex_domain'
    elif simple_weighted:
        priority = ['sol-6.2', 'neon-4', 'opus-5.5', 'astra-6.2']
        model_reason = 'simple_lightweight_change'
    else:
        priority = ['opus-5.5', 'neon-4', 'astra-6.2', 'sol-6.2']
        model_reason = 'frontend_fullstack_or_general'

    diversified = False
    if session_id is not None and priority[0] == session_id:
        diversified = True
    ordered_ids = [mid for mid in priority if mid != session_id]
    if session_id is not None:
        ordered_ids.append(session_id)
    available = _available_ids(available_models)
    if available:
        ordered_ids = ([mid for mid in ordered_ids if mid in available]
                       + [mid for mid in ordered_ids if mid not in available])

    def is_available(model_id):
        return None if available is None else model_id in available

    recommended_model_id = ordered_ids[0]
    selected_model_id = explicit_model_id or recommended_model_id

    deep_needed = (
        domain == 'backend'
        or complexity == 'complex'
        or bool(flags)
        or (domain == 'fullstack' and complexity != 'simple')
    )
    recommended_depth = 'deep' if deep_needed else 'lite'
    selected_depth = explicit_depth or recommended_depth

    model_options = []
    for index, mid in enumerate(ordered_ids):
        info = MODELS[mid]
        model_options.append({
            'id': info['id'],
            'name': info['name'],
            'role': info['role'],
            'recommended': index == 0,
            'matches_session_model': mid == session_id,
            'available': is_available(mid),
            'summary_es': info['summary_es'],
            'summary_en': info['summary_en'],
        })

    depth_order = ('deep', 'lite') if recommended_depth == 'deep' else ('lite', 'deep')
    depth_options = [
        {
            'depth': item,
            'recommended': item == recommended_depth,
            'summary_es': (
                'Revisión adversarial completa + seguridad OWASP Top 10 / NIST SSDF, autenticación, concurrencia, datos y blast radius.'
                if item == 'deep'
                else 'Requisitos funcionales, defectos materiales, regresiones, bordes y pruebas (sin auditoría completa OWASP/NIST salvo defecto obvio).'
            ),
            'summary_en': (
                'Full adversarial review plus OWASP Top 10 / NIST SSDF security, auth, concurrency, data integrity, and full blast radius.'
                if item == 'deep'
                else 'Functional requirements, material defects, regressions, edge cases, and test coverage (skips full OWASP/NIST audit unless obvious defect).'
            ),
        }
        for item in depth_order
    ]

    questions_needed = []
    if explicit_model_id is None:
        questions_needed.append('model')
    if explicit_depth is None:
        questions_needed.append('depth')

    disclosure = (
        None
        if session_detected
        else 'El host no expuso el modelo de la sesión actual; recomendación basada solo en dominio y complejidad.'
    )

    return {
        'domain': domain,
        'complexity': complexity,
        'risk_flags': flags,
        'session_model_raw': session_raw if session_detected else None,
        'session_model_id': session_id,
        'session_model_detected': session_detected,
        'session_model_disclosure': disclosure,
        'diversified_from_session': diversified,
        'model_reason': model_reason,
        'recommended_model': MODELS[recommended_model_id]['name'],
        'recommended_model_id': recommended_model_id,
        'selected_model': MODELS[selected_model_id]['name'],
        'selected_model_id': selected_model_id,
        'selected_model_matches_session': session_id is not None and selected_model_id == session_id,
        'availability_checked': available is not None,
        'recommended_model_available': is_available(recommended_model_id),
        'selected_model_available': is_available(selected_model_id),
        'model_options': model_options,
        'recommended_depth': recommended_depth,
        'selected_depth': selected_depth,
        'depth_options': depth_options,
        'needs_user_question': bool(questions_needed),
        'questions_needed': questions_needed,
    }


def parse_pr_url(value: str) -> dict:
    """Validate and parse a GitHub-style HTTPS PR web URL."""
    if not isinstance(value, str) or not value.strip():
        raise PlanError('PR_URL_REQUIRED')
    try:
        parsed = urlsplit(value.strip())
        hostname, username, password = parsed.hostname, parsed.username, parsed.password
    except ValueError as exc:
        raise PlanError('HTTPS_PR_URL_REQUIRED') from exc
    if parsed.scheme != 'https' or not hostname or username is not None or password is not None:
        raise PlanError('HTTPS_PR_URL_REQUIRED')
    host = hostname.lower().rstrip('.')
    if not re.fullmatch(r'[a-z0-9.-]+', host):
        raise PlanError('INVALID_PR_HOST')
    try:
        port = parsed.port
    except ValueError as exc:
        raise PlanError('INVALID_PR_PORT') from exc
    if port is not None and not 1 <= port <= 65535:
        raise PlanError('INVALID_PR_PORT')
    host_port = host if port in (None, 443) else f'{host}:{port}'
    match = re.fullmatch(r'/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([1-9][0-9]*)/?', parsed.path)
    if not match or any(part in ('.', '..') for part in match.groups()[:2]):
        raise PlanError('PR_WEB_URL_REQUIRED')
    owner, repo, number = match.groups()
    canonical = f'https://{host_port}/{owner.lower()}/{repo.lower()}/pull/{number}'
    return {
        'canonical_url': canonical,
        'host': host_port,
        'owner': owner,
        'repo': repo,
        'number': int(number),
        'reviews_endpoint': f'repos/{owner}/{repo}/pulls/{number}/reviews',
    }


def decide_publish_target(
    pr_url: str | None = None,
    direct_pr_mode: bool = False,
    is_public_repo: bool = False,
    has_exploitable_security: bool = False,
) -> dict:
    """Determine where review output goes and enforce GitHub safety rules."""
    has_pr = bool(pr_url and str(pr_url).strip())
    if direct_pr_mode and not has_pr:
        raise PlanError('PR_URL_REQUIRED')
    parsed = parse_pr_url(pr_url) if has_pr else None

    redact = bool(is_public_repo and has_exploitable_security)
    if not has_pr:
        return {
            'destination': 'local',
            'publish_to_pr': False,
            'keep_local_record': True,
            'inline_comments': False,
            'github_event': None,
            'redact_security_exploits': redact,
            'recommend_private_advisory': redact,
            'pr': None,
        }

    return {
        'destination': 'pr_review_inline_and_local' if direct_pr_mode else 'pr_and_local',
        'publish_to_pr': True,
        'keep_local_record': True,
        'inline_comments': bool(direct_pr_mode),
        'github_event': 'COMMENT',
        'redact_security_exploits': redact,
        'recommend_private_advisory': redact,
        'pr': parsed,
    }


def _safe_relative_path(path: str) -> bool:
    if not isinstance(path, str) or not path or len(path) > 4096:
        return False
    if path.startswith('/') or '\\' in path or any(ord(c) < 32 or ord(c) == 127 for c in path):
        return False
    return not any(part in ('', '.', '..', '.git') for part in path.split('/'))


_C_ESCAPES = {'a': 7, 'b': 8, 't': 9, 'n': 10, 'v': 11, 'f': 12, 'r': 13, '"': 34, '\\': 92}


def _unquote_git_path(target: str) -> str | None:
    """Decode the C-style quoting Git applies to non-ASCII or special paths."""
    if not (len(target) >= 2 and target.startswith('"') and target.endswith('"')):
        return target
    inner = target[1:-1]
    out = bytearray()
    index = 0
    while index < len(inner):
        char = inner[index]
        if char != '\\':
            out.extend(char.encode('utf-8'))
            index += 1
        elif inner[index + 1:index + 2] in _C_ESCAPES:
            out.append(_C_ESCAPES[inner[index + 1]])
            index += 2
        elif re.fullmatch(r'[0-3][0-7]{2}', inner[index + 1:index + 4]):
            out.append(int(inner[index + 1:index + 4], 8))
            index += 4
        else:
            return None
    try:
        return out.decode('utf-8')
    except UnicodeDecodeError:
        return None


def extract_diff_right_lines(diff_text: str) -> dict[str, set[int]]:
    """Return {path: {line_numbers}} valid for RIGHT-side inline PR review comments.

    Hunk bodies are consumed by the line counts of their `@@` header, so content
    that looks like a header (an added line starting with `++ `) stays content.
    """
    if not isinstance(diff_text, str):
        raise PlanError('DIFF_INVALID')
    if len(diff_text.encode('utf-8')) > MAX_INPUT_BYTES:
        raise PlanError('INPUT_TOO_LARGE')
    lines_by_path: dict[str, set[int]] = {}
    current_path: str | None = None
    right_line = 0
    old_left = new_left = 0

    # Only \n ends a diff line; str.splitlines would also cut on form feeds or U+2028 inside code.
    lines = diff_text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    for raw in lines:
        if old_left > 0 or new_left > 0:
            marker = raw[:1]
            if marker == '\\':
                continue
            if marker == '+' and new_left > 0:
                if current_path:
                    lines_by_path[current_path].add(right_line)
                right_line += 1
                new_left -= 1
                continue
            if marker == '-' and old_left > 0:
                old_left -= 1
                continue
            # A tool that trims trailing whitespace leaves a blank context line empty.
            if marker in (' ', '', '\r') and old_left > 0 and new_left > 0:
                if current_path:
                    lines_by_path[current_path].add(right_line)
                right_line += 1
                old_left -= 1
                new_left -= 1
                continue
            old_left = new_left = 0  # Malformed hunk: stop trusting it and re-read this line as a header.
        if raw.startswith('diff --git '):
            current_path = None
        elif raw.startswith('+++ '):
            target = _unquote_git_path(raw[4:].split('\t', 1)[0].rstrip('\r'))
            if target is not None and target.startswith('b/'):
                target = target[2:]
            current_path = target if target is not None and _safe_relative_path(target) else None
            if current_path:
                lines_by_path.setdefault(current_path, set())
        elif raw.startswith('@@ '):
            match = HUNK_RE.match(raw)
            if match:
                old_left = 1 if match.group(1) is None else int(match.group(1))
                right_line = int(match.group(2))
                new_left = 1 if match.group(3) is None else int(match.group(3))
    return lines_by_path


def _local_root_prefixes(local_root: str | None) -> list[str]:
    """Absolute spellings of the checkout root; a relative root such as `.` is resolved first."""
    if not local_root or not isinstance(local_root, str):
        return []
    prefixes = set()
    for candidate in (os.path.abspath(local_root), os.path.realpath(local_root)):
        candidate = candidate.rstrip('/')
        if len(candidate) > 1:
            prefixes.add(candidate)
    return sorted(prefixes, key=len, reverse=True)


def _sanitize_local_root(text: str, local_root: str | None) -> str:
    cleaned = text
    for prefix in _local_root_prefixes(local_root):
        # The lookahead keeps /work/app from matching inside /work/app-old.
        cleaned = re.sub(re.escape(prefix) + r'(?:(/)|(?![A-Za-z0-9_-]))',
                         lambda match: '' if match.group(1) else '<repo>', cleaned)
    return cleaned


def _one_line(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def _check_finding(item) -> None:
    """Reject a finding the formatters cannot render, with a fixed code instead of a traceback."""
    if not isinstance(item, dict):
        raise PlanError('FINDINGS_INVALID')
    for key in ('id', 'evidence'):
        if not isinstance(item.get(key), str) or not item[key].strip():
            raise PlanError('FINDINGS_INVALID')
    for key in FINDING_TEXT_FIELDS:
        if item.get(key) is not None and not isinstance(item[key], str):
            raise PlanError('FINDINGS_INVALID')
    if item.get('severity') is not None and item['severity'] not in SEVERITIES:
        raise PlanError('FINDINGS_INVALID')
    if item.get('status') is not None and item['status'] not in FINDING_STATUSES:
        raise PlanError('FINDINGS_INVALID')
    for key in ('material', 'security_exploitable'):
        if item.get(key) is not None and type(item[key]) is not bool:
            raise PlanError('FINDINGS_INVALID')
    path = item.get('path')
    line = item.get('line')
    if path is not None and not _safe_relative_path(path):
        raise PlanError('INVALID_FINDING_PATH')
    if line is not None and (type(line) is not int or line < 1):
        raise PlanError('INVALID_FINDING_LINE')


def _format_inline_body(finding: dict, language: str = 'es') -> str:
    es = language == 'es'
    fid = finding['id']
    severity = finding.get('severity')
    header = f'**[{fid}]' + (f' ({severity})' if severity else '') + '**'
    parts = [header, finding['evidence'].strip()]
    if finding.get('conditions'):
        parts.append(('**Condiciones:** ' if es else '**Conditions:** ') + finding['conditions'].strip())
    if finding.get('impact'):
        parts.append(('**Impacto:** ' if es else '**Impact:** ') + finding['impact'].strip())
    if finding.get('minimal_fix'):
        parts.append(('**Corrección mínima:** ' if es else '**Minimal fix:** ') + finding['minimal_fix'].strip())
    if finding.get('visible_flow'):
        parts.append(('**Flujo / pantalla visible:** ' if es else '**Visible flow / screen:** ') + finding['visible_flow'].strip())
    return '\n\n'.join(parts)


def _format_orca_note_text(finding: dict) -> str:
    fid = finding['id']
    severity = finding.get('severity')
    prefix = f'[{fid}' + (f'/{severity}' if severity else '') + '] '
    text = prefix + finding['evidence'].strip()
    if finding.get('minimal_fix'):
        text += ' Fix: ' + finding['minimal_fix'].strip()
    return _one_line(text)


def build_pr_review_payload(
    pr_url: str,
    head_sha: str,
    summary_markdown: str,
    findings: list[dict],
    diff_text: str,
    language: str = 'es',
    is_public_repo: bool = False,
    local_root: str | None = None,
) -> dict:
    """Build a single-call GitHub COMMENT review payload + Orca --note list without double-posting.

    `findings` is a list, or a consolidated report object carrying a `findings` list.
    """
    pr = parse_pr_url(pr_url)
    if not isinstance(head_sha, str) or not SHA_RE.fullmatch(head_sha.strip()):
        raise PlanError('HEAD_SHA_REQUIRED')
    head_sha = head_sha.strip().lower()
    if isinstance(findings, dict):
        findings = findings.get('findings')
    if not isinstance(summary_markdown, str) or not summary_markdown.strip():
        raise PlanError('SUMMARY_REQUIRED')
    if language not in ('es', 'en'):
        raise PlanError('LANGUAGE_INVALID')
    if not isinstance(findings, list) or len(findings) > 500:
        raise PlanError('FINDINGS_INVALID')

    diff_lines = extract_diff_right_lines(diff_text)
    inline_comments = []
    orca_notes = []
    out_of_diff = []
    seen_keys = set()
    exploitable_ids = []

    for item in findings:
        _check_finding(item)
        fid = item['id']
        if item.get('material') is False:
            continue
        if item.get('status') in ('resolved', 'dismissed'):
            continue
        if item.get('security_exploitable') is True and fid.strip() not in exploitable_ids:
            exploitable_ids.append(fid.strip())

        path = item.get('path')
        line = item.get('line')

        if path and line is not None and line in diff_lines.get(path, ()):
            dedupe_key = (fid.strip(), path, line)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            body = _sanitize_local_root(_format_inline_body(item, language), local_root)
            inline_comments.append({
                'path': path,
                'line': line,
                'side': 'RIGHT',
                'body': body,
            })
            note_text = _sanitize_local_root(_format_orca_note_text(item), local_root)
            orca_notes.append(f'{path}:{line}:{note_text}')
        else:
            dedupe_key = (fid.strip(), path or '', line or 0)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            out_of_diff.append(item)

    general_body = _sanitize_local_root(summary_markdown.rstrip(), local_root)
    if out_of_diff:
        es = language == 'es'
        section_title = (
            '## Hallazgos fuera del diff (sin comentario en línea)'
            if es
            else '## Out-of-diff findings (no inline comment possible)'
        )
        intro = (
            'GitHub no permite adjuntar comentarios en línea fuera de los hunks del diff; se incluyen aquí para trazabilidad:'
            if es
            else 'GitHub cannot attach inline comments to lines outside the diff hunks; listed here for traceability:'
        )
        bullets = []
        for item in out_of_diff:
            location = item.get('path') or ('sin ruta' if es else 'no path')
            if item.get('path') and item.get('line'):
                location = f"{item['path']}:{item['line']}"
            sev = f" ({item['severity']})" if item.get('severity') else ''
            text = f"- **{item['id']}**{sev} `{location}`: {_one_line(item['evidence'])}"
            if item.get('minimal_fix'):
                label = 'Corrección mínima' if es else 'Minimal fix'
                text += f" — {label}: {_one_line(item['minimal_fix'])}"
            bullets.append(_sanitize_local_root(text, local_root))
        general_body = f'{general_body}\n\n{section_title}\n\n{intro}\n\n' + '\n'.join(bullets)

    if len(general_body) > MAX_GITHUB_BODY_CHARS:
        raise PlanError('SUMMARY_TOO_LARGE')
    if any(len(comment['body']) > MAX_GITHUB_BODY_CHARS for comment in inline_comments):
        raise PlanError('COMMENT_TOO_LARGE')
    local_path_hits = []
    for text in [general_body] + [comment['body'] for comment in inline_comments]:
        for hit in LOCAL_PATH_RE.findall(text):
            if hit not in local_path_hits and len(local_path_hits) < 20:
                local_path_hits.append(hit)

    has_exploitable_security = bool(exploitable_ids)
    payload = {
        'commit_id': head_sha,
        'event': 'COMMENT',
        'body': general_body,
        'comments': inline_comments,
    }
    publish_policy = decide_publish_target(
        pr_url=pr['canonical_url'],
        direct_pr_mode=True,
        is_public_repo=is_public_repo,
        has_exploitable_security=has_exploitable_security,
    )
    return {
        'pr': pr,
        'endpoint': pr['reviews_endpoint'],
        'payload': payload,
        'orca_notes': orca_notes,
        'inline_count': len(inline_comments),
        'out_of_diff_count': len(out_of_diff),
        # Paths that still look local after --local-root; the caller rewrites them before publishing.
        'local_path_hits': local_path_hits,
        # Findings flagged exploitable that a public repository must receive without exploit detail.
        'redaction_required_ids': exploitable_ids if publish_policy['redact_security_exploits'] else [],
        'policy': publish_policy,
    }


def _read_bounded_text(path_str: str) -> str:
    path = Path(path_str)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PlanError('INPUT_UNREADABLE') from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise PlanError('INPUT_TOO_LARGE')
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise PlanError('INPUT_INVALID') from exc


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise PlanError('ARGUMENTS_INVALID')


def main(argv=None) -> int:
    try:
        parser = _Parser(description=__doc__)
        sub = parser.add_subparsers(dest='action', required=True)

        rec = sub.add_parser('recommend', help='Recommend reviewer model and depth with session diversity')
        rec.add_argument('--domain', choices=DOMAINS, default='general')
        rec.add_argument('--complexity', choices=COMPLEXITIES, default='standard')
        rec.add_argument('--risk', action='append', default=[], help='Risk flag (repeatable)')
        rec.add_argument('--session-model', default=None)
        rec.add_argument('--requested-model', default=None)
        rec.add_argument('--requested-depth', choices=DEPTHS, default=None)
        rec.add_argument('--available', action='append', default=None,
                         help='Catalog model this host can run (repeatable); omit when routes were not checked')

        pub = sub.add_parser('publish-plan', help='Decide local vs PR publishing target and safety policy')
        pub.add_argument('--pr-url', default=None)
        pub.add_argument('--direct-pr', action='store_true')
        pub.add_argument('--public-repo', action='store_true')
        pub.add_argument('--exploitable-security', action='store_true')

        prp = sub.add_parser('pr-review-payload', help='Build GitHub COMMENT review JSON payload and Orca notes')
        prp.add_argument('--pr-url', required=True)
        prp.add_argument('--head', required=True)
        prp.add_argument('--summary-file', required=True)
        prp.add_argument('--findings-file', required=True)
        prp.add_argument('--diff-file', required=True)
        prp.add_argument('--language', choices=('es', 'en'), default='es')
        prp.add_argument('--public-repo', action='store_true')
        prp.add_argument('--local-root', default=None)

        args = parser.parse_args(argv)
        if args.action == 'recommend':
            out = recommend_review(
                domain=args.domain,
                complexity=args.complexity,
                risk_flags=args.risk,
                session_model=args.session_model,
                requested_model=args.requested_model,
                requested_depth=args.requested_depth,
                available_models=args.available,
            )
        elif args.action == 'publish-plan':
            out = decide_publish_target(
                pr_url=args.pr_url,
                direct_pr_mode=args.direct_pr,
                is_public_repo=args.public_repo,
                has_exploitable_security=args.exploitable_security,
            )
        else:
            summary = _read_bounded_text(args.summary_file)
            diff_text = _read_bounded_text(args.diff_file)
            try:
                findings = json.loads(_read_bounded_text(args.findings_file))
            except (ValueError, RecursionError) as exc:
                raise PlanError('FINDINGS_INVALID') from exc
            out = build_pr_review_payload(
                pr_url=args.pr_url,
                head_sha=args.head,
                summary_markdown=summary,
                findings=findings,
                diff_text=diff_text,
                language=args.language,
                is_public_repo=args.public_repo,
                local_root=args.local_root,
            )
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except PlanError as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        # Unexpected input shape: name the failure without echoing its content.
        print(json.dumps({'error': type(exc).__name__}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
