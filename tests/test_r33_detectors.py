# Copyright (c) 2025 0xnq (jieecode) <mail@0xnq.cc>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

import sys, pathlib, unittest
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent / "mindseam" / "scripts"))
import mindseam

class R33VerificationTests(unittest.TestCase):
    
    def test_verification_registry_empty(self):
        self.assertEqual(mindseam.verification_regression([]), 100)

    def test_verification_registry_short(self):
        h = [dict(t=1000, next='N0', confidence='thin', risk='low', verified=1)]
        self.assertEqual(mindseam.verification_regression(h), 100)

    def test_verification_registry_stable(self):
        h = [dict(t=1000+i, next='N%d'%i, confidence='thin', risk='low', verified=1) for i in range(3)]
        self.assertEqual(mindseam.verification_regression(h), 100)

    def test_verification_registry_unstable(self):
        h = [dict(t=1000+i, next='N%d'%i, confidence='thin', risk='low', verified=(1 if i%2==0 else 0)) for i in range(3)]
        score = mindseam.verification_regression(h)
        self.assertLess(score, 50)
        self.assertGreaterEqual(score, 0)

    def test_verification_registry_partial(self):
        h = [dict(t=1000, next='N0', confidence='thin', risk='low', verified=1),
             dict(t=1001, next='N1', confidence='thin', risk='low', verified=1),
             dict(t=1002, next='N2', confidence='thin', risk='low', verified=0)]
        score = mindseam.verification_regression(h)
        self.assertGreater(score, 0)
        self.assertLess(score, 100)

    def test_step_retry_rate_empty(self):
        self.assertEqual(mindseam.step_retry_rate([]), 100)

    def test_step_retry_rate_short(self):
        h = [dict(t=1000, next='N0', confidence='thin', risk='low')]
        self.assertEqual(mindseam.step_retry_rate(h), 100)

    def test_step_retry_rate_no_retry(self):
        h = [dict(t=1000+i, next='N%d'%i, confidence='thin', risk='low') for i in range(6)]
        self.assertEqual(mindseam.step_retry_rate(h), 100)

    def test_step_retry_rate_all_same(self):
        h = [dict(t=1000+i, next='N1', confidence='thin', risk='low') for i in range(6)]
        score = mindseam.step_retry_rate(h)
        self.assertLess(score, 30)
        self.assertGreaterEqual(score, 0)

    def test_step_retry_rate_partial(self):
        h = [dict(t=1000, next='N1', confidence='thin', risk='low'),
             dict(t=1001, next='N2', confidence='thin', risk='low'),
             dict(t=1002, next='N3', confidence='thin', risk='low'),
             dict(t=1003, next='N1', confidence='thin', risk='low'),
             dict(t=1004, next='N1', confidence='thin', risk='low'),
             dict(t=1005, next='N5', confidence='thin', risk='low')]
        score = mindseam.step_retry_rate(h)
        self.assertGreater(score, 0)
        self.assertLess(score, 100)

    def test_observations_verification_regression_fact(self):
        h = [dict(t=1000+i, next='N%d'%i, confidence='thin', risk='low', verified=(1 if i%2==0 else 0)) for i in range(3)]
        facts = mindseam.observations(h)
        self.assertTrue(any('verification regression' in f.lower() for f in facts), facts)

    def test_observations_step_retry_rate_fact(self):
        h = [dict(t=1000+i, next='N1', confidence='thin', risk='low') for i in range(6)]
        facts = mindseam.observations(h)
        self.assertTrue(any('step retry score is low' in f.lower() for f in facts), facts)

    def test_session_health_score_verification_regression_penalty(self):
        h = [dict(t=1000+i, next='N%d'%i, confidence='thin', risk='low', verified=(1 if i%2==0 else 0)) for i in range(3)]
        score, reasons = mindseam.session_health_score(h)
        self.assertTrue(any('verification regression' in r.lower() for r in reasons), reasons)

    def test_session_health_score_step_retry_rate_penalty(self):
        h = [dict(t=1000+i, next='N1', confidence='thin', risk='low') for i in range(6)]
        score, reasons = mindseam.session_health_score(h)
        self.assertTrue(any('step retry rate' in r.lower() for r in reasons), reasons)

    def test_premature_convergence_reaches_score_path(self):
        h = [dict(t=1000+i, next='N%d'%i, confidence='thin', risk='low', verified=0, marker='DONE') for i in range(3)]
        score, reasons = mindseam.session_health_score(h, book=None)
        self.assertTrue(any('premature convergence' in r.lower() for r in reasons), reasons)

    def test_premature_convergence_no_false_positive_no_book(self):
        h = [dict(t=1000+i, next='N%d'%i, confidence='thin', risk='low') for i in range(3)]
        score, reasons = mindseam.session_health_score(h)
        self.assertFalse(any('premature convergence' in r.lower() for r in reasons), reasons)
