"""Tests for reviewer model/depth recommendation and PR inline review payload helper."""

import importlib.util
import json
from pathlib import Path
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


if __name__ == '__main__':
    unittest.main()
