"""Tests for reviewer model/depth recommendation and PR inline review payload helper."""

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'skills/revisa/scripts/review_plan.py'
PR_URL = 'https://github.com/peqa-ai/sample-app/pull/123'
HEAD_SHA = 'a' * 40


def load_module():
    spec = importlib.util.spec_from_file_location('review_plan', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


class ModelAndDepthRecommendationTests(unittest.TestCase):
    def setUp(self):
        self.plan = load_module()

    def test_backend_always_recommends_astra_unless_session_is_astra(self):
        for session in ('Opus 5.5', 'claude-opus-5-5', 'Neon 4', 'gemini-4-neon', 'Sol 6.2', None):
            with self.subTest(session=session):
                rec = self.plan.recommend_review(domain='backend', session_model=session)
                self.assertEqual(rec['recommended_model'], 'Astra 6.2')
                self.assertEqual(rec['recommended_model_id'], 'astra-6.2')
                self.assertEqual(rec['recommended_depth'], 'deep')
                self.assertEqual(rec['model_options'][0]['name'], 'Astra 6.2')
                self.assertTrue(rec['model_options'][0]['recommended'])
                self.assertEqual(len(rec['model_options']), 4)

    def test_backend_diversifies_away_when_session_is_astra(self):
        rec = self.plan.recommend_review(domain='backend', session_model='Astra 6.2')
        self.assertTrue(rec['session_model_detected'])
        self.assertTrue(rec['diversified_from_session'])
        self.assertEqual(rec['recommended_model'], 'Opus 5.5')
        self.assertEqual(rec['recommended_depth'], 'deep')
        ordered = [item['name'] for item in rec['model_options']]
        self.assertEqual(ordered, ['Opus 5.5', 'Neon 4', 'Sol 6.2', 'Astra 6.2'])
        self.assertTrue(rec['model_options'][-1]['matches_session_model'])

    def test_complex_and_high_risk_changes_recommend_astra_and_deep(self):
        for risk in ('auth', 'money', 'ledger', 'migration', 'security', 'schema', 'concurrency'):
            with self.subTest(risk=risk):
                rec = self.plan.recommend_review(
                    domain='general', complexity='standard', risk_flags=[risk], session_model='Opus 5.5'
                )
                self.assertEqual(rec['recommended_model'], 'Astra 6.2')
                self.assertEqual(rec['recommended_depth'], 'deep')

    def test_simple_changes_recommend_sol_and_lite_with_session_diversity(self):
        rec = self.plan.recommend_review(domain='simple', complexity='simple', session_model='Opus 5.5')
        self.assertEqual(rec['recommended_model'], 'Sol 6.2')
        self.assertEqual(rec['recommended_depth'], 'lite')
        self.assertEqual(rec['depth_options'][0]['depth'], 'lite')

        diversified = self.plan.recommend_review(domain='simple', complexity='simple', session_model='Sol 6.2')
        self.assertTrue(diversified['diversified_from_session'])
        self.assertNotEqual(diversified['recommended_model'], 'Sol 6.2')
        self.assertIn(diversified['recommended_model'], ('Neon 4', 'Opus 5.5'))
        self.assertEqual(diversified['recommended_depth'], 'lite')

    def test_frontend_and_general_diversify_between_opus_and_neon(self):
        from_opus = self.plan.recommend_review(domain='frontend', session_model='claude-opus-5-5')
        self.assertEqual(from_opus['recommended_model'], 'Neon 4')
        self.assertTrue(from_opus['diversified_from_session'])
        self.assertEqual(from_opus['recommended_depth'], 'lite')

        from_neon = self.plan.recommend_review(domain='frontend', session_model='Gemini 4 Neon')
        self.assertEqual(from_neon['recommended_model'], 'Opus 5.5')
        self.assertFalse(from_neon['diversified_from_session'])
        self.assertEqual(from_neon['model_options'][-1]['name'], 'Neon 4')

        fullstack = self.plan.recommend_review(domain='fullstack', session_model='Opus 5.5')
        self.assertEqual(fullstack['recommended_model'], 'Neon 4')
        self.assertEqual(fullstack['recommended_depth'], 'deep')

    def test_undetected_session_model_is_disclosed_honestly(self):
        for raw in (None, '', 'unknown', 'desconocido'):
            with self.subTest(raw=raw):
                rec = self.plan.recommend_review(domain='frontend', session_model=raw)
                self.assertFalse(rec['session_model_detected'])
                self.assertIsNone(rec['session_model_id'])
                self.assertTrue(rec['session_model_disclosure'])
                self.assertEqual(rec['recommended_model'], 'Opus 5.5')

    def test_explicit_user_overrides_suppress_only_answered_questions(self):
        both = self.plan.recommend_review(
            domain='backend', session_model='Opus 5.5', requested_model='Neon 4', requested_depth='lite'
        )
        self.assertEqual(both['selected_model'], 'Neon 4')
        self.assertEqual(both['selected_depth'], 'lite')
        self.assertFalse(both['needs_user_question'])
        self.assertEqual(both['questions_needed'], [])

        model_only = self.plan.recommend_review(domain='backend', requested_model='Astra 6.2')
        self.assertTrue(model_only['needs_user_question'])
        self.assertEqual(model_only['questions_needed'], ['depth'])

        depth_only = self.plan.recommend_review(domain='backend', requested_depth='deep')
        self.assertTrue(depth_only['needs_user_question'])
        self.assertEqual(depth_only['questions_needed'], ['model'])

    def test_invalid_inputs_raise_fixed_plan_errors(self):
        with self.assertRaises(self.plan.PlanError):
            self.plan.recommend_review(domain='invalid')
        with self.assertRaises(self.plan.PlanError):
            self.plan.recommend_review(complexity='massive')
        with self.assertRaises(self.plan.PlanError):
            self.plan.recommend_review(risk_flags=['unknown_risk'])
        with self.assertRaises(self.plan.PlanError):
            self.plan.recommend_review(requested_model='nonexistent-model')
        with self.assertRaises(self.plan.PlanError):
            self.plan.recommend_review(requested_depth='ultra')


    def test_model_family_matches_whole_words_only(self):
        cases = {
            'gpt-6.2-sol': 'sol-6.2', 'Sol 6.2': 'sol-6.2', 'sol6.2': 'sol-6.2',
            'claude-opus-5-5[1m]': 'opus-5.5', 'ASTRA_6.2': 'astra-6.2', 'gemini-4-neon': 'neon-4',
            # A family name inside another word is not that family.
            'console-resolver-1': None, 'astral-2': None, 'neonatal': None, 'magnum-opusculum': None,
            # Outside the catalog, ambiguous or a placeholder.
            'claude-fable-5-2': None, 'opus-or-neon': None, 'auto': None, 'default': None, '': None, None: None,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(self.plan.normalize_model_id(raw), expected)

    def test_placeholder_session_values_count_as_undetected(self):
        for raw in ('auto', 'default', 'inherit', 'AUTO', ' none '):
            with self.subTest(raw=raw):
                rec = self.plan.recommend_review(domain='backend', session_model=raw)
                self.assertFalse(rec['session_model_detected'])
                self.assertTrue(rec['session_model_disclosure'])
                self.assertEqual(rec['recommended_model'], 'Astra 6.2')

    def test_session_model_outside_catalog_is_detected_without_reordering(self):
        rec = self.plan.recommend_review(domain='backend', session_model='claude-fable-5-2')
        self.assertTrue(rec['session_model_detected'])
        self.assertIsNone(rec['session_model_id'])
        self.assertIsNone(rec['session_model_disclosure'])
        self.assertFalse(rec['diversified_from_session'])
        self.assertEqual([item['name'] for item in rec['model_options']],
                         ['Astra 6.2', 'Opus 5.5', 'Neon 4', 'Sol 6.2'])
        self.assertFalse(any(item['matches_session_model'] for item in rec['model_options']))

    def test_backend_with_astra_session_orders_opus_then_neon(self):
        for session in ('Astra 6.2', 'astra-6.2', 'gpt-6.2-astra'):
            with self.subTest(session=session):
                rec = self.plan.recommend_review(domain='backend', complexity='complex',
                                                 risk_flags=['auth'], session_model=session)
                self.assertEqual([item['id'] for item in rec['model_options'][:2]], ['opus-5.5', 'neon-4'])
                self.assertEqual(rec['model_options'][-1]['id'], 'astra-6.2')
                self.assertEqual(rec['recommended_depth'], 'deep')

    def test_requested_session_model_is_kept_and_flagged(self):
        rec = self.plan.recommend_review(domain='backend', session_model='Astra 6.2', requested_model='astra')
        self.assertEqual(rec['selected_model'], 'Astra 6.2')
        self.assertTrue(rec['selected_model_matches_session'])
        self.assertEqual(rec['recommended_model'], 'Opus 5.5')
        other = self.plan.recommend_review(domain='backend', session_model='Opus 5.5')
        self.assertFalse(other['selected_model_matches_session'])

    def test_models_without_a_route_are_never_recommended_over_available_ones(self):
        unchecked = self.plan.recommend_review(domain='backend', session_model='Opus 5.5')
        self.assertFalse(unchecked['availability_checked'])
        self.assertIsNone(unchecked['recommended_model_available'])
        self.assertTrue(all(item['available'] is None for item in unchecked['model_options']))

        rec = self.plan.recommend_review(domain='backend', session_model='Opus 5.5',
                                         available_models=['claude-opus-5-5', 'gpt-6.2-sol'])
        self.assertTrue(rec['availability_checked'])
        self.assertEqual(rec['recommended_model'], 'Sol 6.2')
        self.assertTrue(rec['recommended_model_available'])
        self.assertEqual([(item['id'], item['available']) for item in rec['model_options']],
                         [('sol-6.2', True), ('opus-5.5', True), ('astra-6.2', False), ('neon-4', False)])
        self.assertEqual([item['recommended'] for item in rec['model_options']], [True, False, False, False])

        only_session = self.plan.recommend_review(domain='backend', session_model='Opus 5.5',
                                                  available_models=['Opus 5.5'])
        self.assertEqual(only_session['recommended_model'], 'Opus 5.5')
        self.assertTrue(only_session['model_options'][0]['matches_session_model'])

        asked = self.plan.recommend_review(domain='backend', requested_model='Astra 6.2',
                                           available_models=['Neon 4'])
        self.assertEqual(asked['selected_model'], 'Astra 6.2')
        self.assertFalse(asked['selected_model_available'])

        none_reachable = self.plan.recommend_review(domain='backend', available_models=[])
        self.assertTrue(none_reachable['availability_checked'])
        self.assertEqual(none_reachable['recommended_model'], 'Astra 6.2')
        self.assertFalse(none_reachable['recommended_model_available'])

        with self.assertRaises(self.plan.PlanError):
            self.plan.recommend_review(available_models=['made-up-model'])


class PublishRulesAndInlinePayloadTests(unittest.TestCase):
    def setUp(self):
        self.plan = load_module()
        self.sample_diff = (
            'diff --git a/src/auth.py b/src/auth.py\n'
            'index 1111111..2222222 100644\n'
            '--- a/src/auth.py\n'
            '+++ b/src/auth.py\n'
            '@@ -10,4 +10,6 @@ def load_user(db, user_id):\n'
            '     row = db.fetch(user_id)\n'
            '-    return row\n'
            '+    if not row:\n'
            '+        return None\n'
            '+    return row.data\n'
            ' \n'
            'diff --git a/src/removed.py b/src/removed.py\n'
            'deleted file mode 100644\n'
            '--- a/src/removed.py\n'
            '+++ /dev/null\n'
            '@@ -1,2 +0,0 @@\n'
            '-old = 1\n'
            '-gone = 2\n'
        )

    def test_publish_target_matrix(self):
        local = self.plan.decide_publish_target(pr_url=None)
        self.assertEqual(local['destination'], 'local')
        self.assertFalse(local['publish_to_pr'])
        self.assertTrue(local['keep_local_record'])
        self.assertIsNone(local['github_event'])

        pr_std = self.plan.decide_publish_target(pr_url=PR_URL, direct_pr_mode=False)
        self.assertEqual(pr_std['destination'], 'pr_and_local')
        self.assertTrue(pr_std['publish_to_pr'])
        self.assertTrue(pr_std['keep_local_record'])
        self.assertFalse(pr_std['inline_comments'])
        self.assertEqual(pr_std['github_event'], 'COMMENT')

        pr_direct = self.plan.decide_publish_target(pr_url=PR_URL, direct_pr_mode=True)
        self.assertEqual(pr_direct['destination'], 'pr_review_inline_and_local')
        self.assertTrue(pr_direct['publish_to_pr'])
        self.assertTrue(pr_direct['inline_comments'])
        self.assertEqual(pr_direct['github_event'], 'COMMENT')

        public_sec = self.plan.decide_publish_target(
            pr_url=PR_URL, direct_pr_mode=True, is_public_repo=True, has_exploitable_security=True
        )
        self.assertTrue(public_sec['redact_security_exploits'])
        self.assertTrue(public_sec['recommend_private_advisory'])
        self.assertEqual(public_sec['github_event'], 'COMMENT')

        with self.assertRaises(self.plan.PlanError):
            self.plan.decide_publish_target(pr_url=None, direct_pr_mode=True)

    def test_extract_diff_right_lines(self):
        lines = self.plan.extract_diff_right_lines(self.sample_diff)
        self.assertEqual(lines, {'src/auth.py': {10, 11, 12, 13, 14}})

    def test_direct_pr_review_payload_partitions_inline_and_out_of_diff_without_duplicates(self):
        findings = [
            {
                'id': 'F1',
                'material': True,
                'status': 'open',
                'severity': 'high',
                'path': 'src/auth.py',
                'line': 13,
                'evidence': 'Retorna row.data sin validar tenant en /tmp/workspace/src/auth.py.',
                'conditions': 'Usuario autenticado de otro tenant.',
                'impact': 'Exposición de datos entre tenants.',
                'minimal_fix': 'Filtrar por tenant_id antes de retornar.',
                'visible_flow': 'GET /api/users/:id',
                'security_exploitable': True,
            },
            # Duplicate of F1 on same line must not double-post
            {
                'id': 'F1',
                'material': True,
                'status': 'open',
                'severity': 'high',
                'path': 'src/auth.py',
                'line': 13,
                'evidence': 'Duplicado que no debe publicarse dos veces.',
            },
            # Out-of-diff line must go into general summary
            {
                'id': 'F2',
                'material': True,
                'status': 'open',
                'severity': 'medium',
                'path': 'src/billing.py',
                'line': 88,
                'evidence': 'Consumidor fuera del diff espera objeto row en vez de row.data.',
                'minimal_fix': 'Actualizar llamada en src/billing.py.',
            },
            # Resolved or non-material findings must not be posted as open inline blockers
            {
                'id': 'F3',
                'material': True,
                'status': 'resolved',
                'path': 'src/auth.py',
                'line': 11,
                'evidence': 'Ya corregido antes de publicar.',
            },
            {
                'id': 'N1',
                'material': False,
                'status': 'open',
                'path': 'src/auth.py',
                'line': 12,
                'evidence': 'Detalle menor.',
            },
        ]
        result = self.plan.build_pr_review_payload(
            pr_url=PR_URL,
            head_sha=HEAD_SHA,
            summary_markdown='# Review consolidado: Cambios requeridos\n\nRevisado en /tmp/workspace.',
            findings=findings,
            diff_text=self.sample_diff,
            language='es',
            is_public_repo=True,
            local_root='/tmp/workspace',
        )
        payload = result['payload']
        self.assertEqual(result['endpoint'], 'repos/peqa-ai/sample-app/pulls/123/reviews')
        self.assertEqual(payload['event'], 'COMMENT')
        self.assertEqual(payload['commit_id'], HEAD_SHA)
        self.assertEqual(result['inline_count'], 1)
        self.assertEqual(result['out_of_diff_count'], 1)
        self.assertEqual(len(payload['comments']), 1)
        comment = payload['comments'][0]
        self.assertEqual((comment['path'], comment['line'], comment['side']), ('src/auth.py', 13, 'RIGHT'))
        self.assertIn('[F1]', comment['body'])
        self.assertNotIn('/tmp/workspace', comment['body'])
        self.assertIn('Hallazgos fuera del diff', payload['body'])
        self.assertIn('src/billing.py:88', payload['body'])
        self.assertNotIn('/tmp/workspace', payload['body'])
        self.assertEqual(len(result['orca_notes']), 1)
        self.assertTrue(result['orca_notes'][0].startswith('src/auth.py:13:[F1/high]'))
        self.assertTrue(result['policy']['recommend_private_advisory'])

    def test_invalid_pr_urls_and_finding_paths_are_rejected(self):
        for bad_url in (
            'http://github.com/org/repo/pull/1',
            'https://user:pass@github.com/org/repo/pull/1',
            'https://github.com/org/repo/issues/1',
        ):
            with self.subTest(bad_url=bad_url):
                with self.assertRaises(self.plan.PlanError):
                    self.plan.parse_pr_url(bad_url)

        with self.assertRaises(self.plan.PlanError):
            self.plan.build_pr_review_payload(
                PR_URL, HEAD_SHA, 'summary',
                [{'id': 'F1', 'material': True, 'status': 'open', 'path': '../etc/passwd', 'line': 1, 'evidence': 'x'}],
                self.sample_diff,
            )
        with self.assertRaises(self.plan.PlanError):
            self.plan.build_pr_review_payload(
                PR_URL, HEAD_SHA, 'summary',
                [{'id': 'F1', 'material': True, 'status': 'open', 'path': 'src/auth.py', 'line': True, 'evidence': 'x'}],
                self.sample_diff,
            )
        with self.assertRaises(self.plan.PlanError):
            self.plan.build_pr_review_payload(PR_URL, 'not-a-sha', 'summary', [], self.sample_diff)

    def payload(self, findings, diff=None, summary='# Review', **extra):
        return self.plan.build_pr_review_payload(
            PR_URL, HEAD_SHA, summary, findings, self.sample_diff if diff is None else diff, **extra)

    def finding(self, **extra):
        return {'id': 'F1', 'material': True, 'status': 'open', 'evidence': 'Falla.', **extra}

    def test_hunk_content_that_looks_like_a_header_stays_content(self):
        diff = (
            'diff --git a/a.c b/a.c\n--- a/a.c\n+++ b/a.c\n'
            '@@ -1,4 +1,5 @@\n one\n+++ counter;\n--- gone\n+back\n three\n four\n'
            '@@ -20 +21,2 @@ tail\n last\n+appended\n'
        )
        self.assertEqual(self.plan.extract_diff_right_lines(diff), {'a.c': {1, 2, 3, 4, 5, 21, 22}})

    def test_blank_context_lines_and_unusual_line_separators_keep_the_hunk_aligned(self):
        trimmed = 'diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,4 @@\n one\n\n+new\n three\n'
        self.assertEqual(self.plan.extract_diff_right_lines(trimmed), {'a.py': {1, 2, 3, 4}})
        form_feed = 'diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,3 @@\n one\x0cmore\n+new\u2028x\n three\n'
        self.assertEqual(self.plan.extract_diff_right_lines(form_feed), {'a.py': {1, 2, 3}})
        crlf = 'diff --git a/a.py b/a.py\r\n--- a/a.py\r\n+++ b/a.py\r\n@@ -1,2 +1,3 @@\r\n one\r\n+new\r\n three\r\n'
        self.assertEqual(self.plan.extract_diff_right_lines(crlf), {'a.py': {1, 2, 3}})

    def test_quoted_paths_renames_and_missing_newline_markers(self):
        diff = (
            'diff --git "a/src/caf\\303\\251.py" "b/src/caf\\303\\251.py"\n'
            '--- "a/src/caf\\303\\251.py"\n+++ "b/src/caf\\303\\251.py"\n'
            '@@ -1 +1,2 @@\n one\n+new\n\\ No newline at end of file\n'
            'diff --git a/old name.py b/new name.py\nsimilarity index 90%\n'
            'rename from old name.py\nrename to new name.py\n'
            '--- a/old name.py\t\n+++ b/new name.py\t\n@@ -5,2 +5,2 @@\n keep\n-old\n+new\n'
            'diff --git a/img.png b/img.png\nBinary files a/img.png and b/img.png differ\n'
        )
        self.assertEqual(self.plan.extract_diff_right_lines(diff),
                         {'src/café.py': {1, 2}, 'new name.py': {5, 6}})
        escaped = 'diff --git "a/..\\057x" "b/..\\057x"\n--- "a/..\\057x"\n+++ "b/..\\057x"\n@@ -1 +1 @@\n-a\n+b\n'
        self.assertEqual(self.plan.extract_diff_right_lines(escaped), {})

    def test_deleted_and_left_side_lines_fall_back_to_the_summary(self):
        result = self.payload([
            self.finding(id='F1', path='src/removed.py', line=1),
            self.finding(id='F2', path='src/auth.py', line=9),
            self.finding(id='F3', path='src/auth.py'),
            self.finding(id='F4'),
        ])
        self.assertEqual(result['inline_count'], 0)
        self.assertEqual(result['out_of_diff_count'], 4)
        self.assertEqual(result['payload']['comments'], [])
        self.assertEqual(result['orca_notes'], [])
        body = result['payload']['body']
        for expected in ('`src/removed.py:1`', '`src/auth.py:9`', '`src/auth.py`', '`sin ruta`'):
            self.assertIn(expected, body)

    def test_out_of_diff_bullets_stay_on_one_line(self):
        result = self.payload([self.finding(path='src/billing.py', line=3, evidence='Línea uno.\n\n## Dos',
                                            minimal_fix='Arreglo\ncon salto.')])
        bullet = [line for line in result['payload']['body'].splitlines() if line.startswith('- **F1**')]
        self.assertEqual(len(bullet), 1)
        self.assertIn('Línea uno. ## Dos', bullet[0])
        self.assertIn('Arreglo con salto.', bullet[0])

    def test_malformed_findings_fail_with_fixed_codes_not_tracebacks(self):
        bad = [
            self.finding(conditions=['lista']), self.finding(impact=3), self.finding(minimal_fix={'a': 1}),
            self.finding(severity='urgent'), self.finding(severity=2), self.finding(status='pending'),
            self.finding(material='yes'), self.finding(security_exploitable='true'),
            self.finding(evidence='   '), self.finding(id=7), 'F1', None,
        ]
        for item in bad:
            with self.subTest(item=item):
                with self.assertRaises(self.plan.PlanError) as caught:
                    self.payload([item])
                self.assertEqual(str(caught.exception), 'FINDINGS_INVALID')
        for findings in ('F1', 7, {'findings': 'F1'}, {'other': []}, [self.finding()] * 501):
            with self.subTest(findings=str(findings)[:30]):
                with self.assertRaises(self.plan.PlanError):
                    self.payload(findings)
        for line in (0, -1, 1.0, '13'):
            with self.subTest(line=line):
                with self.assertRaises(self.plan.PlanError) as caught:
                    self.payload([self.finding(path='src/auth.py', line=line)])
                self.assertEqual(str(caught.exception), 'INVALID_FINDING_LINE')
        for path in ('/abs/x.py', 'a\\b.py', '.git/config', 'a//b', 'a/./b', ''):
            with self.subTest(path=path):
                with self.assertRaises(self.plan.PlanError) as caught:
                    self.payload([self.finding(path=path, line=1)])
                self.assertEqual(str(caught.exception), 'INVALID_FINDING_PATH')

    def test_a_consolidated_report_object_is_accepted_as_findings_input(self):
        report = {'schema_version': 1, 'findings': [
            self.finding(path='src/auth.py', line=13, adjudication='Aceptado por el padre.', security_exploitable=False)]}
        result = self.payload(report)
        self.assertEqual(result['inline_count'], 1)

    def test_commit_id_must_be_a_full_sha(self):
        for bad in ('abc1234', 'a' * 39, 'a' * 41, 'g' * 40, '', None):
            with self.subTest(bad=bad):
                with self.assertRaises(self.plan.PlanError) as caught:
                    self.plan.build_pr_review_payload(PR_URL, bad, 'summary', [], self.sample_diff)
                self.assertEqual(str(caught.exception), 'HEAD_SHA_REQUIRED')
        upper = self.plan.build_pr_review_payload(PR_URL, 'A' * 40, 'summary', [], self.sample_diff)
        self.assertEqual(upper['payload']['commit_id'], 'a' * 40)
        sha256 = self.plan.build_pr_review_payload(PR_URL, 'b' * 64, 'summary', [], self.sample_diff)
        self.assertEqual(sha256['payload']['commit_id'], 'b' * 64)

    def test_local_root_never_rewrites_ordinary_text(self):
        summary = 'Versión 1.2.3 en ./src y a.b.c; ver /work/app/src/x.py, /work/app y /work/app-old/y.py.'
        for root in ('.', './', '', '/', None):
            with self.subTest(root=root):
                body = self.payload([], summary=summary, local_root=root)['payload']['body']
                self.assertEqual(body, summary)
        body = self.payload([], summary=summary, local_root='/work/app/')['payload']['body']
        self.assertEqual(body, 'Versión 1.2.3 en ./src y a.b.c; ver src/x.py, <repo> y /work/app-old/y.py.')

    def test_remaining_local_paths_are_reported_for_the_caller_to_fix(self):
        result = self.payload(
            [self.finding(path='src/auth.py', line=13, evidence='Traza en /Users/ana/proyecto/log.txt.')],
            summary='Informe en ~/notas/review.md y https://example.com/home/page; /work/app/x.py limpio.',
            local_root='/work/app')
        self.assertEqual(result['local_path_hits'], ['~/notas/review.md', '/Users/ana/proyecto/log.txt.'])
        self.assertEqual(self.payload([], summary='Sin rutas; ver src/x.py.')['local_path_hits'], [])

    def test_github_size_limits_fail_before_publishing(self):
        limit = self.plan.MAX_GITHUB_BODY_CHARS
        self.assertEqual(len(self.payload([], summary='x' * limit)['payload']['body']), limit)
        with self.assertRaises(self.plan.PlanError) as caught:
            self.payload([], summary='x' * (limit + 1))
        self.assertEqual(str(caught.exception), 'SUMMARY_TOO_LARGE')
        with self.assertRaises(self.plan.PlanError) as caught:
            self.payload([self.finding(path='src/auth.py', line=13, evidence='y' * limit)])
        self.assertEqual(str(caught.exception), 'COMMENT_TOO_LARGE')

    def test_exploitable_findings_name_what_a_public_repo_must_redact(self):
        findings = [
            self.finding(id='S1', path='src/auth.py', line=13, security_exploitable=True),
            self.finding(id='S2', path='src/billing.py', line=2, security_exploitable=True),
            self.finding(id='S3', status='resolved', security_exploitable=True),
            self.finding(id='F4', path='src/auth.py', line=12),
        ]
        public = self.payload(findings, is_public_repo=True)
        self.assertEqual(public['redaction_required_ids'], ['S1', 'S2'])
        self.assertTrue(public['policy']['redact_security_exploits'])
        self.assertEqual(public['payload']['event'], 'COMMENT')
        private = self.payload(findings, is_public_repo=False)
        self.assertEqual(private['redaction_required_ids'], [])
        self.assertFalse(private['policy']['redact_security_exploits'])

    def test_payload_never_carries_an_approving_or_blocking_event(self):
        result = self.payload([self.finding(path='src/auth.py', line=13)])
        self.assertEqual(set(result['payload']), {'commit_id', 'event', 'body', 'comments'})
        self.assertEqual(result['payload']['event'], 'COMMENT')
        self.assertEqual(set(result['payload']['comments'][0]), {'path', 'line', 'side', 'body'})

    def test_malformed_pr_urls_fail_with_fixed_codes(self):
        cases = {
            'https://github.com:99999/org/repo/pull/1': 'INVALID_PR_PORT',
            'https://github.com:abc/org/repo/pull/1': 'INVALID_PR_PORT',
            'https://[::1/org/repo/pull/1': 'HTTPS_PR_URL_REQUIRED',
            'https://github.com/org/repo/pull/0': 'PR_WEB_URL_REQUIRED',
            'https://github.com/org/repo/pull/12/files': 'PR_WEB_URL_REQUIRED',
            'https://github.com/../repo/pull/1': 'PR_WEB_URL_REQUIRED',
            '   ': 'PR_URL_REQUIRED',
        }
        for url, code in cases.items():
            with self.subTest(url=url):
                with self.assertRaises(self.plan.PlanError) as caught:
                    self.plan.parse_pr_url(url)
                self.assertEqual(str(caught.exception), code)
        parsed = self.plan.parse_pr_url('https://GitHub.Example.com:443/Org/Repo/pull/7/?diff=split#files')
        self.assertEqual(parsed['canonical_url'], 'https://github.example.com/org/repo/pull/7')
        self.assertEqual(parsed['reviews_endpoint'], 'repos/Org/Repo/pulls/7/reviews')
        self.assertEqual(parsed['host'], 'github.example.com')

    def test_cli_reports_bad_input_as_json_without_tracebacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'summary.md').write_text('# Review\n', encoding='utf-8')
            (root / 'pr.diff').write_text(self.sample_diff, encoding='utf-8')
            (root / 'deep.json').write_text('[' * 100000, encoding='utf-8')
            (root / 'shape.json').write_text(json.dumps([{'id': 'F1', 'evidence': 'x', 'conditions': ['a']}]),
                                             encoding='utf-8')
            (root / 'binary.json').write_bytes(b'\xff\xfe')
            base = [sys.executable, str(SCRIPT), 'pr-review-payload', '--pr-url', PR_URL, '--head', HEAD_SHA,
                    '--summary-file', str(root / 'summary.md'), '--diff-file', str(root / 'pr.diff')]
            cases = [
                (base + ['--findings-file', str(root / 'deep.json')], 'FINDINGS_INVALID'),
                (base + ['--findings-file', str(root / 'shape.json')], 'FINDINGS_INVALID'),
                (base + ['--findings-file', str(root / 'binary.json')], 'INPUT_INVALID'),
                (base + ['--findings-file', str(root / 'missing.json')], 'INPUT_UNREADABLE'),
                ([sys.executable, str(SCRIPT), 'publish-plan', '--pr-url', 'https://github.com:99999/o/r/pull/1'],
                 'INVALID_PR_PORT'),
                ([sys.executable, str(SCRIPT), 'recommend', '--domain', 'backend', '--available', 'nope'],
                 'INVALID_AVAILABLE_MODEL'),
                ([sys.executable, str(SCRIPT), 'recommend', '--domain', 'cobol'], 'ARGUMENTS_INVALID'),
            ]
            for command, code in cases:
                with self.subTest(code=code, last=command[-1][-20:]):
                    proc = subprocess.run(command, capture_output=True, text=True, timeout=15)
                    self.assertEqual(proc.returncode, 2, proc.stderr)
                    self.assertEqual(proc.stdout, '')
                    self.assertEqual(json.loads(proc.stderr), {'error': code})
                    self.assertNotIn('Traceback', proc.stderr)

        available = subprocess.run(
            [sys.executable, str(SCRIPT), 'recommend', '--domain', 'backend', '--session-model', 'Opus 5.5',
             '--available', 'Opus 5.5', '--available', 'Neon 4'],
            capture_output=True, text=True, check=True, timeout=15)
        self.assertEqual(json.loads(available.stdout)['recommended_model'], 'Neon 4')

    def test_cli_subcommands(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), 'recommend', '--domain', 'backend', '--session-model', 'Opus 5.5'],
            capture_output=True, text=True, check=True, timeout=15,
        )
        rec = json.loads(proc.stdout)
        self.assertEqual(rec['recommended_model'], 'Astra 6.2')
        self.assertEqual(rec['recommended_depth'], 'deep')

        pub_proc = subprocess.run(
            [sys.executable, str(SCRIPT), 'publish-plan', '--pr-url', PR_URL, '--direct-pr'],
            capture_output=True, text=True, check=True, timeout=15,
        )
        pub = json.loads(pub_proc.stdout)
        self.assertEqual(pub['destination'], 'pr_review_inline_and_local')
        self.assertEqual(pub['github_event'], 'COMMENT')

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary_f = root / 'summary.md'
            findings_f = root / 'findings.json'
            diff_f = root / 'pr.diff'
            summary_f.write_text('# Consolidated review: Changes required\n', encoding='utf-8')
            findings_f.write_text(json.dumps([
                {'id': 'F1', 'material': True, 'status': 'open', 'severity': 'high',
                 'path': 'src/auth.py', 'line': 13, 'evidence': 'Missing check.'}
            ]), encoding='utf-8')
            diff_f.write_text(self.sample_diff, encoding='utf-8')
            payload_proc = subprocess.run(
                [sys.executable, str(SCRIPT), 'pr-review-payload',
                 '--pr-url', PR_URL, '--head', HEAD_SHA,
                 '--summary-file', str(summary_f),
                 '--findings-file', str(findings_f),
                 '--diff-file', str(diff_f), '--language', 'en'],
                capture_output=True, text=True, check=True, timeout=15,
            )
            data = json.loads(payload_proc.stdout)
            self.assertEqual(data['payload']['event'], 'COMMENT')
            self.assertEqual(data['inline_count'], 1)


class DocumentedCommandsTests(unittest.TestCase):
    """The references show commands agents copy; every flag they show must exist."""

    DOCS = ('skills/revisa/references/reviewers.md', 'skills/revisa/references/report.md')

    def documented_flags(self):
        root = SCRIPT.parents[3]
        found = {}
        for name in self.DOCS:
            text = (root / name).read_text(encoding='utf-8')
            # Join shell continuations so one command is one line.
            for line in text.replace('\\\n', ' ').splitlines():
                match = re.search(r'\$REVIEW_PLAN_SCRIPT"\s+([a-z-]+)(.*)', line)
                if match:
                    command = match.group(2).split('|')[0].split('>')[0]
                    found.setdefault(match.group(1), set()).update(re.findall(r'(?<![\w-])--[a-z][a-z-]*', command))
        return found

    def test_every_documented_review_plan_flag_is_accepted(self):
        found = self.documented_flags()
        self.assertEqual(set(found), {'recommend', 'publish-plan', 'pr-review-payload'})
        for action, flags in found.items():
            proc = subprocess.run([sys.executable, str(SCRIPT), action, '--help'],
                                  capture_output=True, text=True, check=True, timeout=15)
            accepted = set(re.findall(r'(?<![\w-])--[a-z][a-z-]*', proc.stdout))
            with self.subTest(action=action):
                self.assertTrue(flags, action)
                self.assertFalse(flags - accepted, f'{action} documents unknown flags')

    def test_documented_risk_flags_match_the_helper(self):
        plan = load_module()
        text = (SCRIPT.parents[3] / self.DOCS[0]).read_text(encoding='utf-8')
        listed = re.search(r'`--risk` repetible \(([^)]*)\)', text)
        self.assertIsNotNone(listed)
        documented = set(re.findall(r'`([a-z_]+)`', listed.group(1)))
        self.assertEqual(documented | {'migrations'}, set(plan.HIGH_RISK_FLAGS))


if __name__ == '__main__':
    unittest.main()
